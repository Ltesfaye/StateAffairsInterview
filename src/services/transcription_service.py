import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional

import whisper
from openai import OpenAI
import google.generativeai as genai

from ..utils.logger import get_logger

logger = get_logger(__name__, service_name="transcription-service")

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
        result = self.model.transcribe(str(audio_path))
        
        duration = time.time() - start_time
        logger.info(f"Local Whisper finished transcription in {duration:.2f} seconds")
        
        return {
            "text": result["text"],
            "segments": result["segments"],
            "duration": duration,
            "provider": "local_whisper"
        }

class OpenAIWhisperProvider(TranscriptionProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def transcribe(self, audio_path: Path) -> Dict[str, Any]:
        start_time = time.time()
        with open(audio_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                response_format="verbose_json"
            )
        return {
            "text": transcript.text,
            "segments": transcript.segments,
            "duration": time.time() - start_time,
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

    def transcribe(self, audio_path: Path) -> Dict[str, Any]:
        start_time = time.time()
        model = genai.GenerativeModel(self.model_name)
        
        # Upload the file to Gemini
        logger.info(f"Uploading {audio_path} to Gemini {self.model_name}...")
        audio_file = genai.upload_file(path=str(audio_path))
        
        # Wait for processing
        while audio_file.state.name == "PROCESSING":
            time.sleep(2)
            audio_file = genai.get_file(audio_file.name)
            
        if audio_file.state.name == "FAILED":
            raise Exception("Gemini audio processing failed")

        prompt = """
        Perform a verbatim transcription of this audio file. 
        Format the output as follows:
        - Identify each speaker (e.g., Speaker 1, Speaker 2, or by name/title if mentioned).
        - Provide a timestamp in [HH:MM:SS] format at the start of every new speaker segment or every 2 minutes.
        - Transcribe every word exactly as spoken.
        - Do NOT summarize or omit any parts of the conversation.
        """
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

