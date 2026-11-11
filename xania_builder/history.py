"""Section 8, History: when the code in focus got the way it is, what changed around it since, and what upstream
already knows. All of it comes from git and (for upstream) the GitHub CLI, read-only.

The questions it answers for a reviewer: *when did this start, why did nobody notice, and has anyone tried before?*
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# Files whose changes alter how the code is compiled or checked, rather than what it does.
TOOLCHAIN = ["CMakeLists.txt", "Makefile", "conanfile.txt", ".github/workflows", "toolchain", "docker-dev"]


@dataclass
class Commit:
    sha: str
    author: str
    date: str  # YYYY-MM-DD
    subject: str

    def short(self) -> str:
        return f"`{self.sha[:7]}` ({self.date}, {self.author}): {self.subject}"


def git(root: Path, *args: str, timeout: int = 60) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args[:2])}: {r.stderr.strip()[:200]}")
    return r.stdout


def blame(root: Path, rel: str, first: int, last: int, ref: str = "HEAD") -> list[tuple[int, Commit]]:
    """(line, the commit that last changed it) for each line in first..last."""
    # -C -C -M -w: follow code moved or copied between files (nanny moved from comm.cpp to MudImpl.cpp, say) and
    # ignore whitespace-only changes, so lines are credited to the commit that wrote them, not one that moved them.
    out = git(root, "blame", "--porcelain", "-C", "-C", "-M", "-w", "-L", f"{first},{last}", ref, "--", rel)
    commits: dict[str, Commit] = {}
    rows: list[tuple[int, Commit]] = []
    sha = ""
    line = 0
    info: dict[str, str] = {}
    for ln in out.splitlines():
        m = re.match(r"^([0-9a-f]{40}) \d+ (\d+)", ln)
        if m:
            sha, line = m.group(1), int(m.group(2))
            info = {}
            continue
        if ln.startswith("\t"):
            if sha not in commits:
                commits[sha] = Commit(sha, info.get("author", "?"), info.get("date", "?"), info.get("summary", ""))
            rows.append((line, commits[sha]))
            continue
        key, _, val = ln.partition(" ")
        if key == "author":
            info["author"] = val
        elif key == "author-time":
            info["date"] = time.strftime("%Y-%m-%d", time.gmtime(int(val)))
        elif key == "summary":
            info["summary"] = val
    return rows


def log(root: Path, *args: str) -> list[Commit]:
    out = git(root, "log", "--format=%H%x1f%an%x1f%ad%x1f%s", "--date=short", *args)
    return [Commit(*ln.split("\x1f", 3)) for ln in out.splitlines() if ln.count("\x1f") == 3]


def build_modes(root: Path) -> list[str]:
    """What Debug and Release builds turn on, from the top CMakeLists.txt."""
    cm = root / "CMakeLists.txt"
    if not cm.exists():
        return []
    text = cm.read_text(encoding="utf-8", errors="replace")
    out = []
    for mode in ("DEBUG", "RELEASE"):
        m = re.search(r'set\(CMAKE_CXX_FLAGS_' + mode + r'\s+"([^"]*)"\)', text)
        if m:
            flags = m.group(1).replace("${CMAKE_CXX_FLAGS_" + mode + "}", "").split()
            out.append(f"{mode.title()} builds add `{' '.join(flags)}`")
    return out


def upstream_mentions(repo: str, words: list[str], limit: int = 5) -> list[dict]:
    """Issues and PRs on the upstream repo that mention any of these words (read-only GitHub search)."""
    if not repo or not shutil.which("gh") or not words:
        return []
    seen: dict[int, dict] = {}
    for w in words:
        r = subprocess.run(["gh", "search", "issues", w, "--repo", repo, "--include-prs", "--limit", str(limit),
                            "--json", "number,title,state,url,isPullRequest"], capture_output=True, text=True,
                           timeout=60, encoding="utf-8", errors="replace")
        if r.returncode:
            continue
        for item in json.loads(r.stdout or "[]"):
            seen.setdefault(item["number"], {**item, "words": []})["words"].append(w)
    return sorted(seen.values(), key=lambda i: -i["number"])


VIEW_CONVERSION = re.compile(r"string_view|ArgParser", re.I)
# Commits whose diff changes the compiler, its version or its flags.
COMPILER_CHANGE = r"g\+\+-[0-9]+|gcc_version|gcc-[0-9]+|clang-[0-9]+|-fsanitize|CMAKE_CXX_FLAGS|CMAKE_CXX_STANDARD"


def history_section(ix, fo, flagged: list[tuple[str, str, int]], upstream: str,
                    declarations: list[tuple[str, str, int]] = (), ref: str = "HEAD"):
    """flagged: (what, file, line) from the debt detectors: the lines a fix is likely to touch.
    declarations: (variable, file, line) where the variables those lines index were declared."""
    from .research import Section

    s = Section("history", "History")
    root = ix.root
    try:
        git(root, "rev-parse", "--git-dir")
    except (RuntimeError, OSError) as e:
        s.note = f"Not a git checkout, so no history: {e}"
        return s
    oldest: Commit | None = None
    candidates: dict[str, Commit] = {}  # commits that wrote a declaration or a flagged line
    for var, rel, line in declarations:
        rows = blame(root, rel, line, line, ref)
        if rows:
            c = rows[0][1]
            candidates[c.sha] = c
            s.facts.append(f"`{var}` is declared at {rel}:{line}, a line last changed in {c.short()}")
    for what, rel, line in flagged:
        rows = blame(root, rel, line, line, ref)
        if rows:
            c = rows[0][1]
            candidates[c.sha] = c
            s.facts.append(f"{what} at {rel}:{line} was last changed in {c.short()}")
            if oldest is None or c.date < oldest.date:
                oldest = c
    # Of those, the ones that say they moved the code to string_view: when the C-string indexing started being on a
    # view, so the likely start of the bug.
    moved = sorted((c for c in candidates.values()
                    if VIEW_CONVERSION.search(git(root, "log", "-1", "--format=%B", c.sha))), key=lambda c: c.date)
    for c in moved:
        s.facts.append(f"The conversion to string_view (or ArgParser): {c.short()}. The indexing above has been on a "
                       "view, with no terminator, since then")
    oldest = moved[0] if moved else oldest
    for fn in fo.functions:
        rows = blame(root, fn.file, fn.line, fn.end, ref)
        by = Counter(c.sha for _, c in rows)
        commits = {c.sha: c for _, c in rows}
        top = [f"{commits[sha].short()} ({n} lines)" for sha, n in by.most_common(4)]
        s.facts.append(f"`{fn.short}` ({fn.lines} lines) comes from {len(by)} commits; the most: " + "; ".join(top))
    if oldest is not None:
        later = log(root, "-G", COMPILER_CHANGE, f"{oldest.sha}..{ref}", "--", *TOOLCHAIN)
        if later:
            s.facts.append(f"Since {oldest.sha[:7]} ({oldest.date}), {len(later)} commits changed the compiler or "
                           "its flags; the latest: " + "; ".join(c.short() for c in later[:5]))
    s.facts += build_modes(root)
    # Function names only: command words like "get" match half the tracker. And only the functions the change is about
    # (those with flagged lines, else the first two): a reported call path adds interpret() and game_loop(), which
    # every crash goes through.
    flagged_fns = [fn.short for fn in fo.functions if any(r == fn.file and fn.line <= ln <= fn.end
                                                           for _, r, ln in flagged)]
    words = list(dict.fromkeys(flagged_fns or [fn.short for fn in fo.functions][:2]))[:4]
    hits = upstream_mentions(upstream, words)
    for h in hits[:8]:
        kind = "PR" if h.get("isPullRequest") else "issue"
        s.facts.append(f"Upstream {kind} [#{h['number']}]({h['url']}) ({h['state'].lower()}): {h['title']} "
                       f"(mentions {', '.join(f'`{w}`' for w in h['words'])})")
    if not hits and upstream and shutil.which("gh"):
        s.facts.append(f"No upstream issue or PR on {upstream} mentions " + ", ".join(f"`{w}`" for w in words) + ".")
    s.questions += ["When did the behaviour start, and why did nobody notice until now?",
                    "Did a toolchain change (compiler, flags, sanitizers) make it show, or change how it shows?",
                    "Has upstream seen or tried this before, and does the change fit what was decided then?"]
    return s
