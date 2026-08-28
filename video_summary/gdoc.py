"""Convert the Obsidian-flavored summary markdown into Google Docs-friendly markdown.

Google Docs' Markdown import does not understand YAML frontmatter (it shows the
raw ``---`` block as text) and it only styles real Markdown headings (``#``/``##``)
— bold "section titles" stay plain bold. This module:

  * lifts the YAML frontmatter into a visible header (title as ``#`` plus
    bold-labelled metadata lines), and
  * promotes any leftover bold section titles to real headings,

so the converted Google Doc gets a proper title, metadata, and heading outline.

Usage:
    python3 -m video_summary.gdoc input.md > input.gdoc.md
"""

import re
import sys

import yaml

# frontmatter keys that never appear in the rendered metadata block: the title
# becomes the document heading, and gdoc_id is bookkeeping for gdoc_sync
HIDDEN_KEYS = ("title", "gdoc_id")

# frontmatter key -> label shown in the rendered Google Docs metadata block
META_LABELS = [
    ("speaker",  "講者"),
    ("audience", "對象"),
    ("date",     "日期"),
    ("purpose",  "目的"),
    ("notes",    "備註"),
]


def split_frontmatter(md):
    """Return (frontmatter_dict, body) — empty dict if there is no frontmatter."""
    m = re.match(r"^﻿?---\n(.*?)\n---\n+", md, re.DOTALL)
    if not m:
        return {}, md
    data = yaml.safe_load(m.group(1)) or {}
    return data, md[m.end():]


def promote_headings(body):
    """Turn bold section titles into real Markdown headings (idempotent).

    In the Detailed Breakdown, each theme used to be a top-level bullet whose
    only content was bold text, with its detail points nested one level below.
    Promoting that bullet to a ``###`` heading orphans the nested points (a
    4-space indent renders as a code block), so within that section we also
    dedent the detail bullets back up by one level.

    Summaries written since the prompt started asking for real headings already
    give each theme its own ``###``; there a bold bullet is a sub-point, not a
    theme, and promoting it would flatten the outline.
    """
    has_own_themes = re.search(r"^###\s", body, re.MULTILINE) is not None

    out = []
    in_detail = False
    for line in body.split("\n"):
        # Track which top-level section we are in (bold or already a heading).
        if re.match(r"^##\s+", line) or re.match(r"^\*\*\d+\.", line):
            in_detail = "內容詳述" in line or "Detailed Breakdown" in line

        # Top-level numbered section, e.g. "**1. 概述**" -> "## 概述"
        m = re.match(r"^\*\*\d+\.\s*(.+?)\*\*\s*$", line)
        if m:
            out.append(f"## {m.group(1).strip()}")
            continue

        if in_detail and not has_own_themes:
            # Sub-theme: a top-level bullet that is *only* bold text ->
            # "*   **論壇背景與高中校舍願景**" -> "### 論壇背景與高中校舍願景"
            m = re.match(r"^[*-]\s+\*\*(.+?)\*\*\s*$", line)
            if m:
                out.append(f"### {m.group(1).strip()}")
                continue
            # Dedent the now-orphaned nested detail bullets by one level.
            if re.match(r"^\s+[*-]\s+", line):
                out.append(re.sub(r"^    ", "", line))
                continue

        out.append(line)
    return "\n".join(out)


def to_gdoc_markdown(md):
    meta, body = split_frontmatter(md)

    # Drop the generic "# Recording Summary" H1 and the model's repeated bold
    # title line; the document title comes from the frontmatter instead.
    body = re.sub(r"^#\s+Recording Summary\s*\n+", "", body.lstrip())
    # ...but a numbered section title ("**1. 概述**") is a section, not a title.
    body = re.sub(r"^\*\*(?!\d+\.)[^\n]+\*\*\s*\n+", "", body, count=1)
    body = promote_headings(body.strip())

    parts = []
    title = meta.get("title")
    if title:
        parts.append(f"# {title}")
    # Each metadata field on its own line: a trailing two-space hard break keeps
    # them as one tight block (a single newline would collapse into one line on
    # Google Docs import).
    # Follow the frontmatter's own order so the block survives a round trip,
    # and render keys the pipeline does not know about under their own name.
    labels = dict(META_LABELS)
    meta_lines = [f"**{labels.get(key, key)}：** {value}"
                  for key, value in meta.items() if key not in HIDDEN_KEYS and value]
    if meta_lines:
        parts.append("  \n".join(meta_lines))
    parts.append(body)

    return "\n\n".join(parts).strip() + "\n"


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdin"
    with open(src, encoding="utf-8") as f:
        sys.stdout.write(to_gdoc_markdown(f.read()))


if __name__ == "__main__":
    main()
