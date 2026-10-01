"""CLI entry point: argument parsing, user prompts, and main pipeline."""

import os
import sys
import argparse

from .pipeline import (
    find_videos, find_audios,
    concat_videos, concat_audios,
    extract_audio, split_audio,
    banner, hr,
)
from .api import transcribe_all, generate_summary
from .gdoc import dump_frontmatter

DEFAULT_MODEL     = "google/gemini-2.5-flash"
DEFAULT_CHUNK_SEC = 600


def _load_dotenv():
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for candidate in [os.path.join(script_dir, ".env"), ".env"]:
        if os.path.isfile(candidate):
            with open(candidate) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())
            break


CONTEXT_FIELDS = [
    ("title",    "Recording title / topic"),
    ("speaker",  "Speaker(s) name & background"),
    ("audience", "Intended audience"),
    ("date",     "Date / event"),
    ("purpose",  "Purpose / goals of this session"),
    ("notes",    "Any other relevant notes"),
]


def ask_context():
    print()
    print("  Please provide background context for this recording.")
    print("  This helps the AI transcribe and summarize more accurately.")
    print("  (Press Enter to skip any field)\n")

    answers = {}
    for key, label in CONTEXT_FIELDS:
        val = input(f"  {label}: ").strip()
        if val:
            answers[key] = val

    return answers


def format_context_for_ai(answers):
    """Human-readable context block fed to the model for transcription/summarization."""
    if not answers:
        return ""
    labels = dict(CONTEXT_FIELDS)
    lines = ["Recording Context:"] + [f"  - {labels[k]}: {v}" for k, v in answers.items()]
    return "\n".join(lines)


def format_context_frontmatter(answers):
    """Obsidian-compatible YAML frontmatter block (without the surrounding ---)."""
    return dump_frontmatter(answers)


def parse_args():
    p = argparse.ArgumentParser(
        description="Full pipeline: concat videos → audio → transcribe → summarize",
    )
    p.add_argument("video_dir", nargs="?", default=".",
                   help="Directory with video/audio files (default: current directory)")
    p.add_argument("--api-key",       default=os.environ.get("OPENROUTER_API_KEY", ""),
                   help="OpenRouter API key (or set OPENROUTER_API_KEY env var)")
    p.add_argument("--model",         default=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL),
                   help=f"Model to use (default: $OPENROUTER_MODEL, else {DEFAULT_MODEL})")
    p.add_argument("--chunk",         type=int, default=DEFAULT_CHUNK_SEC, metavar="SECS",
                   help=f"Audio chunk size in seconds (default: {DEFAULT_CHUNK_SEC})")
    p.add_argument("--source-lang",   default="English,Traditional Chinese",
                   help='Comma-separated languages in the audio (default: "English,Traditional Chinese")')
    p.add_argument("--summary-lang",  default="Traditional Chinese",
                   help='Output language for the summary (default: "Traditional Chinese")')
    p.add_argument("--timestamps",    action="store_true",
                   help="Annotate audio timestamps in the Detailed Breakdown (off by default)")
    p.add_argument("--keep-chunks",   action="store_true",
                   help="Keep intermediate audio chunk files after completion")
    p.add_argument("--no-concat",     action="store_true",
                   help="Skip concat; use existing combined.mp4 or single video")
    p.add_argument("--no-extract",    action="store_true",
                   help="Skip audio extraction; use existing audio.m4a")
    p.add_argument("--no-transcribe", action="store_true",
                   help="Skip transcription; use existing full_transcript.txt")
    p.add_argument("--output",        default="summary.md",
                   help="Output summary filename (default: summary.md)")
    p.add_argument("--work-dir",      default="",
                   help="Working directory for intermediate files (default: VIDEO_DIR)")
    return p.parse_args()


def main():
    _load_dotenv()
    args = parse_args()

    video_dir = os.path.abspath(args.video_dir)
    work_dir  = os.path.abspath(args.work_dir) if args.work_dir else video_dir
    os.makedirs(work_dir, exist_ok=True)
    os.chdir(work_dir)

    combined_video  = os.path.join(work_dir, "combined.mp4")
    audio_file      = os.path.join(work_dir, "audio.m4a")
    chunk_dir       = os.path.join(work_dir, "audio_chunks")
    transcript_file = os.path.join(work_dir, "full_transcript.txt")
    output_file     = os.path.join(work_dir, args.output)

    source_langs = [s.strip() for s in args.source_lang.split(",")]
    summary_lang = args.summary_lang

    # ── API key ──
    api_key = args.api_key
    if not api_key:
        api_key = input("OpenRouter API key: ").strip()
    if not api_key:
        print("ERROR: API key required. Use --api-key or set OPENROUTER_API_KEY.")
        sys.exit(1)

    # ── Context ──
    banner("Recording Context")
    context_answers = ask_context()
    context = format_context_for_ai(context_answers)

    # ── Step 1: Concat ──
    banner("Step 1 · Concat Video / Audio Sources")
    audio_only = False
    audios = []

    if args.no_concat:
        videos = find_videos(video_dir)
        if len(videos) == 1:
            combined_video = videos[0]
            print(f"  Single video: {combined_video}")
        elif os.path.exists(combined_video):
            print(f"  Using existing: {combined_video}")
        else:
            print("  ERROR: no combined.mp4 found and --no-concat was set.")
            sys.exit(1)
    else:
        videos = find_videos(video_dir)
        if not videos:
            audios = find_audios(video_dir)
            if audios:
                audio_only = True
                print(f"  No video files found; {len(audios)} audio file(s) detected — skipping video concat.")
            else:
                print(f"  ERROR: No video or audio files found in {video_dir}")
                sys.exit(1)
        elif len(videos) == 1:
            combined_video = videos[0]
            print(f"  Single file, skipping concat: {combined_video}")
        else:
            concat_videos(videos, combined_video)

    # ── Step 2: Extract audio ──
    banner("Step 2 · Extract Audio")
    if audio_only and not args.no_extract:
        if len(audios) == 1:
            audio_file = audios[0]
            print(f"  Single audio file, using directly: {audio_file}")
        else:
            concat_audios(audios, audio_file)
    elif args.no_extract:
        if not os.path.exists(audio_file):
            print(f"  ERROR: {audio_file} not found and --no-extract was set.")
            sys.exit(1)
        print(f"  Using existing: {audio_file}")
    else:
        extract_audio(combined_video, audio_file)

    # ── Step 3: Transcribe ──
    banner("Step 3 · Transcribe Audio")
    if args.no_transcribe:
        if not os.path.exists(transcript_file):
            print(f"  ERROR: {transcript_file} not found and --no-transcribe was set.")
            sys.exit(1)
        print(f"  Loading existing transcript: {transcript_file}")
        blocks = open(transcript_file).read().split("\n\n")
        transcripts = [(0, b) for b in blocks if b.strip()]
    else:
        chunks = split_audio(audio_file, chunk_dir, args.chunk)
        transcripts = transcribe_all(
            api_key, args.model, chunks, context, source_langs, chunk_dir,
        )

        with open(transcript_file, "w") as f:
            for i, (start, text) in enumerate(transcripts):
                mins, secs = divmod(int(start), 60)
                f.write(f"[Segment {i+1} — {mins:02d}:{secs:02d}]\n{text}\n\n")
        print(f"  ✓ Full transcript saved: {transcript_file}")

        if not args.keep_chunks:
            import shutil
            shutil.rmtree(chunk_dir, ignore_errors=True)
            print("  Cleaned up chunk directory.")

    # ── Step 4: Summarize ──
    banner("Step 4 · Generate Summary")
    print("  Sending transcript to model for summarization...")
    summary = generate_summary(api_key, args.model, transcripts, context, source_langs,
                               summary_lang, timestamps=args.timestamps)

    with open(output_file, "w") as f:
        frontmatter = format_context_frontmatter(context_answers)
        if frontmatter:
            f.write(f"---\n{frontmatter}\n---\n\n")
        f.write("# Recording Summary\n\n")
        f.write(summary)
        f.write(f"\n\n---\n*Generated by recording_notes using {args.model}*\n")

    print(f"  ✓ Summary saved: {output_file}")

    hr("═")
    print("  DONE")
    print(f"  Transcript : {transcript_file}")
    print(f"  Summary    : {output_file}")
    hr("═")
