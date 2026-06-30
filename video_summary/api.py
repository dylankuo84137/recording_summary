"""OpenRouter API: transcription and summarization."""

import os
import re
import base64
import requests

from . import prompts as P

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

# Conversational preamble lines the model sometimes prepends, e.g.
# "好的，這是一份根據您提供的錄音內容撰寫的摘要：" or "Here is the summary:".
_PREAMBLE_PATTERNS = [
    re.compile(r"^(好的|好|這是|這就是|以下是|下面是|為您|為你|根據|附上).*[:：]\s*$"),
    re.compile(r"^(sure|certainly|of course|here\s+is|here's|here are|below is)\b.*[:：]\s*$",
               re.IGNORECASE),
]


def _is_strippable_lead(line):
    s = line.strip()
    if s == "" or s in ("---", "***", "___") or s.startswith("```"):
        return True
    return any(p.match(s) for p in _PREAMBLE_PATTERNS)


def clean_summary(text):
    """Strip conversational preamble/sign-off and stray fences or rules the model adds."""
    lines = text.strip().split("\n")

    while lines and _is_strippable_lead(lines[0]):
        lines.pop(0)

    while lines:
        last = lines[-1].strip()
        if last in ("", "---", "***", "___") or last.startswith("```"):
            lines.pop()
        else:
            break

    return "\n".join(lines).strip()


def call_api(api_key, model, messages, temperature=0.2):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost",
    }
    payload = {"model": model, "messages": messages, "temperature": temperature}
    resp = requests.post(
        f"{DEFAULT_BASE_URL}/chat/completions",
        headers=headers, json=payload, timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def transcribe_chunk(api_key, model, chunk_index, start_sec, filepath, context, source_langs):
    mins, secs = divmod(int(start_sec), 60)
    b64 = base64.b64encode(open(filepath, "rb").read()).decode()

    prompt = P.format_transcribe(
        chunk_index=chunk_index,
        timestamp=f"{mins:02d}:{secs:02d}",
        source_langs=source_langs,
        context=context,
    )

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "input_audio", "input_audio": {"data": b64, "format": "m4a"}},
        ],
    }]
    return call_api(api_key, model, messages)


def transcribe_all(api_key, model, chunks, context, source_langs, chunk_dir):
    transcripts = []
    for chunk_index, start_sec, filepath in chunks:
        cache_file = os.path.join(chunk_dir, f"transcript_{chunk_index:03d}.txt")
        mins, secs = divmod(int(start_sec), 60)

        if os.path.exists(cache_file):
            print(f"  [cached] chunk {chunk_index:02d} ({mins:02d}:{secs:02d})")
            text = open(cache_file).read()
        else:
            print(f"  Transcribing chunk {chunk_index:02d} ({mins:02d}:{secs:02d})...", end=" ", flush=True)
            try:
                text = transcribe_chunk(api_key, model, chunk_index, start_sec, filepath,
                                        context, source_langs)
                open(cache_file, "w").write(text)
                print(f"✓ ({len(text)} chars)")
            except Exception as e:
                print(f"✗ ERROR: {e}")
                text = f"[Transcription failed: {e}]"

        transcripts.append((start_sec, text))
    return transcripts


def generate_summary(api_key, model, transcripts, context, source_langs, summary_lang,
                     timestamps=False):
    full_text = "\n\n".join(
        f"[Segment {i+1} — {int(s//60):02d}:{int(s%60):02d}]\n{t}"
        for i, (s, t) in enumerate(transcripts)
    )
    prompt = P.format_summary(
        transcript=full_text,
        source_langs=source_langs,
        summary_lang=summary_lang,
        context=context,
        timestamps=timestamps,
    )
    messages = [{"role": "user", "content": prompt}]
    return clean_summary(call_api(api_key, model, messages, temperature=0.3))
