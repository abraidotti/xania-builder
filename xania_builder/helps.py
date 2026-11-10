"""Help entries from the area files (``#HELPS`` sections): ``<level> <keywords>~`` then the text, ending ``~``."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Help:
    keywords: list[str]  # upper-cased; multi-word keywords kept whole ("MAGIC MISSILE")
    level: int
    text: str
    file: str
    line: int

    @property
    def title(self) -> str:
        return " ".join(k if " " not in k else f"'{k}'" for k in self.keywords)

    def matches(self, word: str) -> bool:
        w = word.upper()
        return any(k == w or (len(w) >= 3 and k.startswith(w) and " " not in k) for k in self.keywords)


def _keywords(s: str) -> list[str]:
    try:
        return [k.upper() for k in shlex.split(s.replace("'", '"'))]
    except ValueError:
        return s.upper().split()


def parse(text: str, file: str = "") -> list[Help]:
    out: list[Help] = []
    m = re.search(r"^#HELPS\s*$", text, re.M)
    if not m:
        return out
    pos = m.end()
    while True:
        h = re.compile(r"\s*(-?\d+)\s+([^~]*)~").match(text, pos)
        if not h:
            break
        level, kw = int(h.group(1)), h.group(2).strip()
        if kw == "$":
            break
        end = text.find("~", h.end())
        if end < 0:
            break
        body = text[h.end():end].lstrip("\n")
        if body.startswith("."):
            body = body[1:]  # a leading '.' keeps leading spaces in Merc help files
        out.append(Help(_keywords(kw), level, body.rstrip(), file, text.count("\n", 0, h.start(2)) + 1))
        pos = end + 1
    return out


def load(root: Path) -> list[Help]:
    out: list[Help] = []
    for path in sorted((Path(root) / "area").glob("*.are")):
        text = path.read_text(encoding="latin-1")
        if "#HELPS" in text:
            out += parse(text, path.relative_to(root).as_posix())
    return out
