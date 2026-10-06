"""FFmpeg pipeline steps: find, concat, extract, split."""

import os
import math
import subprocess

VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".m4v", ".mts", ".ts")
AUDIO_EXTENSIONS = (".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus", ".wma")


# ─── Shell helpers ────────────────────────────────────────────────────────────

def run(cmd, check=True, capture=False):
    result = subprocess.run(cmd, capture_output=capture, text=capture, check=check,
                            stdin=subprocess.DEVNULL)
    return result


def get_duration(filepath):
    result = run(
        ["ffprobe", "-v", "quiet",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1",
         filepath],
        capture=True,
    )
    return float(result.stdout.strip())


def hr(char="─", width=60):
    print(char * width)


def banner(title):
    hr()
    print(f"  {title}")
    hr()


# ─── File discovery ───────────────────────────────────────────────────────────

def find_videos(directory):
    return [
        os.path.join(directory, f)
        for f in sorted(os.listdir(directory))
        if f.lower().endswith(VIDEO_EXTENSIONS)
    ]


def find_audios(directory):
    return [
        os.path.join(directory, f)
        for f in sorted(os.listdir(directory))
        if f.lower().endswith(AUDIO_EXTENSIONS)
    ]


# ─── Concat ───────────────────────────────────────────────────────────────────

def concat_videos(video_files, output_path):
    list_file = output_path + ".filelist.txt"
    with open(list_file, "w") as f:
        for vf in video_files:
            f.write(f"file '{vf}'\n")

    print(f"  Concatenating {len(video_files)} file(s) → {output_path}")
    for i, vf in enumerate(video_files, 1):
        print(f"    [{i}] {os.path.basename(vf)}")

    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", list_file, "-c", "copy", output_path])
    os.remove(list_file)
    print(f"  ✓ Combined video saved: {output_path}")


def concat_audios(audio_files, output_path):
    list_file = output_path + ".filelist.txt"
    with open(list_file, "w") as f:
        for af in audio_files:
            f.write(f"file '{af}'\n")

    print(f"  Concatenating {len(audio_files)} audio file(s) → {output_path}")
    for i, af in enumerate(audio_files, 1):
        print(f"    [{i}] {os.path.basename(af)}")

    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", list_file, "-c:a", "copy", output_path])
    os.remove(list_file)
    print(f"  ✓ Combined audio saved: {output_path}")


# ─── Extract / Split ──────────────────────────────────────────────────────────

def extract_audio(video_path, audio_path):
    print(f"  Extracting audio → {audio_path}")
    run(["ffmpeg", "-y", "-i", video_path, "-vn", "-c:a", "copy", audio_path])
    size_mb = os.path.getsize(audio_path) / 1024 / 1024
    duration = get_duration(audio_path)
    print(f"  ✓ Audio: {size_mb:.1f} MB, {duration/60:.1f} min")


def split_audio(audio_path, chunk_dir, chunk_seconds):
    os.makedirs(chunk_dir, exist_ok=True)
    duration = get_duration(audio_path)
    num_chunks = math.ceil(duration / chunk_seconds)
    print(f"  Duration: {duration:.1f}s → {num_chunks} chunks of {chunk_seconds}s")

    src_ext = os.path.splitext(audio_path)[1].lower()
    # M4A container only supports AAC; use source extension when possible
    chunk_ext = src_ext if src_ext in (".mp3", ".aac", ".flac", ".wav", ".ogg") else ".m4a"

    chunks = []
    for i in range(num_chunks):
        start = i * chunk_seconds
        out = os.path.join(chunk_dir, f"chunk_{i:03d}{chunk_ext}")
        if not os.path.exists(out):
            run(["ffmpeg", "-y", "-i", audio_path,
                 "-ss", str(start), "-t", str(chunk_seconds),
                 "-c:a", "copy", out])
        chunks.append((i, start, out))
        mins, secs = divmod(int(start), 60)
        print(f"    chunk {i:02d}: {mins:02d}:{secs:02d} → {out}")
    return chunks
