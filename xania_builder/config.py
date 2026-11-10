"""Where everything is: the Xania checkout, the fork, Explorer and Sim. Read from builder.toml.

Search order: ``--config PATH``, ``$XANIA_BUILDER_CONFIG``, ``./builder.toml``, then the repo's own builder.toml.
Every key has a default that fits sibling checkouts (``../xania``, ``../xania-explorer``, ``../xania-sim``).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    source: Path  # the Xania checkout research reads
    fork: str = "abraidotti/xania"
    upstream: str = "mattgodbolt/xania"
    sim_xania: str = ""  # the checkout as Sim sees it ("" = Sim's default)
    explorer_repo: Path | None = None
    sim_repo: Path | None = None
    sim_python: str = ""
    path: Path | None = None  # the file it came from

    @property
    def src(self) -> Path:
        return self.source / "src"

    def commit(self) -> tuple[str, bool]:
        """The checkout's commit and whether it has uncommitted changes ("" when it isn't a git checkout)."""
        try:
            head = subprocess.run(["git", "-C", str(self.source), "rev-parse", "HEAD"], capture_output=True,
                                  text=True, timeout=20).stdout.strip()
            dirty = subprocess.run(["git", "-C", str(self.source), "status", "--porcelain", "--untracked-files=no"],
                                   capture_output=True, text=True, timeout=20).stdout.strip()
            return head, bool(dirty)
        except (OSError, subprocess.SubprocessError):
            return "", False

    def python_for_sim(self) -> str:
        if self.sim_python:
            return self.sim_python
        if self.sim_repo:
            for rel in (".venv/Scripts/python.exe", ".venv/bin/python"):
                if (self.sim_repo / rel).exists():
                    return str(self.sim_repo / rel)
        return sys.executable

    def use_explorer(self) -> None:
        """Make ``import xania_explorer`` work from the configured checkout when it isn't installed."""
        _add_path(self.explorer_repo)


def _add_path(repo: Path | None) -> None:
    if repo and repo.exists() and str(repo) not in sys.path:
        sys.path.append(str(repo))


def load(path: str | Path | None = None) -> Config:
    candidates = [path, os.environ.get("XANIA_BUILDER_CONFIG"), Path.cwd() / "builder.toml", REPO / "builder.toml"]
    file = next((Path(p) for p in candidates if p and Path(p).exists()), None)
    data = tomllib.loads(file.read_text(encoding="utf-8")) if file else {}
    base = file.parent if file else REPO

    def rel(value: str | None, default: str) -> Path:
        p = Path(os.path.expanduser(value or default))
        return (p if p.is_absolute() else base / p).resolve()

    x, e, s = data.get("xania", {}), data.get("explorer", {}), data.get("sim", {})
    return Config(
        source=rel(x.get("source"), "../xania"),
        fork=x.get("fork", "abraidotti/xania"),
        upstream=x.get("upstream", "mattgodbolt/xania"),
        sim_xania=x.get("sim_xania", ""),
        explorer_repo=rel(e.get("repo"), "../xania-explorer"),
        sim_repo=rel(s.get("repo"), "../xania-sim"),
        sim_python=s.get("python", ""),
        path=file,
    )
