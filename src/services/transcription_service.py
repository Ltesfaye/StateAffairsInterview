import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import timedelta

import whisper
from openai import OpenAI
import google.generativeai as genai

from ..utils.logger import get_logger

logger = get_logger(__name__, service_name="transcription-service")

def format_timestamp(seconds: float) -> str:
    """Convert seconds to [HH:MM:SS] format"""
    td = timedelta(seconds=int(seconds))
    # Ensure HH:MM:SS format even for durations > 24h or < 1h
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"

class TranscriptionProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> Dict[str, Any]:
        pass

class LocalWhisperProvider(TranscriptionProvider):
    def __init__(self, model_name: str = "base"):
        logger.info(f"Loading local Whisper model: {model_name}")
        self.model = whisper.load_model(model_name)

    def transcribe(self, audio_path: Path) -> Dict[str, Any]:
        logger.info(f"Local Whisper starting transcription for: {audio_path}")
        start_time = time.time()
        
        # This is the 'heavy' part that takes time
        result = self.model.transcribe(
            str(audio_path),
            initial_prompt="A verbatim transcription of a legislative session. Maintain all filler words and formal language."
        )
        
        segments = result.get("segments", [])
        formatted_lines = []
        
        for segment in segments:
            start = segment.get('start', 0)
            text = segment.get('text', "")
            ts = format_timestamp(start)
            formatted_lines.append(f"{ts} **Speaker:** {text.strip()}")
            
        full_text = "\n".join(formatted_lines)
        duration = time.time() - start_time
        logger.info(f"Local Whisper finished transcription in {duration:.2f} seconds")
        
        return {
            "text": full_text,
            "segments": segments,
            "duration": duration,
            "provider": "local_whisper"
        }

class OpenAIWhisperProvider(TranscriptionProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def transcribe(self, audio_path: Path) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"OpenAI Whisper starting transcription for: {audio_path}")
        
        with open(audio_path, "rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                response_format="verbose_json",
                prompt="A verbatim transcription of a legislative session. Maintain all filler words and formal language."
            )
        
        # verbose_json returns segments. We map them to our unified format.
        segments = getattr(response, 'segments', [])
        formatted_lines = []
        
        for segment in segments:
            # handle both dict and object access
            start = segment.get('start') if isinstance(segment, dict) else getattr(segment, 'start', 0)
            text = segment.get('text') if isinstance(segment, dict) else getattr(segment, 'text', "")
            
            ts = format_timestamp(start)
            formatted_lines.append(f"{ts} **Speaker:** {text.strip()}")
            
        full_text = "\n".join(formatted_lines)
        duration = time.time() - start_time
        logger.info(f"OpenAI Whisper finished transcription in {duration:.2f} seconds")

        return {
            "text": full_text,
            "segments": segments,
            "duration": duration,
            "provider": "openai_whisper"
        }

class GeminiTranscriptionProvider(TranscriptionProvider):
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        # Use provided model_name or fallback to env or hard default
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        genai.configure(api_key=api_key or os.getenv("GOOGLE_API_KEY"))
        
        # Standardize: Ensure the model string doesn't have the 'models/' prefix
        if self.model_name.startswith("models/"):
            self.model_name = self.model_name.replace("models/", "")

        self.system_instruction = """
        You are a professional transcriptionist for the Michigan Legislature. 
        Your goal is to provide a verbatim, word-for-word transcript.

        STRICT FORMATTING RULES:
        1. Every entry MUST start with a timestamp in [HH:MM:SS] format.
        2. Use bold speaker labels: **Speaker Name/Title:**.
        3. Format: [HH:MM:SS] **Speaker Name/Title:** Verbatim text...
        4. Identify roles where possible (e.g., **Mr. Speaker:**, **Clerk:**, **Representative [Name]:**).
        5. If a speaker is unknown, use **Speaker 1:**, **Speaker 2:**, etc.
        6. Include a new timestamp and label whenever the speaker changes.
        7. For long speeches, include a timestamp at least every 2 minutes.
        8. Describe non-speech events in brackets: [HH:MM:SS] [Gavel strikes], [HH:MM:SS] [Ambient noise].
        9. DO NOT summarize. DO NOT omit filler words if they are part of the formal record.
        """

    def transcribe(self, audio_path: Path) -> Dict[str, Any]:
        start_time = time.time()
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_instruction
        )
        
        # Upload the file to Gemini
        logger.info(f"Uploading {audio_path} to Gemini {self.model_name}...")
        audio_file = genai.upload_file(path=str(audio_path))
        
        # Wait for processing
        while audio_file.state.name == "PROCESSING":
            time.sleep(2)
            audio_file = genai.get_file(audio_file.name)
            
        if audio_file.state.name == "FAILED":
            raise Exception("Gemini audio processing failed")

        prompt = "Provide a verbatim transcription of this audio file following the system instructions."
        response = model.generate_content([prompt, audio_file])
        
        return {
            "text": response.text,
            "duration": time.time() - start_time,
            "provider": f"gemini_3.0_{self.model_name}"
        }

def get_provider(provider_type: str, **kwargs) -> TranscriptionProvider:
    if provider_type == "local":
        return LocalWhisperProvider(model_name=kwargs.get("whisper_model", "base"))
    elif provider_type == "openai":
        return OpenAIWhisperProvider(api_key=kwargs.get("openai_api_key"))
    elif provider_type == "gemini":
        return GeminiTranscriptionProvider(
            api_key=kwargs.get("google_api_key"),
            model_name=kwargs.get("gemini_model")
        )
    else:
        raise ValueError(f"Unknown transcription provider: {provider_type}")

