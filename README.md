# video_summary

An end-to-end pipeline for transcribing and summarizing video/audio recordings using AI via the OpenRouter API.

## Features

- Concatenates multiple video or audio files into a single source
- Extracts audio from video files using FFmpeg
- Splits audio into manageable chunks for transcription
- Transcribes each chunk with multilingual support (default: English + Traditional Chinese)
- Generates a structured bilingual markdown summary

## Requirements

**Python dependencies:**

```bash
pip install -r requirements.txt
```

**System dependency** (must be installed separately):

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
apt install ffmpeg
```

## Setup

Set your OpenRouter API key as an environment variable, or place it in a `.env` file:

```bash
export OPENROUTER_API_KEY=your_key_here
```

Or create a `.env` file in the project root or current directory:

```
OPENROUTER_API_KEY=your_key_here
```

## Usage

```bash
python video_to_summary.py [video_dir] [options]
```

`video_dir` is the directory containing your video or audio files. Defaults to the current directory.

When run, the pipeline will interactively prompt you for recording context (title, speaker, audience, etc.) to improve transcription and summary quality.

### Examples

```bash
# Summarize videos in current directory
python video_to_summary.py

# Summarize videos in a specific directory
python video_to_summary.py /path/to/recordings

# Use a specific model and output language
python video_to_summary.py /path/to/recordings --model google/gemini-2.5-pro --summary-lang English

# Resume from existing transcript (skip transcription step)
python video_to_summary.py /path/to/recordings --no-transcribe
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `video_dir` | `.` | Directory containing video/audio source files |
| `--api-key` | env var | OpenRouter API key (or use `OPENROUTER_API_KEY`) |
| `--model` | `google/gemini-2.5-flash` | OpenRouter model to use |
| `--chunk` | `600` | Audio chunk size in seconds |
| `--source-lang` | `English,Traditional Chinese` | Languages spoken in the audio |
| `--summary-lang` | `Traditional Chinese` | Output language for the summary |
| `--output` | `summary.md` | Output filename for the summary |
| `--work-dir` | `video_dir` | Working directory for intermediate files |
| `--keep-chunks` | off | Keep intermediate audio chunk files after completion |
| `--no-concat` | off | Skip concat step; use existing `combined.mp4` |
| `--no-extract` | off | Skip audio extraction; use existing `audio.m4a` |
| `--no-transcribe` | off | Skip transcription; use existing `full_transcript.txt` |

### Supported Formats

**Video:** `.mp4`, `.mov`, `.mkv`, `.avi`, `.m4v`, `.mts`, `.ts`

**Audio:** `.m4a`, `.mp3`, `.wav`, `.aac`, `.flac`, `.ogg`, `.opus`, `.wma`

## Project Structure

```
video_summary/
├── video_to_summary.py       # Entry point
├── requirements.txt
├── .gitignore
└── video_summary/            # Main package
    ├── __init__.py
    ├── cli.py                # CLI argument parsing and pipeline orchestration
    ├── pipeline.py           # FFmpeg-based media processing
    ├── api.py                # OpenRouter API client
    ├── prompts.py            # Prompt template loader
    └── prompts/
        ├── transcribe.yaml   # Transcription prompt template
        └── summary.yaml      # Summary structure template
```

## Pipeline Steps

1. **Concat** — Merges all source files into `combined.mp4`
2. **Extract** — Pulls audio into `audio.m4a` via FFmpeg
3. **Split** — Divides audio into `audio_chunks/chunk_NNN.m4a` files
4. **Transcribe** — Sends each chunk to the API; caches results as `transcript_NNN.txt`
5. **Merge** — Combines chunk transcripts into `full_transcript.txt`
6. **Summarize** — Sends full transcript + context to API; writes `summary.md`

Intermediate files are stored in the working directory. Audio chunks are deleted after transcription by default (use `--keep-chunks` to retain them). Use `--no-concat`, `--no-extract`, or `--no-transcribe` to resume a pipeline from a checkpoint.

## Summary Output Format

The generated `summary.md` follows a structured bilingual (Chinese/English) template:

1. **概述 / Overview** — 2–3 sentence summary
2. **核心觀點 / Key Points** — Bulleted list of main ideas
3. **內容詳述 / Detailed Breakdown** — Organized by theme or time segment
4. **重要引言或案例 / Notable Quotes/Examples** — Key quotes or examples, if any
5. **行動建議與結論 / Action Items/Takeaways** — Concrete next steps or conclusions
