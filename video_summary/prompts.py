"""Load and format prompt templates from prompts/*.yaml."""

import os
import yaml

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load(name):
    with open(os.path.join(_PROMPTS_DIR, name)) as f:
        return yaml.safe_load(f)


def format_transcribe(chunk_index, timestamp, source_langs, context=""):
    tpl = _load("transcribe.yaml")
    context_block = f"Recording background:\n{context}\n\n" if context else ""
    lang_list = ", ".join(source_langs) if isinstance(source_langs, list) else source_langs
    return tpl["user_template"].format(
        context_block=context_block,
        chunk_index=chunk_index,
        timestamp=timestamp,
        source_langs=lang_list,
        instructions=tpl["instructions"],
    )


def format_summary(transcript, source_langs, summary_lang, context="", timestamps=False):
    tpl = _load("summary.yaml")
    context_block = f"Recording background:\n{context}\n\n" if context else ""
    lang_list = ", ".join(source_langs) if isinstance(source_langs, list) else source_langs

    section_list = "\n".join(
        f"- {sec['label']}" + (f" — {sec['hint']}" if sec.get("hint") else "")
        for sec in tpl["sections"]
    )

    if "Chinese" in summary_lang or "中文" in summary_lang:
        lang_instruction = f"請用{summary_lang}撰寫摘要。"
    else:
        lang_instruction = f"Write the summary in {summary_lang}."

    if timestamps:
        timestamp_instruction = (
            "In the Detailed Breakdown, annotate the corresponding audio "
            "timestamps (e.g. 00:00–03:00) for each theme."
        )
    else:
        timestamp_instruction = (
            "Do not annotate audio timestamps (e.g. 00:00 or 00:00–03:00) "
            "anywhere in the summary."
        )

    return tpl["user_template"].format(
        context_block=context_block,
        source_langs=lang_list,
        transcript=transcript,
        lang_instruction=lang_instruction,
        section_list=section_list,
        timestamp_instruction=timestamp_instruction,
    )
