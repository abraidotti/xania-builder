"""``ship``: push a gated branch and open (or update) its pull request, with a description built from the
dossier's analysis and the gate's results, linking to the dossier's page on the website.

It refuses unless the gate passed **at the branch's current commit**. The fork is the default target; upstream
only with ``--to upstream``, which a person runs by hand after the fork PR has been reviewed.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path

from .site import PAGES_URL

ATTRIBUTION = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"


def _outside_code(md: str, fn) -> str:
    """Apply fn to the parts of md that aren't fenced code blocks or `inline code`."""
    out = []
    for i, block in enumerate(re.split(r"(^```.*?^```[^\n]*$)", md, flags=re.M | re.S)):
        if i % 2:
            out.append(block)
            continue
        out.append("".join(p if j % 2 else fn(p) for j, p in enumerate(re.split(r"(`[^`\n]+`)", block))))
    return "".join(out)


def retarget(md: str, target: str, fork: str, upstream: str) -> str:
    """Issue references, written in analyses as ``#N`` (the fork's) and ``upstream #N``, made right for the repo
    the PR goes to: on the fork, upstream's become ``owner/repo#N``; on upstream, the fork's do."""
    def fix(text: str) -> str:
        text = re.sub(r"\bupstream #(\d+)", lambda m: f"\x00{m.group(1)}\x00", text)
        if target == "upstream":
            text = re.sub(r"(?<![\w/#\[])#(\d+)\b", lambda m: f"{fork}#{m.group(1)}", text)
            return re.sub(r"\x00(\d+)\x00", r"#\1", text)
        return re.sub(r"\x00(\d+)\x00", lambda m: f"{upstream}#{m.group(1)}", text)

    return _outside_code(md, fix)


def unwrap(md: str) -> str:
    """Join hard-wrapped lines: GitHub shows every newline in a PR description as a line break. Code blocks,
    tables, headings and HTML stay as they are; a list item's continuation lines join the item."""
    out: list[str] = []
    fence = False
    for ln in md.split("\n"):
        if ln.startswith("```"):
            fence = not fence
            out.append(ln)
            continue
        plain = ln.strip() and not re.match(r"^(\s*[-*] |\s*\d+\. |#|\||<|>|```)", ln)
        prev = out[-1] if out else ""
        joinable = prev.strip() and not re.match(r"^(#|\||<|```)", prev) and not prev.rstrip().endswith("</details>")
        if not fence and plain and joinable and out:
            out[-1] = prev.rstrip() + " " + ln.strip()
        else:
            out.append(ln)
    return "\n".join(out)


def sections(md: str) -> dict[str, str]:
    """{heading: body} for each ## and ### heading."""
    out: dict[str, str] = {}
    parts = re.split(r"^(#{2,3}) (.+)$", md, flags=re.M)
    for i in range(1, len(parts) - 2, 3):
        out[parts[i + 1].strip()] = parts[i + 2].strip()
    return out


def _first_table(md: str) -> str:
    m = re.search(r"(?:^\|.*\|[ \t]*(?:\n|\Z))+", md, re.M)
    return m.group(0).strip() if m else ""


def _until(md: str, stop: str) -> str:
    return md.split(stop, 1)[0].strip()


def _mark(ok) -> str:
    return "✅" if ok else "❌" if ok is False else "➖"


def gate_tables(g: dict, head: str = "") -> str:
    out = ["| | Check | Expected | Result |", "|---|---|---|---|"]
    for s in g["steps"]:
        if s["key"].startswith("unit.base"):
            continue  # shown in the before/after table
        out.append(f"| {_mark(s['ok'])} | {s['title']} | {s['expected']} | {s['detail']} |")
    for s in g["steps"]:
        if s["key"] == "before-after":
            out += ["", "The new tests on the code **before** the change (the branch's tests applied to the base) "
                        "and after it:", "",
                    "| Test | Before, Debug | Before, Release | After, Debug | After, Release |",
                    "|---|---|---|---|---|"]
            for r in s["data"]["table"]:
                out.append(f"| {r['case']} | {r['base.debug']} | {r['base.release']} | {r['branch.debug']} | "
                           f"{r['branch.release']} |")
    env = g.get("environment", {})
    if env:
        out += ["", f"<sub>{env.get('gcc', '')}; {env.get('cmake', '')}; {env.get('os', '')}. Base "
                    f"`{g['base_sha'][:10]}`, branch `{g['branch_sha'][:10]}`"
                    + (f" (this PR's `{head[:10]}` has the same code, with its history squashed)"
                       if head and head != g['branch_sha'] else "") + ".</sub>"]
    return "\n".join(out)


def body(folder: Path, g: dict, target: str, issue_ref: str, fork: str, upstream: str = "mattgodbolt/xania",
         head: str = "") -> str:
    a = (folder / "analysis.md").read_text(encoding="utf-8")
    sec = sections(a)
    lead = a.split("## In one paragraph", 1)[1].split("\n## ", 1)[0].strip() if "## In one paragraph" in a else ""
    root = sec.get("Root cause", "")
    fix = sec.get("The fix", "")
    alts = sec.get("Alternatives considered", "")
    answers = sec.get("Answers to the dossier's questions", "")
    gameplay = re.search(r"\*\*5\. Gameplay\.\*\* (.+?)(?=\n\n\*\*\d)", answers, re.S)
    follow = sec.get("Follow-ups (not in this PR)", "")
    why = sec.get("Why debug builds abort and release builds don't", "")
    page = f"{PAGES_URL}/dossiers/{folder.name}/"
    n = re.sub(r"\D", "", issue_ref)
    closes = f"Fixes #{n}." if target == "fork" else f"Reported as {fork}#{n} (with the reproduction)."
    parts = [lead, "", closes, "",
             "## What was wrong", "", _first_table(root)]
    if why:
        parts += ["", "<details><summary>Why debug builds abort and release builds don't</summary>", "",
                  why, "", "</details>"]
    parts += ["", "## The fix", "", fix]
    if alts:
        parts += ["", "<details><summary>Alternatives considered</summary>", "", alts, "", "</details>"]
    if gameplay:
        parts += ["", "## What players will notice", "", gameplay.group(1).strip()]
    parts += ["", "## Verification", "",
              "Run by Xania Builder's gate, in the same configurations CI uses (Debug, which here means "
              "ASan + UBSan + libstdc++ assertions, and Release -O2):", "", gate_tables(g, head)]
    fork_pr = next((p["url"] for p in (json.loads((folder / "pr.json").read_text(encoding="utf-8"))["prs"]
                                       if (folder / "pr.json").exists() else []) if p["target"] == "fork"), "")
    if target == "upstream" and fork_pr:
        parts += ["", f"The same change went through the fork first, where this repo's own CI (format, Debug and "
                      f"Release build and test) passed: {fork_pr}."]
    if follow:
        parts += ["", "## Not in this PR", "", follow]
    parts += ["", "---", "",
              f"**More detail:** the [full write-up]({page}) has the root-cause analysis, every question the "
              f"research asked and its answer, and the gate's logs. Researched and gated with "
              f"[Xania Builder](https://github.com/abraidotti/xania-builder); players simulated with "
              f"[Xania Sim](https://github.com/abraidotti/xania-sim).", "", ATTRIBUTION, ""]
    return unwrap(retarget("\n".join(parts), target, fork, upstream))


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if r.returncode:
        raise RuntimeError(f"{' '.join(cmd[:3])}: {(r.stderr or r.stdout).strip()[:400]}")
    return r.stdout.strip()


def ship(cfg, folder: Path, target: str = "fork", draft: bool = False, dry_run: bool = False, say=print,
         branch: str = "") -> dict:
    """branch: ship this branch instead of the gated one (e.g. reworded commits for upstream); its code must be
    identical to what the gate ran on."""
    gate_file = folder / "gate.json"
    if not gate_file.exists():
        raise RuntimeError(f"no gate for {folder.name}: run `prototype` first")
    g = json.loads(gate_file.read_text(encoding="utf-8"))
    if not g.get("passed"):
        raise RuntimeError(f"the gate for {folder.name} didn't pass; see {folder / 'gate.md'}")
    branch = branch or g["branch"]
    head = _run(["git", "-C", str(cfg.source), "rev-parse", branch])
    # The gate proves code, not history: a branch squashed or reworded after the gate is still the code it gated,
    # as long as the tree (every file's content) is the same.
    tree = lambda ref: _run(["git", "-C", str(cfg.source), "rev-parse", f"{ref}^{{tree}}"])  # noqa: E731
    if head != g["branch_sha"] and tree(head) != tree(g["branch_sha"]):
        raise RuntimeError(f"{branch} is at {head[:10]}, whose code differs from what the gate ran on "
                           f"({g['branch_sha'][:10]}): rerun it")
    if not (folder / "analysis.md").exists():
        raise RuntimeError(f"no analysis.md in {folder}: write it (it answers the dossier's questions)")
    d = json.loads((folder / "dossier.json").read_text(encoding="utf-8"))
    plan = tomllib.loads((folder / "gate.toml").read_text(encoding="utf-8")) if (folder / "gate.toml").exists() else {}
    # The branch's first commit says what the change is; later ones are usually follow-ups.
    title = plan.get("title") or _run(["git", "-C", str(cfg.source), "log", "--reverse", "--format=%s",
                                        f"{g['base_sha']}..{head}"]).splitlines()[0]
    if target == "upstream":
        title = re.sub(r"\s*\(#\d+\)$", "", title)  # "#1" in a title on upstream would mean upstream's #1
    text = body(folder, g, target, d["idea"].get("ref", ""), cfg.fork, cfg.upstream, head)
    (folder / ("pr.md" if target == "fork" else "pr-upstream.md")).write_text(text, encoding="utf-8")
    result = {"title": title, "target": target, "body": str(folder / "pr.md")}
    if dry_run:
        say(f"ship (dry run): would push {branch} and open \"{title}\" on "
            f"{cfg.fork if target == 'fork' else cfg.upstream}; wrote {result['body']}")
        return result
    repo = cfg.fork if target == "fork" else cfg.upstream
    owner = cfg.fork.split("/")[0]
    _run(["git", "-C", str(cfg.source), "push", "-u", "origin", f"{branch}:{branch}"])
    head_ref = branch if target == "fork" else f"{owner}:{branch}"
    existing = json.loads(_run(["gh", "pr", "list", "-R", repo, "--head", branch, "--state", "open",
                                "--json", "url,number"]) or "[]")
    body_file = folder / ("pr.md" if target == "fork" else "pr-upstream.md")
    if existing:
        url = existing[0]["url"]
        _run(["gh", "pr", "edit", url, "--title", title, "--body-file", str(body_file)])
        say(f"ship: updated {url}")
    else:
        cmd = ["gh", "pr", "create", "-R", repo, "--base", "main", "--head", head_ref, "--title", title,
               "--body-file", str(body_file)] + (["--draft"] if draft else [])
        url = _run(cmd).splitlines()[-1]
        say(f"ship: opened {url}")
    result["url"] = url
    rec_file = folder / "pr.json"
    rec = json.loads(rec_file.read_text(encoding="utf-8")) if rec_file.exists() else {"prs": []}
    label = f"PR on {'the fork' if target == 'fork' else 'upstream'}"
    rec["prs"] = [p for p in rec["prs"] if p["target"] != target] + [{"target": target, "url": url, "label": label}]
    rec_file.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return result
