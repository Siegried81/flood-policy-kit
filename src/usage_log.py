"""Reading and writing `docs/ai_usage_log.md` - Annex A of the brief.

Two small operations that both exist because this one file has **two readers**
with different capabilities, and code that treats it as a plain Markdown blob
gets each of them wrong:

- In the repository it is a document with a table and closing prose, and its
  relative links to its sibling docs are correct.
- Served by the Streamlit app it is a rendered string on an HTTP origin that has
  no `.md` files behind it, and the table is something a form appends to while
  the app is running.

They live here rather than in `app/streamlit_app.py` so a test can exercise them
without executing the app: importing the script runs the whole page, which reads
the real `data/processed/` tables - green on this machine and red on a runner
that has no `data/`.
"""

from __future__ import annotations

import re
from pathlib import Path

#: `[text](something.md)` and `[text](../docs/something.md#anchor)`, but never an
#: `http(s)` target, which a reader with a network can follow.
_RELATIVE_DOC_LINK = re.compile(r"\[([^\]]+)\]\((?!https?:)[^)]*\.md[^)]*\)")


def append_row(path: Path, row: str) -> None:
    """Insert `row` after the LAST table row, not at the end of the file.

    The log ends with prose - the closing section naming what the AI was not
    allowed to decide - so appending to the file put the new entry below it,
    outside the table, where Markdown renders it as a paragraph of text with
    pipe characters in it rather than as a row of the log.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    last = max(
        (i for i, line in enumerate(lines) if line.lstrip().startswith("|")),
        default=len(lines) - 1,
    )
    if not lines[last].endswith("\n"):
        lines[last] += "\n"
    lines.insert(last + 1, row)
    path.write_text("".join(lines), encoding="utf-8")


def unlink_relative_docs(text: str) -> str:
    """Drop Markdown links whose target is a sibling `.md` file, keeping the text.

    In the repository `[`docs/decisions.md`](decisions.md)` is right. Served by
    Streamlit the same link resolves against the app's own origin, and the dev
    server answers an unknown path with the app shell - so clicking it opened a
    second copy of the whole app in a new tab. Rewriting the targets to absolute
    GitHub URLs is not the fix either: the kit has to work with the Wi-Fi off,
    and a dead link is not better than no link. The link text in this log already
    names the file, so dropping the link loses nothing a reader needs.
    """
    return _RELATIVE_DOC_LINK.sub(r"\1", text)
