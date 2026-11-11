"""``research``: the dossier. Seven sections, each with **facts** (gathered from the source, Explorer and Sim) and
**questions** (judgement calls for whoever writes the change), plus the gate plan ``prototype`` will run.

Every section is gathered in isolation: one that can't run (Explorer missing, no Sim database) says why and the
rest carry on.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import helps as helps_mod
from .idea import Focus, Idea
from .source import Function, Index

SCHEMA = 1

# Idioms: (label, regex, kind). "modern" ones are what newer Xania code reaches for; "legacy" ones are Merc-era C.
IDIOMS = [
    ("ArgParser", r"\bArgParser\b", "modern"),
    ("std::string_view", r"\bstd::string_view\b", "modern"),
    ("fmt::format", r"\bfmt::format\b", "modern"),
    ("matches()/matches_start()", r"\bmatches(?:_start)?\s*\(", "modern"),
    ("range-for over contents", r"for\s*\(\s*(?:const\s+)?auto\s*\*?\s*&?\s*\w+\s*:", "modern"),
    ("act()", r"\bact\s*\(", "either"),
    ("char buffers", r"\bchar\s+\w+\s*\[", "legacy"),
    ("sprintf/strcpy/strcat", r"\b(?:sprintf|snprintf|strcpy|strcat|strncpy)\s*\(", "legacy"),
    ("str_cmp/str_prefix", r"\bstr_(?:cmp|prefix|infix)\s*\(", "legacy"),
    ("'\\0' terminator checks", r"'\\0'", "legacy"),
]
DEBT_MARKS = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b[:\s]*(.*)")
# Functions whose presence in a body means the change reaches persisted data.
DATA_CALLS = {"save_char_obj": "player files", "load_char_obj": "player files", "fread_char": "player files",
              "fwrite_char": "player files", "load_area": "area files", "save_area": "area files",
              "extract_obj": "object lifetimes", "extract_char": "character lifetimes", "obj_to_char": "inventory",
              "obj_from_char": "inventory", "obj_to_room": "room contents", "obj_from_room": "room contents"}


@dataclass
class Section:
    key: str
    title: str
    facts: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    note: str = ""  # why a part couldn't be gathered


@dataclass
class Dossier:
    idea: Idea
    focus: Focus
    commit: str
    dirty: bool
    sections: list[Section] = field(default_factory=list)
    gate: dict = field(default_factory=dict)
    generated: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"schema": SCHEMA, "idea": self.idea.to_dict(), "focus": self.focus.to_dict(), "commit": self.commit,
                "dirty": self.dirty, "generated": self.generated, "gate": self.gate,
                "sections": [asdict(s) for s in self.sections]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=1)

    def markdown(self) -> str:
        i = self.idea
        ref = f" ({i.ref})" if i.ref else ""
        out = [f"# {i.title}{ref}", ""]
        meta = [f"Xania {self.commit[:10] or 'unknown'}" + (" (uncommitted changes)" if self.dirty else ""),
                time.strftime("%Y-%m-%d %H:%M", time.localtime(self.generated))]
        if i.url:
            meta.insert(0, f"[{i.ref}]({i.url})")
        out += [" · ".join(meta), ""]
        if i.text.strip():
            out += ["<details><summary>The idea as given</summary>", "", i.text.strip(), "", "</details>", ""]
        f = self.focus
        out += ["## Focus", ""]
        if f.empty:
            out += ["Nothing in the idea pointed at the code. Rerun with `--symbol`, `--file` or `--command`.", ""]
        for fn in f.functions:
            out.append(f"- `{fn.name}` ({fn.where}, {fn.lines} lines): {f.why.get('function:' + fn.name, '')}")
        for rel in f.files:
            if not any(fn.file == rel for fn in f.functions):
                out.append(f"- `{rel}`")
        if f.commands:
            out.append("- Commands: " + ", ".join(f"`{c}`" for c in f.commands))
        out.append("")
        for n, s in enumerate(self.sections, 1):
            out += [f"## {n}. {s.title}", ""]
            if s.note:
                out += [f"> {s.note}", ""]
            out += [f"- {x}" for x in s.facts] or ["- (nothing found)"]
            if s.questions:
                out += ["", "**To decide**", ""] + [f"- [ ] {q}" for q in s.questions]
            out.append("")
        g = self.gate
        out += ["## Gate plan", "", "What `prototype` runs on the fork before this can ship:", ""]
        out += [f"- Builds: {', '.join(g.get('builds', []))}"]
        out += [f"- Unit tests: {', '.join(f'`{t}`' for t in g.get('unit_tests', [])) or 'the whole suite'}"]
        for t in g.get("sim", []):
            out.append(f"- Sim: `{t['command']}`: {t['why']}")
        for t in g.get("regressions", []):
            out.append(f"- Regression: {t}")
        out.append("")
        return "\n".join(out)


def _fns(fs: list[Function]) -> str:
    return ", ".join(f"`{f.name}` ({f.where})" for f in fs)


def _short(fs: list[Function], limit: int = 12) -> str:
    """Names, one per short name, flagging names with several definitions (lexical matches)."""
    groups: dict[str, list[Function]] = {}
    for f in fs:
        groups.setdefault(f.short, []).append(f)
    items = [f"`{k}`" + (f" ({len(v)} definitions)" if len(v) > 1 else "") for k, v in sorted(groups.items())]
    more = f" and {len(items) - limit} more" if len(items) > limit else ""
    return ", ".join(items[:limit]) + more


# 1. Explorer insights ------------------------------------------------------------------------------------------

def explorer_section(ix: Index, fo: Focus, world) -> Section:
    s = Section("explorer", "Explorer insights")
    if world is None:
        s.note = "Explorer isn't available (see `doctor`), so its bug checks and assessments weren't read."
        return s
    from xania_explorer.bugs import run_checks
    from xania_explorer.systems import SYSTEMS

    names = [f.short for f in fo.functions]
    for r in run_checks(world):
        hits = [o for o in r.detection.occurrences if o.file and (o.file in fo.files or f"src/{o.file}" in fo.files)]
        mention = [n for n in names if re.search(r"\b" + re.escape(n) + r"\b", r.check.explain + r.check.remedy)]
        if hits or mention:
            where = ", ".join(o.where for o in hits[:5]) or "mentions " + ", ".join(f"`{m}`" for m in mention)
            s.facts.append(f"Bug check `{r.check.id}` ({r.status}, {r.check.severity}): {r.check.title}. {where}")
    touched = {Path(f).name for f in fo.files}
    for system in SYSTEMS:
        if not touched & set(system.needs):
            continue
        story = system.story(world)
        s.facts.append(f"The **{system.title}** assessment reads {', '.join(sorted(touched & set(system.needs)))}; "
                       f"a change here can move its numbers ({story.status}).")
        for fd in story.findings:
            if fd.issue and fd.impact >= 2:
                s.facts.append(f"{system.title} finding `{fd.id}` (impact {fd.impact}): {fd.title}")
            for rec in fd.recommendations:
                if rec.kind == "code" and any(Path(f).name in rec.change for f in fo.files):
                    s.facts.append(f"Recommendation `{rec.id}`: {rec.title}")
    if not s.facts:
        s.facts.append("No Explorer bug check, assessment or recommendation touches the focus.")
    if any(f.startswith("Bug check `code.") for f in s.facts):
        s.questions.append("The fix should turn the code check above to `fixed` (it matches the faulty pattern). "
                           "Does it, and are there other occurrences to fix at the same time?")
    elif fo.functions:
        s.questions.append("No Explorer code check covers this. Should one be added for the faulty pattern, so "
                           "other places with it show up and the fix shows as `fixed`?")
    return s


# 2. Architecture ------------------------------------------------------------------------------------------------

def architecture_section(ix: Index, fo: Focus) -> Section:
    s = Section("architecture", "Architecture")
    if fo.stack:
        s.facts.append("Reported call path (innermost first): " + " <- ".join(f"`{n}` ({w})" for n, w in fo.stack))
    for fn in fo.functions:
        callers = ix.callers(fn)
        cmds = ix.commands_for(fn)
        s.facts.append(f"`{fn.name}` is defined at {fn.where}-{fn.end} ({fn.lines} lines): `{fn.signature}`")
        if cmds:
            s.facts.append(f"`{fn.name}` handles the command(s) " + ", ".join(
                f"`{c.name}` (minimum position {c.position.rsplit('::', 1)[-1] or '?'}, {c.file}:{c.line})" for c in cmds))
        if callers:
            s.facts.append(f"Called from {_fns(callers)}" + ("; so it also runs without a player typing it"
                                                             if cmds else ""))
        elif not cmds:
            s.facts.append(f"No caller found for `{fn.short}` in src/ (it may be called through a table or pointer).")
        callees = ix.callees(fn)
        if callees:
            s.facts.append(f"`{fn.short}` calls {_short(callees)}")
        data = sorted({v for k, v in DATA_CALLS.items() if k in fn.calls})
        if data:
            s.facts.append(f"`{fn.short}` reaches persisted or shared state: {', '.join(data)}")
    for rel in fo.files:
        sf = ix.files.get(rel)
        if sf:
            n = sum(1 for f in ix.functions if f.file == rel)
            s.facts.append(f"`{rel}`: {len(sf.starts)} lines, {n} functions")
    s.questions += ["Is the change local to these functions, or does the fix belong in a shared helper their callers "
                    "use too?",
                    "Does every caller (including automatic ones) still get the behaviour it expects?"]
    return s


# 3. Design patterns ------------------------------------------------------------------------------------------

def _idioms(text: str) -> Counter:
    return Counter({label: len(re.findall(rx, text)) for label, rx, _ in IDIOMS})


def patterns_section(ix: Index, fo: Focus) -> Section:
    s = Section("patterns", "Design patterns")
    whole = Counter()
    for sf in ix.files.values():
        whole += _idioms(sf.text)
    kinds = {label: kind for label, _, kind in IDIOMS}
    for fn in fo.functions:
        here = _idioms(ix.body(fn))
        used = [f"{k} x{v} ({kinds[k]})" for k, v in here.items() if v]
        if used:
            s.facts.append(f"In `{fn.short}`: " + ", ".join(used))
        both = [k for k, v in here.items() if v and kinds[k] == "modern"]
        old = [k for k, v in here.items() if v and kinds[k] == "legacy"]
        if both and old:
            s.facts.append(f"`{fn.short}` mixes modern ({', '.join(both)}) and legacy ({', '.join(old)}) idioms: "
                           "the modern ones already in the function are the pattern to follow.")
        helpers = re.findall(r"\bconst\s+auto\s+(\w+)\s*=\s*(matches(?:_start)?\([^;]*\));", ix.body(fn))
        for name, expr in helpers:
            s.facts.append(f"`{fn.short}` already names a test as a value: `{name} = {expr}`")
        same = [f for f in ix.functions if f.signature.split("(", 1)[-1] == fn.signature.split("(", 1)[-1]
                and f is not fn]
        if same and ix.commands_for(fn):
            s.facts.append(f"{len(same)} other functions share the signature `({fn.signature.split('(', 1)[-1]}`; "
                           f"in the same file: {_short([f for f in same if f.file == fn.file], 8) or 'none'}")
    top = ", ".join(f"{k} {v}" for k, v in whole.most_common() if v)
    s.facts.append(f"Across src/: {top}")
    s.questions += ["Which existing idiom does the change follow, and does it leave the function more consistent?",
                    "Is there a helper already (in the same file or a header) that does what the change needs?"]
    return s


# 4. Technical debt -----------------------------------------------------------------------------------------------

GUARD_WINDOW = 15  # lines: an empty() test this close before a [0] counts as its guard


def string_view_hits(ix: Index, fn: Function, guarded: bool = False) -> list[tuple[str, str, int]]:
    """Variables holding string_views (args.shift(), std::string_view) indexed like NUL-terminated C strings:
    (the expression, file, line). Indexing a view at or past its size is undefined behaviour.

    Comments and strings don't count (the masked code is searched). A ``[0]`` with a test of the same view's
    ``empty()`` in the GUARD_WINDOW lines before it is guarded, and left out unless ``guarded``: an empty() check makes
    [0] safe, though not [3] (do_get checks arg1.empty() and still read arg1[3]), and only if it's close (nanny tests
    argument.empty() in one case of its switch but not the others)."""
    code = ix.code(fn)  # masked: comments and string literals blanked, positions kept
    views = set(re.findall(r"\bauto\s+(\w+)\s*=\s*\w+\.shift\(\)", code))
    views |= set(re.findall(r"\bstd::string_view\s+(\w+)", code))
    lines = code.split("\n")
    out = []
    for v in sorted(views):
        for m in re.finditer(r"&?\b" + re.escape(v) + r"\[(\d+)\]", code):
            n = code.count("\n", 0, m.start())
            if m.group(1) == "0" and not guarded:
                before = "\n".join(lines[max(0, n - GUARD_WINDOW):n] + [lines[n][:m.start() - code.rfind("\n", 0, m.start()) - 1]])
                if re.search(r"\b" + re.escape(v) + r"\.empty\(\)", before):
                    continue
            out.append((f"`{m.group(0)}`", fn.file, fn.line + n))
    return sorted(out, key=lambda h: h[2])


def _string_view_as_c_string(ix: Index, fn: Function) -> list[str]:
    return [f"{what} at {rel}:{line}" for what, rel, line in string_view_hits(ix, fn)]


def view_declarations(ix: Index, fn: Function) -> list[tuple[str, str, int]]:
    """Where each string_view a hit indexes was declared: (variable, file, line)."""
    code = ix.code(fn)  # starts at fn.line
    hits = {re.match(r"(\w+)", w.strip("`&")).group(1) for w, _, _ in string_view_hits(ix, fn)}
    out = []
    for v in sorted(hits):
        m = re.search(r"\b(?:auto|std::string_view)\s+&?" + re.escape(v) + r"\b", code)
        if m:
            out.append((v, fn.file, fn.line + code.count("\n", 0, m.start())))
    return out


def flagged_lines(ix: Index, fo: Focus) -> list[tuple[str, str, int]]:
    return [h for fn in fo.functions for h in string_view_hits(ix, fn)]


def debt_section(ix: Index, fo: Focus, world) -> Section:
    s = Section("debt", "Technical debt")
    for fn in fo.functions:
        flags = _string_view_as_c_string(ix, fn)
        if flags:
            s.facts.append(f"`{fn.short}` indexes string_views like C strings (reading past the end when the view "
                           f"is that long, and never seeing a terminator): " + ", ".join(flags))
        if fn.lines > 60:
            s.facts.append(f"`{fn.short}` is {fn.lines} lines long (src/ median "
                           f"{sorted(f.lines for f in ix.functions)[len(ix.functions) // 2]}).")
        legacy = [k for k, v in _idioms(ix.body(fn)).items() if v and dict((a, c) for a, _, c in IDIOMS)[k] == "legacy"]
        if legacy:
            s.facts.append(f"Legacy idioms in `{fn.short}`: {', '.join(legacy)}")
    for rel in fo.files:
        sf = ix.files.get(rel)
        if not sf:
            continue
        marks = [(sf.line_of(m.start()), m.group(1), m.group(2).strip()[:80]) for m in DEBT_MARKS.finditer(sf.text)]
        for line, tag, msg in marks[:8]:
            s.facts.append(f"{tag} at {rel}:{line}: {msg}")
        if len(marks) > 8:
            s.facts.append(f"... and {len(marks) - 8} more TODO/FIXME marks in `{rel}`")
    if any(string_view_hits(ix, fn) for fn in fo.functions):
        names = {fn.name for fn in fo.functions}
        others = [(fn, hits) for fn in ix.functions if fn.name not in names and (hits := string_view_hits(ix, fn))]
        if others:
            s.facts.append(f"The same pattern elsewhere in src/ ({sum(len(h) for _, h in others)} places in "
                           f"{len(others)} functions; each is the same kind of bug unless the view is known to be "
                           "long enough): " + "; ".join(f"`{fn.short}` " + ", ".join(f"{w} :{ln}" for w, _, ln in h)
                                                         for fn, h in others[:10]))
        else:
            s.facts.append("Nowhere else in src/ indexes a string_view this way: fixing the focus clears the pattern.")
    if not s.facts:
        s.facts.append("No debt markers found in the focus.")
    s.questions += ["Are the other places with the same pattern the same bug, and do they belong in this change?",
                    "What debt does the change pay down while it's here, and what does it deliberately leave?",
                    "Does the change add any (a special case, a duplicated check, a new legacy idiom)?"]
    return s


# 5. Gameplay ----------------------------------------------------------------------------------------------------

def gameplay_section(ix: Index, fo: Focus, world) -> Section:
    s = Section("gameplay", "Gameplay")
    for c in fo.commands:
        for cmd in ix.command(c):
            pos = cmd.position.rsplit("::", 1)[-1] or "any"
            s.facts.append(f"Players reach this with `{c}` (from position {pos} up).")
    for fn in fo.functions:
        auto = [f for f in ix.callers(fn) if not ix.commands_for(f)]
        if auto and ix.commands_for(fn):
            s.facts.append(f"`{fn.short}` also runs on its own from {_fns(auto)}: players who never type the command "
                           "are affected too (e.g. through an auto setting).")
        msgs = [m for m in ix.strings(fn) if re.search(r"[A-Za-z]{3,}", m) and " " in m]
        if msgs:
            s.facts.append(f"Messages `{fn.short}` can show: " + "; ".join(f'"{m}"' for m in msgs[:10])
                           + (f" (+{len(msgs) - 10})" if len(msgs) > 10 else ""))
    if world is not None:
        from xania_explorer.systems import SYSTEMS

        touched = {Path(f).name for f in fo.files}
        moved = [sy.title for sy in SYSTEMS if touched & set(sy.needs)]
        s.facts.append("Balance numbers Explorer models from these files: " + (", ".join(moved) if moved else
                       "none (the change is behaviour, not balance; Explorer's predictions shouldn't move)"))
    s.questions += ["What does a player notice before and after (messages, what they get, what's refused)?",
                    "Can a careless or abusive player use the change (or the old behaviour) to their advantage?",
                    "Does it change balance for any class, race or level range? If so, which Explorer numbers?"]
    return s


# 6. Documentation -------------------------------------------------------------------------------------------------

def docs_section(ix: Index, fo: Focus, helps: list) -> Section:
    s = Section("docs", "Documentation")
    words = list(fo.commands)
    for c in fo.commands:
        for h in helps:
            if h.matches(c):
                first = h.text.strip().splitlines()[0][:100] if h.text.strip() else ""
                entry = f"Help `{h.title}` ({h.file}:{h.line}, level {h.level}): {first}"
                if entry not in s.facts:
                    s.facts.append(entry)
    for short in dict.fromkeys(fn.short for fn in fo.functions):
        mentioned = [h for h in helps if re.search(r"\b" + re.escape(short) + r"\b", h.text)]
        for h in mentioned[:3]:
            s.facts.append(f"Help `{h.title}` mentions `{short}` ({h.file}:{h.line})")
    docs = [p for p in ix.root.glob("*.md")] + list((ix.root / "docs").rglob("*.md"))
    for p in docs:
        text = p.read_text(encoding="utf-8", errors="replace")
        hit = [w for w in words + [f.short for f in fo.functions] if re.search(r"`" + re.escape(w) + r"\b", text)]
        if hit:
            s.facts.append(f"`{p.relative_to(ix.root).as_posix()}` mentions {', '.join(f'`{w}`' for w in hit)}")
    if fo.commands and not any(f.startswith("Help") for f in s.facts):
        s.facts.append("No help entry covers " + ", ".join(f"`{c}`" for c in fo.commands) + ".")
    if not s.facts:
        s.facts.append("No help entries or docs mention the focus.")
    s.questions += ["Does any help entry describe the behaviour being changed, and does it need rewording?",
                    "Does the change need a note anywhere else (README, release notes, an issue comment)?"]
    return s


# 7. Tests -------------------------------------------------------------------------------------------------------

def _sim_findings(cfg, names: list[str]) -> list[dict]:
    db = cfg.sim_repo / "state" / "lore.db" if cfg.sim_repo else None
    if not db or not db.exists():
        return []
    out = []
    with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        for r in con.execute("SELECT signature, title, status, link, count, kind, repro FROM findings"):
            if any(re.search(r"\b" + re.escape(n) + r"\b", f"{r['signature']} {r['title']} {r['repro']}") for n in names):
                out.append(dict(r))
    return out


def _sim_mentions(cfg, words: list[str]) -> dict[str, list[str]]:
    """Sim scenarios and modules that send these commands ("get all corpse", ...): {path: [words]}."""
    if not cfg.sim_repo or not cfg.sim_repo.exists():
        return {}
    out: dict[str, list[str]] = {}
    pkg = cfg.sim_repo / "xania_sim"
    players = [p for sub in ("activities", "players", "trials") for p in (pkg / sub).rglob("*.py")]
    for p in sorted(list((cfg.sim_repo / "scenarios").glob("test_*.py")) + players):
        text = p.read_text(encoding="utf-8", errors="replace")
        hit = [w for w in words if re.search(r"[\"'(]" + re.escape(w) + r"\b", text)]
        if hit:
            out[p.relative_to(cfg.sim_repo).as_posix()] = hit
    return out


def tests_section(ix: Index, fo: Focus, cfg) -> tuple[Section, dict]:
    s = Section("tests", "Test coverage")
    names = [f.short for f in fo.functions]
    unit: list[str] = []
    # One line per test file, with every reason it's relevant (several focus files often share the same tests).
    reasons: dict[str, list[str]] = {}
    for rel in fo.files:
        found = ix.tests_for(rel, names)
        for t, why in found.items():
            reasons.setdefault(t, []).extend(why)
        if not found:
            s.facts.append(f"No unit test file for `{rel}`.")
    for t, why in sorted(reasons.items()):
        s.facts.append(f"`{t}`: {', '.join(dict.fromkeys(why))}")
        unit.append(t)
    for fn in fo.functions:
        if not any(re.search(r"\b" + re.escape(fn.short) + r"\b", sf.code) for sf in ix.tests.values()):
            s.facts.append(f"No unit test calls `{fn.short}`.")
    sims = _sim_mentions(cfg, fo.commands)
    for path, w in sims.items():
        s.facts.append(f"Sim `{path}` sends {', '.join(f'`{x}`' for x in w)}")
    found = _sim_findings(cfg, names)
    for f in found:
        link = f" ({f['link']})" if f["link"] else ""
        s.facts.append(f"Sim finding `{f['signature']}` [{f['status']}, seen {f['count']}x]: {f['title']}{link}")
    if cfg.sim_repo and not (cfg.sim_repo / "state" / "lore.db").exists():
        s.note = "Sim's lore database isn't there, so Sim's findings weren't checked."
    s.questions += ["Which unit test pins the fixed behaviour (a test that fails before the change)?",
                    "Which Sim trial or scenario shows it from a player's side, and should a new one be added?"]
    gate = gate_plan(ix, fo, unit, sims, found)
    return s, gate


def gate_plan(ix: Index, fo: Focus, unit: list[str], sims: dict, findings: list[dict]) -> dict:
    sim = [{"command": "smoke", "why": "the game still boots and a player can log in"}]
    files = {Path(f).name for f in fo.files}
    callers = {Path(c.file).name for fn in fo.functions for c in ix.callers(fn)}
    if "fight.cpp" in files | callers:
        sim.append({"command": "hunt --minutes 5", "why": "fights and what runs after a kill (autoloot) reach it"})
    lifetimes = {"extract_char", "do_quit", "close_socket", "char_update", "reap_closed", "nanny"}
    if any(fn.short in lifetimes or fn.calls & lifetimes for fn in fo.functions) or files & {"comm.cpp", "Descriptor.cpp"}:
        sim.append({"command": "churn --minutes 5", "why": "logins and quits reach it (lifetime bugs show here)"})
    for fn in fo.functions:
        m = re.fullmatch(r"spell_(\w+)", fn.short)
        if m:
            sim.append({"command": f"skill \"{m.group(1).replace('_', ' ')}\"", "why": f"`{fn.short}` is a spell"})
    for path in sims:
        if path.startswith("scenarios/"):
            sim.append({"command": f"pytest {path}", "why": "it sends the commands involved"})
    regressions = [f"Sim finding `{f['signature']}` should stop reproducing" + (f" ({f['link']})" if f["link"] else "")
                   for f in findings if f["status"] != "ignored"]
    return {"builds": ["Debug (ASan, UBSan, LSan, libstdc++ assertions)", "Release (-O2)"], "unit_tests": sorted(set(unit)), "sim": sim, "regressions": regressions}


# ---------------------------------------------------------------------------------------------------------------

def build(idea: Idea, fo: Focus, ix: Index, cfg, world=None, at: str = "") -> Dossier:
    commit, dirty = (at, False) if at else cfg.commit()
    d = Dossier(idea, fo, commit, dirty)
    helps = helps_mod.load(ix.root)

    def guarded(key: str, title: str, fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - one section failing mustn't lose the rest
            return Section(key, title, note=f"Couldn't gather this section: {type(e).__name__}: {e}")

    d.sections.append(guarded("explorer", "Explorer insights", lambda: explorer_section(ix, fo, world)))
    d.sections.append(guarded("architecture", "Architecture", lambda: architecture_section(ix, fo)))
    d.sections.append(guarded("patterns", "Design patterns", lambda: patterns_section(ix, fo)))
    d.sections.append(guarded("debt", "Technical debt", lambda: debt_section(ix, fo, world)))
    d.sections.append(guarded("gameplay", "Gameplay", lambda: gameplay_section(ix, fo, world)))
    d.sections.append(guarded("docs", "Documentation", lambda: docs_section(ix, fo, helps)))
    try:
        tests, d.gate = tests_section(ix, fo, cfg)
    except Exception as e:  # noqa: BLE001
        tests = Section("tests", "Test coverage", note=f"Couldn't gather this section: {type(e).__name__}: {e}")
        d.gate = gate_plan(ix, fo, [], {}, [])
    d.sections.append(tests)
    from .history import history_section

    d.sections.append(guarded("history", "History",
                              lambda: history_section(ix, fo, flagged_lines(ix, fo), cfg.upstream,
                                                      [d for fn in fo.functions for d in view_declarations(ix, fn)])))
    return d


def write(d: Dossier, out_dir: Path) -> Path:
    folder = Path(out_dir) / d.idea.slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "dossier.md").write_text(d.markdown(), encoding="utf-8")
    (folder / "dossier.json").write_text(d.to_json(), encoding="utf-8")
    return folder
