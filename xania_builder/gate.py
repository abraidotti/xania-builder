"""``prototype``: the gate. It proves a change on the fork before anything ships, and records the proof.

For a branch against its base it runs, in WSL (where Xania builds):

1. **format**: ``make check-format`` on the branch, as CI does.
2. **builds**: Debug (ASan, UBSan, LSan, and libstdc++ assertions at -O0) and Release (-O2), as CI does.
3. **unit tests**: the whole suite on the branch, both builds (``ctest``, as CI does, plus a per-case report).
4. **before/after**: the branch's tests applied to the *base* and run in both builds. A test that pins a bug
   should fail (or abort) on the base and pass on the branch; if it passes on both, it doesn't test the fix.
5. **Sim**: trials from the dossier's ``gate.toml`` (or its gate plan), on the branch and, where an expectation
   is given, on the base too: a crash that "reproduces" on the base and is "clean" on the branch.
6. **static**: Builder's own detectors on the focus functions, base against branch.

Everything lands in ``dossiers/<slug>/gate.json`` and ``gate.md``. Exit codes: 0 passed, 1 a step failed or
didn't meet its expectation, 2 couldn't run.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA = 1
MODES = ("Debug", "Release")


@dataclass
class Step:
    key: str
    title: str
    ok: bool | None = None  # None: skipped
    expected: str = ""  # what passing means, in words
    detail: str = ""  # what happened, in words
    seconds: float = 0.0
    log: str = ""  # the tail of the output
    data: dict = field(default_factory=dict)


@dataclass
class Gate:
    slug: str
    branch: str
    branch_sha: str
    base_sha: str
    started: float = field(default_factory=time.time)
    seconds: float = 0.0
    environment: dict = field(default_factory=dict)
    changes: dict = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)
    error: str = ""

    @property
    def passed(self) -> bool:
        return not self.error and all(s.ok is not False for s in self.steps)

    def exit_code(self) -> int:
        return 2 if self.error else 0 if self.passed else 1

    def to_dict(self) -> dict:
        return {"schema": SCHEMA, **asdict(self), "passed": self.passed, "exit_code": self.exit_code()}


# WSL ------------------------------------------------------------------------------------------------------------

def wsl_path(p: Path) -> str:
    s = str(Path(p).resolve())
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", s)
    return f"/mnt/{m.group(1).lower()}/{m.group(2).replace(os.sep, '/')}" if m else s


class Shell:
    """Runs bash scripts in WSL (or locally on Linux). Scripts go on stdin as bytes: wsl.exe expands $VARS in
    arguments, and text mode would add \\r."""

    def __init__(self, distro: str):
        self.cmd = ["wsl.exe", "-d", distro, "bash", "-s"] if os.name == "nt" else ["bash", "-s"]

    def run(self, script: str, timeout: int = 3600) -> tuple[int, str]:
        r = subprocess.run(self.cmd, input=script.encode(), capture_output=True, timeout=timeout)
        out = (r.stdout + r.stderr).decode("utf-8", errors="replace")
        return r.returncode, out


# User names seen on this machine (the WSL user, the Windows user): published output never contains them.
PRIVATE_NAMES: set[str] = {n for n in (os.environ.get("USERNAME", ""), os.environ.get("USER", "")) if len(n) > 2}


def redact(text: str) -> str:
    """Gate output gets published: home directories become ~ and user names become "user"."""
    text = re.sub(r"/home/[^/\s]+", "~", text)
    text = re.sub(r"(?i)[A-Z]:[\\/]Users[\\/][^\\/\s]+", "~", text)
    for name in sorted(PRIVATE_NAMES, key=len, reverse=True):
        text = re.sub(re.escape(name), "user", text, flags=re.I)
    return text


def _tail(text: str, n: int = 40) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip() and not re.match(r"^\[\d+/\d+\] ", ln)]
    return redact("\n".join(lines[-n:]))


# Catch2 ---------------------------------------------------------------------------------------------------------

def parse_junit(xml: str) -> dict[str, str]:
    """{test case (or "case/section"): "pass" | "fail"} from Catch2's JUnit reporter."""
    out: dict[str, str] = {}
    try:
        root = ET.fromstring(xml.strip())  # the XML declaration must come first: no leading newline
    except ET.ParseError:
        return out
    for tc in root.iter("testcase"):
        name = tc.get("name", "")
        failed = tc.find("failure") is not None or tc.find("error") is not None
        out[name] = "fail" if failed or out.get(name) == "fail" else "pass"
    return out


def new_test_cases(diff: str) -> list[str]:
    return re.findall(r'^\+\s*TEST_CASE\("([^"]+)"', diff, re.M)


def case_status(results: dict[str, str], case: str, aborted: bool) -> str:
    mine = {k: v for k, v in results.items() if k == case or k.startswith(case + "/")}
    if not mine:
        return "aborted" if aborted else "missing"
    return "fail" if "fail" in mine.values() else "pass"


# The gate -------------------------------------------------------------------------------------------------------

def find_dossier(dossiers: Path, ref: str) -> Path:
    p = Path(ref)
    if (p / "dossier.json").exists():
        return p
    m = re.fullmatch(r"#?(\d+)", ref)
    pattern = f"issue-{m.group(1)}-*" if m else f"{ref}*"
    hits = sorted(dossiers.glob(pattern))
    if len(hits) != 1:
        raise FileNotFoundError(f"{len(hits)} dossiers match {ref!r} in {dossiers}")
    return hits[0]


def load_plan(folder: Path) -> dict:
    """gate.toml in the dossier folder (written by whoever writes the change) wins over research's gate plan."""
    toml = folder / "gate.toml"
    if toml.exists():
        return tomllib.loads(toml.read_text(encoding="utf-8"))
    plan = json.loads((folder / "dossier.json").read_text(encoding="utf-8")).get("gate", {})
    return {"sim": [{"args": shlex.split(t["command"]), "why": t["why"], "branch": "clean"}
                    for t in plan.get("sim", []) if not t["command"].startswith("pytest")]}


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=120,
                       encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def shared_base_dir(base_sha: str) -> str:
    return f"_base-{base_sha[:12]}"


LOCK_STALE_S = 4 * 3600  # a lock older than this is from a gate that died


def run(cfg, folder: Path, branch: str, base: str = "", only: set[str] | None = None, say=print) -> Gate:
    """Run the gate, one at a time: base worktrees are shared between dossiers."""
    cfg.gate_dir.mkdir(parents=True, exist_ok=True)
    lock = cfg.gate_dir / "gate.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime < LOCK_STALE_S:
        raise RuntimeError(f"another gate is running ({lock.read_text(encoding='utf-8').strip()}); "
                           f"delete {lock} if it isn't")
    lock.write_text(f"{folder.name}, started {time.strftime('%H:%M')}", encoding="utf-8")
    try:
        return _run(cfg, folder, branch, base, only, say)
    finally:
        lock.unlink(missing_ok=True)


def _run(cfg, folder: Path, branch: str, base: str = "", only: set[str] | None = None, say=print) -> Gate:
    plan = load_plan(folder)
    src = cfg.source
    branch_sha = _git(src, "rev-parse", f"{branch}^{{commit}}").strip()
    base = base or plan.get("base") or _git(src, "merge-base", branch, cfg.main_ref).strip()
    base_sha = _git(src, "rev-parse", f"{base}^{{commit}}").strip()
    g = Gate(folder.name, branch, branch_sha, base_sha)
    t0 = time.time()
    sh = Shell(cfg.wsl_distro)
    want = (lambda k: only is None or any(k.startswith(o) for o in only))

    # What changed, and the tests to replay on the base.
    diff_tests = _git(src, "diff", f"{base_sha}..{branch_sha}", "--", "src/test")
    g.changes = {
        "files": [ln.split("\t", 1) for ln in _git(src, "diff", "--name-status", f"{base_sha}..{branch_sha}")
                  .splitlines()],
        "stat": _git(src, "diff", "--shortstat", f"{base_sha}..{branch_sha}").strip(),
        "commits": _git(src, "log", "--format=%h %s", f"{base_sha}..{branch_sha}").splitlines(),
        # Test cases the diff adds that the base didn't have (an edit next to an old one can show it as added).
        "new_tests": [t for t in new_test_cases(diff_tests) if t not in set(re.findall(
            r'TEST_CASE\("([^"]+)"', _git(src, "grep", "-h", "TEST_CASE(", base_sha, "--", "src/test")))],
    }
    work = cfg.gate_dir / g.slug
    work.mkdir(parents=True, exist_ok=True)
    (work / "tests.patch").write_text(diff_tests, encoding="utf-8", newline="\n")

    W = f"$HOME/xania-gate/{g.slug}"
    # The base is shared by every dossier on the same base commit (one worktree and its builds, not one per
    # dossier): each gate resets it to the base and applies its own tests, so only the test files recompile.
    D = {"branch": f"{W}/branch", "base": f"$HOME/xania-gate/{shared_base_dir(base_sha)}"}
    R = cfg.wsl_repo
    say(f"gate {g.slug}: {branch} {branch_sha[:10]} against {base_sha[:10]}")
    prep = f"""
set -e
R={R}; W={W}; B={D["base"]}
git -C "$R" fetch -q {shlex.quote(wsl_path(src))} +refs/heads/{branch}:refs/gate/{g.slug}
git -C "$R" cat-file -e {base_sha}^{{commit}} || git -C "$R" fetch -q origin
mkdir -p "$W"
[ -d "$W/branch" ] || git -C "$R" worktree add -q --detach "$W/branch" {branch_sha}
[ -d "$B" ] || git -C "$R" worktree add -q --detach "$B" {base_sha}
cd "$W/branch" && git checkout -q -f --detach {branch_sha} && git clean -qfd src
cd "$B" && git checkout -q -f --detach {base_sha} && git clean -qfd src
git apply {shlex.quote(wsl_path(work / 'tests.patch'))} 2>&1 || {{ echo "tests.patch doesn't apply to the base"; exit 3; }}
echo "gcc: $(g++-15 --version 2>/dev/null | head -1 || g++ --version | head -1)"
echo "cmake: $(cmake --version | head -1)"
echo "os: $(. /etc/os-release; echo $PRETTY_NAME)"
echo "user: $(whoami)"
"""
    code, out = sh.run(prep, timeout=900)
    if code:
        g.error = f"couldn't set up the worktrees: {_tail(out, 10)}"
        return _finish(g, folder, t0)
    for ln in out.splitlines():
        k, _, v = ln.partition(": ")
        if k in ("gcc", "cmake", "os"):
            g.environment[k] = v
        elif k == "user" and len(v.strip()) > 2:
            PRIVATE_NAMES.add(v.strip())
    g.environment["distro"] = cfg.wsl_distro

    def step(key: str, title: str, expected: str, script: str, timeout: int = 3600) -> Step | None:
        if not want(key):
            return None
        say(f"  {title} ...")
        st = Step(key, title, expected=expected)
        t = time.time()
        code, out = sh.run(script, timeout=timeout)
        st.seconds = round(time.time() - t, 1)
        st.ok, st.log = code == 0, _tail(out)
        st.data["exit"] = code
        st.data["output"] = out
        g.steps.append(st)
        # Each step's outcome as it happens, so a log watcher sees progress (the full verdicts print at the end).
        say(f"    -> {'done' if code == 0 else f'exit {code}'} in {st.seconds:.0f} s")
        return st

    # 1. Format
    s = step("format", "clang-format (make check-format, as CI)", "no formatting differences",
             f'cd {D["branch"]} && make check-format 2>&1')
    if s:
        s.detail = "clean" if s.ok else "formatting differs: run `make reformat-code`"

    # 2. Builds, 3. unit tests, 4. before/after
    results: dict[tuple[str, str], tuple[dict, bool]] = {}
    for where in ("branch", "base"):
        for mode in MODES:
            lc = mode.lower()
            label = "the branch" if where == "branch" else "the base with the branch's tests"
            b = step(f"build.{where}.{lc}", f"{mode} build of {label}", "it compiles (-Werror)",
                     f"cd {D[where]} && make build BUILD_TYPE={mode} 2>&1"
                     + (f" && make install BUILD_TYPE={mode} > /dev/null 2>&1" if mode == "Debug" else ""))
            if b and not b.ok:
                if (where == "base" and "error:" in b.log and "src/test/" in b.log
                        and any(s.key == f"build.branch.{lc}" and s.ok for s in g.steps)):
                    # The base is known to build: only the branch's tests were added, so they use something the
                    # change adds. That's not a failure, but the before/after proof has to come from Sim instead.
                    b.ok = None
                    b.detail = ("the new tests use code the change adds, so they can't compile without it; Sim's "
                                "trials on the base are the before/after proof")
                    b.data["needs_change"] = True
                else:
                    b.detail = "build failed"
                continue
            if b:
                b.detail = "up to date (nothing to rebuild)" if b.seconds < 3 else f"built in {b.seconds:.0f} s"
            xml = f"/tmp/xania-gate-{g.slug}-{where}-{lc}.xml"
            u = step(f"unit.{where}.{lc}", f"Unit tests, {mode}, {label}",
                     "every test passes" if where == "branch" else "the new tests fail here (they pin the bug)",
                     f"cd {D[where]}/cmake-build-{lc} && rm -f {xml}; "
                     + ("ctest --output-on-failure > /tmp/ctest.log 2>&1; c=$?; tail -5 /tmp/ctest.log; "
                        if where == "branch" else "c=0; ")
                     + f"./src/test/xania_test -r junit -o {xml} > /tmp/catch.log 2>&1; x=$?; "
                     "grep -m3 -E 'Assertion|ERROR: AddressSanitizer|runtime error' /tmp/catch.log; "
                     f"echo '=== junit ==='; cat {xml} 2>/dev/null; exit $(( c > x ? c : x ))")
            if not u:
                continue
            out = u.data.pop("output")
            junit = out.split("=== junit ===", 1)[1] if "=== junit ===" in out else ""
            cases = parse_junit(junit)
            # A run that died (an assertion, ASan, or any signal: 134 abort, 139 segfault) leaves no full report.
            died = u.data.get("exit", 0) >= 128 or bool(re.search(r"Assertion '.*' failed|ERROR: AddressSanitizer", out))
            aborted = died and (not cases or "</testsuites>" not in junit)
            results[(where, lc)] = (cases, aborted)
            u.log = _tail(out.split("=== junit ===", 1)[0], 15)
            fails = sorted(k for k, v in cases.items() if v == "fail")
            u.data.update(cases=len(cases), failed=fails, aborted=aborted)
            if where == "branch":
                u.detail = (f"{len(cases)} test cases and sections, all passed" if u.ok and not fails else
                            f"{len(fails)} failed: {', '.join(fails[:5])}" + (" (aborted)" if aborted else ""))
            else:
                u.ok = None  # judged by the before/after step
                why = re.search(r"Assertion '.*' failed|ERROR: AddressSanitizer: \S+", out)
                signal = {134: "SIGABRT", 139: "SIGSEGV (a segfault)"}.get(u.data.get("exit", 0), "")
                u.detail = (f"aborted: {why.group(0) if why else signal or 'the test binary died'}" if aborted else
                            f"{len(fails)} of {len(cases)} failed" + (f": {', '.join(fails[:4])}" if fails else ""))
    # If the new tests need the change to compile, the base worktree didn't build, and Sim still needs the base:
    # build the base exactly as it is (without the branch's tests) for Sim's trials there.
    if any(s.data.get("needs_change") for s in g.steps) and plan.get("sim"):
        b = step("build.base-for-sim", "Debug build of the base as it is (for Sim's trials on it)",
                 "it compiles and installs",
                 f"cd {D['base']} && git checkout -q -f --detach {base_sha} && git clean -qfd src && "
                 "make build BUILD_TYPE=Debug 2>&1 && make install BUILD_TYPE=Debug > /dev/null 2>&1")
        if b:
            b.detail = f"built in {b.seconds:.0f} s" if b.ok else "build failed"
    for st in g.steps:
        st.data.pop("output", None)

    if want("before-after") and g.changes["new_tests"]:
        st = Step("before-after", "The new tests, before and after the change",
                  expected="each new test fails or aborts on the base in at least one build, and passes on the branch")
        table = []
        ok = True
        for case in g.changes["new_tests"]:
            row = {"case": case}
            for where in ("base", "branch"):
                for lc in ("debug", "release"):
                    cases, aborted = results.get((where, lc), ({}, False))
                    row[f"{where}.{lc}"] = case_status(cases, case, aborted) if (where, lc) in results else "not run"
            pins = any(row[f"base.{m}"] in ("fail", "aborted") for m in ("debug", "release"))
            fixed = all(row[f"branch.{m}"] == "pass" for m in ("debug", "release"))
            row["verdict"] = "pins the fix" if pins and fixed else "fails on the branch" if not fixed else \
                "passes before too (doesn't pin the bug; fine for a test of behaviour that must not change)"
            ok &= fixed
            table.append(row)
        st.data["table"] = table
        base_built = any(k[0] == "base" for k in results)
        if not base_built:
            # Judge only the branch side; Sim has to show the bug on the base (checked below).
            st.ok = None if ok else False
            st.detail = ("the new tests pass on the branch; they can't build on the base (they test code the change "
                         "adds), so the base side is Sim's" if ok else "the new tests fail on the branch")
            for r in table:
                r["verdict"] = "can't build before the change" if ok else r["verdict"]
        else:
            st.ok = ok and any(r["verdict"] == "pins the fix" for r in table)
            st.detail = f"{sum(r['verdict'] == 'pins the fix' for r in table)} of {len(table)} new tests pin the fix"
        g.steps.append(st)

    # 5. Sim
    for n, trial in enumerate(plan.get("sim", [])):
        for where in ("base", "branch"):
            expect = trial.get(where, "")
            if not expect or expect == "skip" or not want(f"sim.{n}.{where}"):
                continue
            st = _sim(cfg, trial, where, expect, D[where], n, say)
            say(f"    -> {'ok' if st.ok else 'FAIL'}: {st.detail.splitlines()[0] if st.detail else ''}")
            g.steps.append(st)

    # A fix needs proof that the bug was there: a new test failing on the base, or Sim seeing it on the base.
    ba = next((s for s in g.steps if s.key == "before-after"), None)
    sim_before = [s for s in g.steps if s.key.startswith("sim.") and s.key.endswith(".base")]
    if only is None and (ba is None or ba.ok is None):
        st = Step("before-proof", "Proof the bug was there before the change",
                  expected="a new test fails on the base, or a Sim trial shows the bug on the base")
        st.ok = any(s.ok for s in sim_before)
        st.detail = ("Sim showed it on the base: " + "; ".join(s.title for s in sim_before if s.ok) if st.ok else
                     "nothing shows the bug on the base: add a test that fails there, or a Sim trial that reproduces it")
        g.steps.append(st)

    # 6. Static
    if want("static"):
        g.steps.append(_static(cfg, folder, base_sha, branch_sha))
    return _finish(g, folder, t0)


def _sim(cfg, trial: dict, where: str, expect: str, checkout: str, n: int, say) -> Step:
    args = [str(a) for a in trial["args"]]
    title = f"Sim `{' '.join(args)}` on the {where}"
    st = Step(f"sim.{n}.{where}", title, expected=trial.get(f"{where}_means") or {
        "reproduces": f"it reproduces `{trial.get('finding', 'a crash')}` (the bug is there)",
        "clean": "it runs and finds no crash", "pass": "the scenario passes", "fail": "the scenario fails"}[expect])
    say(f"  {title} ...")
    t = time.time()
    py = cfg.python_for_sim()
    home = subprocess.run(Shell(cfg.wsl_distro).cmd, input=b"echo $HOME", capture_output=True).stdout.decode().strip()
    path = checkout.replace("$HOME", home)
    env = {**os.environ, "XANIA_SIM_XANIA": path, "PYTHONIOENCODING": "utf-8"}
    if args[0] == "pytest":
        cmd = [py, "-m", "pytest", *args[1:], "-q", "-p", "no:cacheprovider"]
    else:
        cmd = [py, "-m", "xania_sim", "--xania", path, *args, "--json", "--no-record"]
    try:
        r = subprocess.run(cmd, cwd=cfg.sim_repo, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=int(trial.get("timeout", 3600)), env=env)
    except subprocess.TimeoutExpired:
        st.ok, st.detail = False, "timed out"
        return st
    st.seconds = round(time.time() - t, 1)
    st.log = _tail(r.stderr if args[0] != "pytest" else r.stdout + r.stderr, 25)
    if args[0] == "pytest":
        st.ok = (r.returncode == 0) == (expect == "pass")
        st.detail = f"pytest exit {r.returncode}: " + (_tail(r.stdout, 1) or "")
        return st
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        st.ok, st.detail = False, f"Sim exit {r.returncode}, no JSON: {_tail(r.stderr, 3)}"
        return st
    if not res.get("ran"):
        st.ok, st.detail = False, f"couldn't run: {res.get('error')}"
        return st
    crashes = [f for f in res.get("findings", []) if f.get("signature", "").startswith("crash")]
    st.data = {"measurements": res.get("measurements", {}), "findings": [
        {k: f.get(k) for k in ("signature", "title", "status")} for f in res.get("findings", [])],
        "seconds": res.get("seconds"), "commit": res.get("commit")}
    if expect == "reproduces":
        want_sig = trial.get("finding", "crash")
        hit = [f for f in crashes if want_sig in f["signature"]]
        st.ok = bool(hit)
        st.detail = (f"reproduced: {hit[0]['title']}" if hit else
                     f"didn't reproduce `{want_sig}` in {res.get('seconds', 0):.0f} s")
    else:
        outcomes = res.get("outcomes", [])
        st.data["outcomes"] = [{"ok": o.get("ok"), "summary": o.get("summary")} for o in outcomes]
        untested = [o for o in outcomes if o.get("ok") is not True] if trial.get("outcomes") == "all-ok" else []
        st.ok = not crashes and not untested
        m = res.get("measurements", {})
        shown = [f"{k.replace('_', ' ')} {v}" for k, v in m.items() if isinstance(v, (int, float, str))]
        st.detail = ("crashed: " + "; ".join(f["title"] for f in crashes) if crashes else
                     f"{len(untested)} of {len(outcomes)} checks didn't pass: " + "; ".join(
                         o.get("summary", "") for o in untested[:3]) if untested else
                     f"no crash in {res.get('seconds', 0):.0f} s" + (f" ({', '.join(shown)})" if shown else ""))
    if expect == "reproduces":
        m = res.get("measurements", {})
        shown = [f"{k} {v}" for k, v in m.items() if isinstance(v, str)]
        if shown:
            st.detail += f" ({', '.join(shown)})"
    return st


def _static(cfg, folder: Path, base_sha: str, branch_sha: str) -> Step:
    from .research import string_view_hits
    from .source import Index

    st = Step("static", "Builder's detectors on the focus, base against branch",
              expected="no string_view indexed like a C string is left in the focus")
    focus = json.loads((folder / "dossier.json").read_text(encoding="utf-8"))["focus"]
    names = [f["name"] for f in focus["functions"]]
    rows = []
    for name in names:
        row = {"function": name}
        for label, sha in (("base", base_sha), ("branch", branch_sha)):
            root, _ = cfg.checkout_at(sha)
            ix = Index(root)
            hits = [h for fn in ix.find(name) for h in string_view_hits(ix, fn)]
            row[label] = [f"{w} at {rel}:{ln}" for w, rel, ln in hits]
        rows.append(row)
    st.data["table"] = rows
    before = sum(len(r["base"]) for r in rows)
    after = sum(len(r["branch"]) for r in rows)
    st.ok = after == 0 or after < before
    st.detail = f"{before} before, {after} after"
    if before == after == 0:
        st.ok, st.detail = None, "doesn't apply: the focus has no string_view indexing, before or after"
    return st


def _finish(g: Gate, folder: Path, t0: float) -> Gate:
    g.seconds = round(time.time() - t0, 1)
    (folder / "gate.json").write_text(redact(json.dumps(g.to_dict(), indent=1)), encoding="utf-8")
    (folder / "gate.md").write_text(redact(markdown(g)), encoding="utf-8")
    return g


def _mark(ok) -> str:
    return "✅" if ok else "❌" if ok is False else "➖"


def markdown(g: Gate) -> str:
    out = [f"# Gate: {g.slug}", "",
           f"Branch `{g.branch}` at `{g.branch_sha[:10]}` against base `{g.base_sha[:10]}`: "
           + ("**passed**" if g.passed else "**couldn't run**" if g.error else "**failed**")
           + f" in {g.seconds / 60:.0f} min, {time.strftime('%Y-%m-%d %H:%M', time.localtime(g.started))}.", ""]
    if g.error:
        out += [f"> {g.error}", ""]
    if g.environment:
        out += ["Environment: " + "; ".join(f"{k} {v}" for k, v in g.environment.items()), ""]
    if g.changes:
        out += [f"Changes: {g.changes.get('stat', '')}", ""]
        out += [f"- `{c}`" for c in g.changes.get("commits", [])] + [""]
    out += ["| | Step | Expected | Result | Time |", "|---|---|---|---|---|"]
    for s in g.steps:
        out.append(f"| {_mark(s.ok)} | {s.title} | {s.expected} | {s.detail} | {s.seconds:.0f} s |")
    out.append("")
    for s in g.steps:
        if s.key == "before-after":
            out += ["## The new tests, before and after", "",
                    "| Test | Base, Debug | Base, Release | Branch, Debug | Branch, Release | |",
                    "|---|---|---|---|---|---|"]
            for r in s.data["table"]:
                out.append(f"| {r['case']} | {r['base.debug']} | {r['base.release']} | {r['branch.debug']} | "
                           f"{r['branch.release']} | {r['verdict']} |")
            out.append("")
        if s.key == "static":
            out += ["## Detectors, base against branch", "", "| Function | Base | Branch |", "|---|---|---|"]
            for r in s.data["table"]:
                out.append(f"| `{r['function']}` | {', '.join(r['base']) or 'none'} | "
                           f"{', '.join(r['branch']) or 'none'} |")
            out.append("")
    logs = [s for s in g.steps if s.log and (s.ok is False or s.key.startswith(("sim", "unit.base")))]
    if logs:
        out += ["## Logs", ""]
        for s in logs:
            out += [f"<details><summary>{_mark(s.ok)} {s.title}</summary>", "", "```", s.log, "```", "", "</details>",
                    ""]
    return "\n".join(out)
