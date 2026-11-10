"""What a dossier is about: an idea, from a fork issue, an Explorer bug check or free text, and its focus in the code.

The focus is gathered from the idea's text plus explicit hints: ``file.cpp:123`` references (the function around
that line), names that are functions in the source, and commands in backticks or quotes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field

from .source import Function, Index

_FILE_LINE = re.compile(r"\b((?:src/)?[\w/]+\.(?:cpp|hpp|h)):(\d+)")
_FILE = re.compile(r"\b((?:src/)?[\w/]+\.(?:cpp|hpp|h))\b")
# A function named on its own in backticks: `do_get`, `Char::send_line`, `get_obj()`.
_TICKED = re.compile(r"`(~?[A-Za-z_]\w*(?:::~?[A-Za-z_]\w*)*)(?:\(\))?`")
_QUOTED = re.compile(r"`([a-z][^`\n]{0,40})`|'([a-z][a-z .]{1,30})'|\"([a-z][a-z .]{1,30})\"")
_FENCE = re.compile(r"^```.*?^```[^\n]*$", re.M | re.S)
# gdb/ASan frames: "#7  do_get (ch=...) at src/act_obj.cpp:707", "#3 0x55 in do_get /x/src/act_obj.cpp:707:9"
_FRAME = re.compile(r"^\s*#(\d+)\s+(?:0x[0-9a-f]+ in )?([~\w:<>]+).*?(?:\bat )?((?:/\S*/)?src/[\w/]+\.(?:cpp|hpp|h)):(\d+)",
                    re.M)


def split_text(text: str) -> tuple[str, list[str]]:
    """(the prose, the fenced code blocks). Code blocks are evidence (backtraces, suggested patches), not focus."""
    return _FENCE.sub("", text), _FENCE.findall(text)


class IdeaError(Exception):
    pass


@dataclass
class Idea:
    kind: str  # issue | bug | text
    ref: str  # "#1", "code.do_get_all", or "" for text
    title: str
    text: str
    url: str = ""
    labels: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        head = {"issue": f"issue-{self.ref.lstrip('#')}", "bug": f"bug-{self.ref}"}.get(self.kind, "")
        words = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        words = "-".join(words.split("-")[:6])
        return "-".join(p for p in (head, words) if p) or "idea"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Focus:
    functions: list[Function] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    lines: list[tuple[str, int]] = field(default_factory=list)  # file:line references in the idea
    stack: list[tuple[str, str]] = field(default_factory=list)  # a reported call path: (function, file:line)
    why: dict[str, str] = field(default_factory=dict)  # "function:do_get" -> how it was found

    @property
    def empty(self) -> bool:
        return not (self.functions or self.files or self.commands)

    def to_dict(self) -> dict:
        return {"functions": [{"name": f.name, "where": f.where, "lines": f.lines} for f in self.functions],
                "files": self.files, "commands": self.commands,
                "lines": [f"{f}:{n}" for f, n in self.lines], "stack": [list(s) for s in self.stack],
                "why": self.why}


def from_issue(number: str, repo: str) -> Idea:
    if not shutil.which("gh"):
        raise IdeaError("reading an issue needs the GitHub CLI (gh); pass the idea as text instead")
    r = subprocess.run(["gh", "issue", "view", number.lstrip("#"), "-R", repo, "--json", "title,body,url,labels"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    if r.returncode:
        raise IdeaError(f"gh couldn't read {repo}#{number.lstrip('#')}: {r.stderr.strip()}")
    d = json.loads(r.stdout)
    return Idea("issue", "#" + number.lstrip("#"), d["title"], d.get("body") or "", d.get("url", ""),
                [lab["name"] for lab in d.get("labels", [])])


def from_bug(check_id: str, world) -> Idea:
    from xania_explorer.bugs import run_checks

    for r in run_checks(world):
        if r.check.id == check_id or r.check.id.endswith("." + check_id):
            occ = "\n".join(f"- {o.where}: {o.detail}" for o in r.detection.occurrences[:20])
            text = f"{r.check.explain}\n\nStatus: {r.status}\n{occ}\n\nRemedy:\n{r.check.remedy}"
            return Idea("bug", r.check.id, r.check.title, text)
    raise IdeaError(f"Explorer has no bug check {check_id!r}")


def resolve(arg: str, cfg, world_loader=None) -> Idea:
    if re.fullmatch(r"#?\d+", arg.strip()):
        return from_issue(arg.strip(), cfg.fork)
    if arg.startswith("bug:"):
        if world_loader is None:
            raise IdeaError("an Explorer bug check needs Explorer")
        return from_bug(arg[4:], world_loader())
    first = arg.strip().splitlines()[0] if arg.strip() else "idea"
    return Idea("text", "", first[:100], arg)


def focus(idea: Idea, index: Index, symbols=(), files=(), commands=()) -> Focus:
    fo = Focus()
    prose, blocks = split_text(f"{idea.title}\n{idea.text}")

    def add_fn(fn: Function, why: str) -> None:
        if fn not in fo.functions:
            fo.functions.append(fn)
            fo.why[f"function:{fn.name}"] = why
        if fn.file not in fo.files:
            fo.files.append(fn.file)

    for s in symbols:
        for fn in index.find(s):
            add_fn(fn, "named with --symbol")
    for f, n in _FILE_LINE.findall(prose):
        rel = index.resolve_file(f)
        if rel:
            fo.lines.append((rel, int(n)))
            fn = index.at(rel, int(n))
            if fn:
                add_fn(fn, f"{f}:{n} is in it")
    for name in dict.fromkeys(_TICKED.findall(prose)):
        if "_" not in name and "::" not in name:  # `all`, `get`: words more often than functions
            continue
        hits = index.find(name)
        if hits and len(hits) <= 3:  # several same-named definitions: too ambiguous to mean one
            for fn in hits:
                add_fn(fn, "named in the idea")
    for block in blocks:  # a backtrace: the innermost frame in our source is focus, the rest is the call path
        frames = sorted(((int(n), name, f, int(line)) for n, name, f, line in _FRAME.findall(block)))
        first = True
        for _, name, f, line in frames:
            rel = index.resolve_file(f.split("/src/", 1)[-1] if "/src/" in f else f.removeprefix("src/"))
            fn = index.at(rel, line) if rel else None
            if not fn:
                continue
            if (fn.name, f"{rel}:{line}") not in fo.stack:
                fo.stack.append((fn.name, f"{rel}:{line}"))
            if first:
                add_fn(fn, f"innermost frame of a reported backtrace ({rel}:{line})")
                first = False
    for f in list(files) + _FILE.findall(prose):
        rel = index.resolve_file(f)
        if rel and rel not in fo.files:
            fo.files.append(rel)
            fo.why[f"file:{rel}"] = "named" if f in files else "named in the idea"
    names = {c.name for c in index.commands if re.fullmatch(r"[a-z]{2,}", c.name)}
    wanted = list(commands)
    for m in _QUOTED.finditer(prose):
        phrase = next(g for g in m.groups() if g)
        word = re.split(r"[\s.]", phrase, maxsplit=1)[0].lower()
        if word in names:
            wanted.append(word)
    for fn in fo.functions:
        wanted += [c.name for c in index.commands_for(fn)]
    for c in wanted:
        if c not in fo.commands and c in names:
            fo.commands.append(c)
            for cmd in index.command(c):
                for fn in index.find(cmd.handler):
                    if fn not in fo.functions and c in commands:
                        add_fn(fn, f"handles the {c!r} command")
    return fo
