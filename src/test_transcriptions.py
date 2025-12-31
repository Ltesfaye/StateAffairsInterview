import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv

from src.services.transcription_service import get_provider
from src.utils.logger import get_logger

# Load environment variables from .env if it exists
load_dotenv()

logger = get_logger(__name__, service_name="transcription-benchmark")

def extract_audio(video_path: Path) -> Path:
    """Extract audio from video file using FFmpeg"""
    audio_path = video_path.with_suffix(".wav")
    if audio_path.exists():
        logger.info(f"Audio file already exists: {audio_path}")
        return audio_path
    
    logger.info(f"Extracting audio from {video_path} to {audio_path}")
    command = [
        "ffmpeg", "-i", str(video_path),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(audio_path), "-y"
    ]
    subprocess.run(command, check=True, capture_output=True)
    return audio_path

def main():
    parser = argparse.ArgumentParser(description="Benchmark transcription providers")
    parser.add_argument("file", help="Path to video or audio file")
    parser.add_argument("--providers", nargs="+", default=["local", "openai", "gemini"], 
                        help="Providers to test (local, openai, gemini)")
    parser.add_argument("--output-dir", default="data/test_bench", help="Directory to save results")
    args = parser.parse_args()

    input_path = Path(args.file)
    if not input_path.exists():
        logger.error(f"File not found: {input_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract audio if it's a video file
    if input_path.suffix.lower() in [".mp4", ".mkv", ".mov"]:
        audio_path = extract_audio(input_path)
    else:
        audio_path = input_path

    results = {}

    for provider_name in args.providers:
        logger.info(f"--- Running transcription with provider: {provider_name} ---")
        try:
            # Configure provider-specific settings from env or defaults
            kwargs = {
                "whisper_model": os.getenv("WHISPER_MODEL", "base"),
                "openai_api_key": os.getenv("OPENAI_API_KEY"),
                "google_api_key": os.getenv("GOOGLE_API_KEY"),
                "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.0-flash-preview-001")
            }
            
            provider = get_provider(provider_name, **kwargs)
            result = provider.transcribe(audio_path)
            
            results[provider_name] = result
            
            # Save individual result
            provider_file = output_dir / f"{input_path.stem}_{provider_name}.json"
            with open(provider_file, "w") as f:
                json.dump(result, f, indent=2)
            
            logger.info(f"Successfully transcribed with {provider_name} in {result['duration']:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed transcription with {provider_name}: {e}")
            results[provider_name] = {"error": str(e)}

    # Save summary
    summary_file = output_dir / f"{input_path.stem}_summary.json"
    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Benchmark complete. Results saved to {output_dir}")

if __name__ == "__main__":
    main()

