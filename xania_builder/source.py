"""A lexical index of Xania's C++: function definitions, who calls whom, the command table, the unit tests.

No compiler involved, so it's approximate in known ways: calls are matched by name (an overloaded or same-named
method counts as a call to every definition with that name), and a constructor whose initialiser list uses braces
(``a_{x}``) is missed. Good enough to point a person at the right code; the gate's builds and tests are the proof.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path

KEYWORDS = {
    "if", "for", "while", "switch", "return", "catch", "sizeof", "alignof", "decltype", "static_assert", "do",
    "else", "case", "new", "delete", "throw", "typeid", "noexcept", "requires", "co_return", "co_await", "defined",
    "static_cast", "dynamic_cast", "const_cast", "reinterpret_cast", "operator",
}
_HEADER = re.compile(
    r"(?P<name>~?[A-Za-z_][\w]*(?:::~?[A-Za-z_]\w*)*)\s*\((?P<params>[^()]*(?:\([^()]*\)[^()]*)*)\)\s*"
    r"(?:const\s*)?(?:&{1,2}\s*)?(?:noexcept\s*(?:\([^)]*\))?\s*)?(?:(?:override|final)\s*)*(?:->\s*[^{;]+?)?\s*"
    r"(?::\s*[^{;]*?)?\s*$", re.S)
_SCOPE = re.compile(r"\b(namespace|class|struct|union)\b[^()]*$|\bextern\s*$", re.S)
_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_COMMAND = re.compile(r'add_command\(\s*"([^"]+)"\s*,\s*([\w:]+)\s*(?:,\s*([\w:]+))?')
_STRING = re.compile(r'"((?:[^"\\\n]|\\.)*)"')


def mask(text: str) -> str:
    """The text with comments, string/char literal contents and preprocessor lines blanked (newlines kept), so
    braces and names in them don't count."""
    out = list(text)
    i, n = 0, len(text)
    line_start = True
    while i < n:
        c = text[i]
        if line_start and c == "#":
            j = text.find("\n", i)
            j = n if j < 0 else j
            while j > i and text[j - 1] == "\\" and j < n:  # continued macro lines
                k = text.find("\n", j + 1)
                j = n if k < 0 else k
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
            continue
        if c == "\n":
            line_start = True
            i += 1
            continue
        if not c.isspace():
            line_start = False
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif c in "\"'":
            if c == "'" and i > 0 and (text[i - 1].isalnum()):  # digit separator 1'000
                i += 1
                continue
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            for k in range(i + 1, min(j, n)):
                out[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(out)


@dataclass
class Function:
    name: str  # as written, e.g. "do_get" or "Char::send_line"
    file: str  # relative to the checkout, e.g. "src/act_obj.cpp"
    line: int  # where the name is
    end: int  # the closing brace's line
    signature: str
    calls: set[str] = field(default_factory=set)  # short names called in the body

    @property
    def short(self) -> str:
        return self.name.rsplit("::", 1)[-1]

    @property
    def lines(self) -> int:
        return self.end - self.line + 1

    @property
    def where(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass
class Command:
    name: str
    handler: str
    position: str
    file: str
    line: int


@dataclass
class SourceFile:
    rel: str
    text: str
    code: str
    starts: list[int]  # offset of each line

    def line_of(self, pos: int) -> int:
        return bisect_right(self.starts, pos)

    def lines(self, first: int, last: int) -> str:
        a = self.starts[first - 1]
        b = self.starts[last] if last < len(self.starts) else len(self.text)
        return self.text[a:b]


def _line_starts(text: str) -> list[int]:
    return [0] + [m.end() for m in re.finditer(r"\n", text)]


def _match_brace(code: str, pos: int) -> int:
    depth = 0
    for i in range(pos, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(code) - 1


def functions_in(sf: SourceFile) -> list[Function]:
    code, out = sf.code, []
    boundary, i, scopes = 0, 0, 0
    while i < len(code):
        c = code[i]
        if c in ";":
            boundary = i + 1
        elif c == "}":
            scopes = max(0, scopes - 1)
            boundary = i + 1
        elif c == "{":
            header = code[boundary:i].strip()
            if _SCOPE.search(header):
                scopes += 1
                boundary = i + 1
                i += 1
                continue
            end = _match_brace(code, i)
            m = _HEADER.search(header)
            name = m.group("name") if m else ""
            short = name.rsplit("::", 1)[-1]
            if m and short not in KEYWORDS and not re.search(r"[=,(]\s*$|\breturn\s*$", header[: m.start()]):
                name_pos = boundary + (code[boundary:i].find(header)) + m.start("name")
                body = code[i:end]
                calls = {c for c in _CALL.findall(body) if c not in KEYWORDS}
                sig = " ".join(header.split())
                out.append(Function(name, sf.rel, sf.line_of(name_pos), sf.line_of(end), sig, calls))
            i = end + 1
            boundary = i
            continue
        i += 1
    return out


class Index:
    """Every function definition under src/ (tests apart), the command table, and the unit test files."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.files: dict[str, SourceFile] = {}
        self.functions: list[Function] = []
        self.tests: dict[str, SourceFile] = {}
        self.commands: list[Command] = []
        src = self.root / "src"
        for path in sorted(src.rglob("*")):
            if path.suffix not in (".cpp", ".hpp", ".h", ".cc"):
                continue
            rel = path.relative_to(self.root).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            sf = SourceFile(rel, text, mask(text), _line_starts(text))
            if "/test/" in f"/{path.relative_to(src).as_posix()}" or path.parent.name == "test":
                self.tests[rel] = sf
                continue
            self.files[rel] = sf
            self.functions += functions_in(sf)
            for m in _COMMAND.finditer(text):
                self.commands.append(Command(m.group(1), m.group(2), m.group(3) or "", rel, sf.line_of(m.start())))
        self.by_short: dict[str, list[Function]] = {}
        for f in self.functions:
            self.by_short.setdefault(f.short, []).append(f)

    # lookups
    def find(self, name: str) -> list[Function]:
        """Definitions by short or qualified name."""
        short = name.rsplit("::", 1)[-1]
        return [f for f in self.by_short.get(short, []) if "::" not in name or f.name.endswith(name)]

    def at(self, rel: str, line: int) -> Function | None:
        rel = self.resolve_file(rel) or rel
        hits = [f for f in self.functions if f.file == rel and f.line <= line <= f.end]
        return min(hits, key=lambda f: f.lines) if hits else None

    def resolve_file(self, name: str) -> str | None:
        """'act_obj.cpp' or 'src/act_obj.cpp' -> 'src/act_obj.cpp'."""
        name = name.replace("\\", "/")
        if name in self.files:
            return name
        hits = [r for r in self.files if r.endswith("/" + name)]
        return hits[0] if len(hits) == 1 else None

    def callers(self, fn: Function) -> list[Function]:
        return [f for f in self.functions if fn.short in f.calls and f is not fn]

    def callees(self, fn: Function) -> list[Function]:
        out = []
        for name in sorted(fn.calls):
            out += [f for f in self.by_short.get(name, []) if f is not fn]
        return out

    def commands_for(self, fn: Function) -> list[Command]:
        return [c for c in self.commands if c.handler.rsplit("::", 1)[-1] == fn.short]

    def command(self, name: str) -> list[Command]:
        return [c for c in self.commands if c.name == name]

    def body(self, fn: Function) -> str:
        return self.files[fn.file].lines(fn.line, fn.end)

    def code(self, fn: Function) -> str:
        sf = self.files[fn.file]
        a = sf.starts[fn.line - 1]
        b = sf.starts[fn.end] if fn.end < len(sf.starts) else len(sf.code)
        return sf.code[a:b]

    def strings(self, fn: Function) -> list[str]:
        """String literals in the body: mostly the messages players see."""
        return [m.group(1) for m in _STRING.finditer(self.body(fn))]

    def tests_for(self, rel: str, names: list[str]) -> dict[str, list[str]]:
        """Unit test files for a source file: by name (act_obj.cpp -> act_obj_test.cpp, ActObjTest.cpp) and by
        mention of any of ``names``. {test file: reasons}."""
        stem = Path(rel).stem.lower().replace("_", "")
        out: dict[str, list[str]] = {}
        for t, sf in self.tests.items():
            tstem = Path(t).stem.lower().replace("_", "")
            if tstem in (stem + "test", "test" + stem):
                out.setdefault(t, []).append(f"named after {Path(rel).name}")
            header = Path(rel).with_suffix(".hpp").name
            if re.search(r'#include\s+"(?:\.\./)*' + re.escape(header) + '"', sf.text):
                out.setdefault(t, []).append(f"includes {header}")
            for n in names:
                if re.search(r"\b" + re.escape(n) + r"\b", sf.code):
                    out.setdefault(t, []).append(f"mentions {n}")
        return out
