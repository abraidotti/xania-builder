"""Disk space: what the gate's workspaces take, a check before a gate runs, and ``clean``.

Each dossier's gate keeps two Xania worktrees in WSL (``~/xania-gate/<dossier>/{branch,base}``), each with a Debug
and a Release build: about 13 GB a dossier. They're kept so a rerun only rebuilds what changed (seconds, not
minutes), but nothing needs them once a change has shipped. On Windows, WSL's disk is one virtual file on the host
drive that grows as builds fill it and doesn't shrink by itself, so the space that matters is the **host's**.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .gate import Shell

GB = 1024 ** 3
REFUSE_BELOW_GB = 20  # a gate needs ~13 GB for a new dossier; refuse to start with less than this free
WARN_BELOW_GB = 40


@dataclass
class Workspace:
    slug: str
    gb: float
    modified: int  # epoch seconds


def host_free_gb(path: str | Path | None = None) -> float:
    """Free space where WSL's disk lives (the user's profile drive on Windows), else where this runs."""
    where = path or (os.environ.get("LOCALAPPDATA") if os.name == "nt" else "/")
    return shutil.disk_usage(where or ".").free / GB


def workspaces(cfg) -> list[Workspace]:
    code, out = Shell(cfg.wsl_distro).run(
        'cd "$HOME/xania-gate" 2>/dev/null || exit 0; for d in */; do d=${d%/}; '
        'echo "$d $(du -sk "$d" | cut -f1) $(stat -c %Y "$d")"; done', timeout=600)
    rows = []
    for ln in out.splitlines():
        m = re.fullmatch(r"(\S+) (\d+) (\d+)", ln.strip())
        if m:
            rows.append(Workspace(m.group(1), int(m.group(2)) / 1024 ** 2, int(m.group(3))))
    return sorted(rows, key=lambda w: -w.modified)


def check(cfg, new_slug: str = "") -> tuple[bool, str]:
    """(ok to run, a sentence about it). A new dossier's workspace needs ~13 GB on the host."""
    free = host_free_gb()
    needs = 0 if any(w.slug == new_slug for w in workspaces(cfg)) else 13
    msg = f"{free:.0f} GB free on the host" + (f"; a new gate workspace takes about {needs} GB" if needs else "")
    if free - needs < REFUSE_BELOW_GB:
        return False, msg + f". That would leave under {REFUSE_BELOW_GB} GB: run `clean` first."
    if free - needs < WARN_BELOW_GB:
        return True, msg + f". Getting low: `clean` removes workspaces of changes that have shipped."
    return True, msg


def remove(cfg, slugs: list[str]) -> str:
    """Remove these dossiers' gate workspaces (worktrees and builds); the dossiers themselves are untouched."""
    script = "set -e\ncd " + cfg.wsl_repo + "\n"
    for s in slugs:
        if not re.fullmatch(r"[\w.-]+", s):
            raise ValueError(f"not a dossier name: {s!r}")
        script += (f'for t in branch base; do [ -d "$HOME/xania-gate/{s}/$t" ] && '
                   f'git worktree remove --force "$HOME/xania-gate/{s}/$t" || true; done\n'
                   f'rm -rf "$HOME/xania-gate/{s}"\ngit update-ref -d refs/gate/{s} 2>/dev/null || true\n')
    script += "git worktree prune\n"
    code, out = Shell(cfg.wsl_distro).run(script, timeout=1200)
    if code:
        raise RuntimeError(out.strip()[-400:])
    return out
