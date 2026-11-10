"""``python -m xania_builder``: doctor and research (prototype and ship come next).

Exit codes, as in Xania Sim: **0** done and nothing needs attention, **1** done but something needs attention
(research: nothing in the idea pointed at the code; doctor: something optional is missing), **2** couldn't run.
``--json`` prints the result on stdout; the human text goes to stderr.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import config as config_mod


def _say(msg: str) -> None:
    print(msg, file=sys.stderr)


def _load_world(cfg):
    cfg.use_explorer()
    from xania_explorer.api import load_world

    return load_world(cfg.source)


def doctor(cfg, as_json: bool) -> int:
    checks: list[tuple[str, bool, bool, str]] = []  # name, ok, required, detail

    def check(name: str, required: bool, fn) -> None:
        try:
            detail = fn()
            checks.append((name, True, required, detail or ""))
        except Exception as e:  # noqa: BLE001
            checks.append((name, False, required, f"{type(e).__name__}: {e}"))

    def source():
        if not (cfg.src / "InterpreterImpl.cpp").exists() and not cfg.src.exists():
            raise FileNotFoundError(f"no src/ in {cfg.source}")
        commit, dirty = cfg.commit()
        return f"{cfg.source} at {commit[:10] or 'no git'}" + (" (uncommitted changes)" if dirty else "")

    def explorer():
        cfg.use_explorer()
        import xania_explorer

        return str(Path(xania_explorer.__file__).parent)

    def sim():
        py = cfg.python_for_sim()
        r = subprocess.run([py, "-c", "import xania_sim, sys; print(xania_sim.__file__)"], capture_output=True,
                           text=True, timeout=60, cwd=cfg.sim_repo if cfg.sim_repo and cfg.sim_repo.exists() else None)
        if r.returncode:
            raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "xania_sim won't import")
        return f"{py}: {r.stdout.strip()}"

    def lore():
        db = cfg.sim_repo / "state" / "lore.db"
        if not db.exists():
            raise FileNotFoundError(f"{db} (run a Sim trial to create it)")
        return str(db)

    def gh():
        if not shutil.which("gh"):
            raise FileNotFoundError("gh not on PATH (needed to read issues and open PRs)")
        r = subprocess.run(["gh", "repo", "view", cfg.fork, "--json", "nameWithOwner"], capture_output=True,
                           text=True, timeout=60)
        if r.returncode:
            raise RuntimeError(r.stderr.strip() or "gh can't see the fork")
        return f"can see {cfg.fork}"

    check("config", False, lambda: str(cfg.path) if cfg.path else (_ for _ in ()).throw(
        FileNotFoundError("no builder.toml; using defaults (copy builder.example.toml)")))
    check("xania source", True, source)
    check("explorer", True, explorer)
    check("sim", True, sim)
    check("sim lore database", False, lore)
    check("gh and the fork", False, gh)
    for name, ok, req, detail in checks:
        _say(f"  {'ok ' if ok else ('ERR' if req else 'warn')}  {name}: {detail}")
    failed = [(ok, req) for _, ok, req, _ in checks if not ok]
    code = 2 if any(req for _, req in failed) else 1 if failed else 0
    if as_json:
        print(json.dumps({"command": "doctor", "exit_code": code, "checks": [
            {"name": n, "ok": o, "required": r, "detail": d} for n, o, r, d in checks]}, indent=1))
    return code


def research(cfg, args) -> int:
    from . import idea as idea_mod
    from . import research as research_mod
    from .source import Index

    if not cfg.src.exists():
        _say(f"COULDN'T RUN: no Xania source at {cfg.source} (see `doctor`)")
        return 2
    world = None
    world_error = ""
    if not args.no_explorer:
        try:
            world = _load_world(cfg)
        except Exception as e:  # noqa: BLE001
            world_error = f"{type(e).__name__}: {e}"
    try:
        idea = idea_mod.resolve(args.idea, cfg, (lambda: world) if world is not None else None)
    except idea_mod.IdeaError as e:
        _say(f"COULDN'T RUN: {e}")
        return 2
    ix = Index(cfg.source)
    fo = idea_mod.focus(idea, ix, args.symbol or [], args.file or [], args.command or [])
    d = research_mod.build(idea, fo, ix, cfg, world)
    if world_error:
        d.sections[0].note = f"Explorer couldn't load the world: {world_error}"
    folder = research_mod.write(d, Path(args.out))
    _say(f"research: {idea.title}" + (f" ({idea.ref})" if idea.ref else ""))
    _say(f"  focus: {', '.join(f.name for f in fo.functions) or '-'}; files {', '.join(fo.files) or '-'}; "
         f"commands {', '.join(fo.commands) or '-'}")
    for s in d.sections:
        _say(f"  {s.title}: {len(s.facts)} facts, {len(s.questions)} questions" + (f" ({s.note})" if s.note else ""))
    _say(f"  gate: {len(d.gate.get('sim', []))} Sim trials, {len(d.gate.get('unit_tests', []))} unit test files")
    _say(f"  wrote {folder / 'dossier.md'}")
    code = 1 if fo.empty else 0
    if args.json:
        print(json.dumps({"command": "research", "exit_code": code, "folder": str(folder), **d.to_dict()}, indent=1))
    return code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="xania_builder")
    ap.add_argument("--config", help="builder.toml to use (default ./builder.toml, then the repo's)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor", help="check the Xania checkout, Explorer, Sim and gh are all where builder.toml says")
    d.add_argument("--json", action="store_true")
    r = sub.add_parser("research", help="write a dossier for an idea: #ISSUE on the fork, bug:CHECK_ID, or text")
    r.add_argument("idea", help="'#1' (a fork issue), 'bug:<Explorer check id>', or a description")
    r.add_argument("--symbol", action="append", help="a function the idea is about (repeatable)")
    r.add_argument("--file", action="append", help="a source file the idea is about (repeatable)")
    r.add_argument("--command", action="append", help="a player command the idea is about (repeatable)")
    r.add_argument("--out", default=str(config_mod.REPO / "dossiers"), help="where dossiers go (default dossiers/)")
    r.add_argument("--no-explorer", action="store_true", help="skip Explorer (faster; section 1 stays empty)")
    r.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    cfg = config_mod.load(args.config)
    if args.cmd == "doctor":
        return doctor(cfg, args.json)
    return research(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
