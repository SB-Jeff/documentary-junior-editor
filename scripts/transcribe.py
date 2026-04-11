#!/usr/bin/env python3
"""
Auto-transcription script for the documentary-junior-editor skill.

Scans a project's transcripts/audio/ folder for audio files, sends each to
AssemblyAI for transcription with speaker diarization, and saves formatted
.txt transcripts to transcripts/text/. Skips any audio file that already
has a matching .txt in the text folder.

Usage:
    python3 transcribe.py /path/to/project

    # Or set the API key explicitly:
    ASSEMBLYAI_API_KEY=your_key python3 transcribe.py /path/to/project

Requirements:
    pip install assemblyai python-dotenv
"""

import sys
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env — checks multiple locations so the script works whether it's
# running from an SSD project copy, the Desktop repo, or anywhere else.
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv

    script_dir = Path(__file__).resolve().parent

    # Priority 1: .env in the documentary-junior-editor/ folder (SSD / standalone)
    skill_env = script_dir.parent / ".env"
    if skill_env.exists():
        load_dotenv(skill_env)

    # Priority 2: file-api/.env in the repo (when running from the repo directly)
    repo_env = script_dir.parents[2] / "file-api" / ".env"
    if repo_env.exists():
        load_dotenv(repo_env, override=False)

    # Priority 3: file-api/.env on the Mac mini Desktop (when running from SSD)
    mac_mini_env = Path.home() / "Desktop" / "storyboard-ops" / "file-api" / ".env"
    if mac_mini_env.exists():
        load_dotenv(mac_mini_env, override=False)
except ImportError:
    pass  # python-dotenv not installed — rely on env vars being set directly

import assemblyai as aai

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}


def ms_to_timestamp(ms: int) -> str:
    """Convert milliseconds to a MM:SS timestamp string."""
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def format_transcript(filename: str, utterances: list) -> str:
    """Format AssemblyAI utterances into a readable transcript."""
    lines = [f"Transcript: {filename}\n"]
    for u in utterances:
        ts = ms_to_timestamp(u.start)
        lines.append(f"\n{ts} Speaker {u.speaker}: {u.text}")
    return "\n".join(lines) + "\n"


def main():
    # -----------------------------------------------------------------------
    # Parse arguments
    # -----------------------------------------------------------------------
    if len(sys.argv) < 2:
        print("Usage: python3 transcribe.py /path/to/project")
        print("\nTranscribes audio files in <project>/transcripts/audio/")
        print("and saves .txt transcripts to <project>/transcripts/text/")
        sys.exit(1)

    project_path = Path(sys.argv[1]).resolve()
    audio_dir = project_path / "transcripts" / "audio"
    text_dir = project_path / "transcripts" / "text"

    # -----------------------------------------------------------------------
    # Validate paths
    # -----------------------------------------------------------------------
    if not project_path.is_dir():
        print(f"Error: Project folder not found: {project_path}")
        sys.exit(1)

    if not audio_dir.is_dir():
        print(f"Error: Audio folder not found: {audio_dir}")
        print("Expected folder structure: <project>/transcripts/audio/")
        sys.exit(1)

    # Create text output folder if it doesn't exist
    text_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Check API key
    # -----------------------------------------------------------------------
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("Error: ASSEMBLYAI_API_KEY not set.")
        print("Set it as an environment variable or place it in a .env file")
        print("in the documentary-junior-editor/ folder.")
        sys.exit(1)

    aai.settings.api_key = api_key

    # -----------------------------------------------------------------------
    # Find audio files that need transcription
    # -----------------------------------------------------------------------
    existing_transcripts = {
        f.stem for f in text_dir.iterdir() if f.suffix == ".txt"
    }

    audio_files = sorted([
        f for f in audio_dir.iterdir()
        if f.suffix.lower() in AUDIO_EXTENSIONS
    ])

    if not audio_files:
        print(f"No audio files found in {audio_dir}")
        sys.exit(0)

    to_transcribe = []
    skipped = []

    for af in audio_files:
        if af.stem in existing_transcripts:
            skipped.append(af.name)
        else:
            to_transcribe.append(af)

    if skipped:
        print(f"Skipping {len(skipped)} already-transcribed file(s): {', '.join(skipped)}")

    if not to_transcribe:
        print("All audio files already have transcripts. Nothing to do.")
        sys.exit(0)

    print(f"\nTranscribing {len(to_transcribe)} file(s)...\n")

    # -----------------------------------------------------------------------
    # Transcribe each file
    # -----------------------------------------------------------------------
    config = aai.TranscriptionConfig(
        speaker_labels=True,
        language_detection=True,
        speech_models=["universal-3-pro", "universal-2"],
    )
    transcriber = aai.Transcriber()

    results = {"transcribed": [], "errors": []}

    for af in to_transcribe:
        print(f"  Transcribing: {af.name} ...")

        try:
            transcript = transcriber.transcribe(str(af), config=config)

            if transcript.status == aai.TranscriptStatus.error:
                print(f"    Error: {transcript.error}")
                results["errors"].append({"file": af.name, "error": transcript.error})
                continue

            utterances = transcript.utterances or []
            formatted = format_transcript(af.name, utterances)

            out_path = text_dir / f"{af.stem}.txt"
            out_path.write_text(formatted, encoding="utf-8")

            speakers = len({u.speaker for u in utterances})
            print(f"    Saved: {af.stem}.txt ({len(utterances)} utterances, {speakers} speaker(s))")
            results["transcribed"].append(af.name)

        except Exception as e:
            print(f"    Failed: {e}")
            results["errors"].append({"file": af.name, "error": str(e)})

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"\n--- Done ---")
    print(f"Transcribed: {len(results['transcribed'])}")
    print(f"Skipped:     {len(skipped)}")
    print(f"Errors:      {len(results['errors'])}")

    if results["errors"]:
        print("\nErrors:")
        for err in results["errors"]:
            print(f"  {err['file']}: {err['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
