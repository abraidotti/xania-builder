"""``site``: the dossiers as a static website (what PRs link to). One page per dossier with its analysis, gate and
research, and an index. Standard library only, so GitHub Actions can build it straight from the repo.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import time
from pathlib import Path

PAGES_URL = "https://abraidotti.github.io/xania-builder"
REPO_URL = "https://github.com/abraidotti/xania-builder"


# Markdown: the subset the dossiers use -----------------------------------------------------------------------------

def _inline(text: str) -> str:
    # Code spans first, kept aside as placeholders, so bold, italics and links can wrap them.
    codes: list[str] = []

    def keep(m: re.Match) -> str:
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    p = re.sub(r"`([^`]+)`", keep, text)
    p = html.escape(p, quote=False)
    p = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{_href(m.group(2))}">{m.group(1)}</a>', p)
    p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
    p = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", p)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], p)


def _href(url: str) -> str:
    # Links between a dossier's files become links between the site's tabs.
    return {"dossier.md": "#research", "gate.md": "#gate", "analysis.md": "#analysis"}.get(url, html.escape(url))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", text).lower()).strip("-")


def markdown(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            lang = ln[3:].strip()
            code = html.escape("\n".join(lines[i + 1:j]))
            out.append(f'<pre><code class="lang-{lang or "text"}">{code}</code></pre>')
            i = j + 1
            continue
        if re.match(r"^\s*</?(details|summary)\b", ln):
            m = re.match(r"^\s*<details><summary>(.*)</summary>\s*$", ln)
            out.append(f"<details><summary>{_inline(m.group(1))}</summary>" if m else ln)
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            n, text = len(m.group(1)), _inline(m.group(2))
            out.append(f'<h{n} id="{_slug(text)}">{text}</h{n}>')
            i += 1
            continue
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1]):
            head = _cells(ln)
            rows = []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            out.append('<div class="table"><table><thead><tr>' + "".join(f"<th>{_inline(c)}</th>" for c in head)
                       + "</tr></thead><tbody>" + "".join(
                           "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
                       + "</tbody></table></div>")
            continue
        if re.match(r"^\s*[-*] ", ln):
            items = []
            while i < len(lines) and (re.match(r"^\s*[-*] ", lines[i]) or (lines[i].startswith("  ") and items)):
                if re.match(r"^\s*[-*] ", lines[i]):
                    items.append(re.sub(r"^\s*[-*] ", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            lis = []
            for it in items:
                box = re.match(r"^\[( |x)\] (.*)$", it)
                lis.append(f'<li class="todo">{_inline(box.group(2))}</li>' if box else f"<li>{_inline(it)}</li>")
            out.append("<ul>" + "".join(lis) + "</ul>")
            continue
        if ln.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip("> "))
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(quote))}</blockquote>")
            continue
        if not ln.strip():
            i += 1
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4} |```|\||\s*[-*] |>|\s*<)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
        else:
            out.append(html.escape(ln))
            i += 1
    return "\n".join(out)


def _cells(row: str) -> list[str]:
    row = row.strip().strip("|")
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", row)]


# Pages ------------------------------------------------------------------------------------------------------------

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a64;--line:#e4e1d8;--card:#fff;--accent:#7a4b12;--code:#f3f0e8;
--ok:#1f7a3a;--bad:#a8261b;--warn:#8a6a00}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#151513;--fg:#ecebe6;--muted:#a3a198;
--line:#33322d;--card:#1c1c19;--accent:#e2a65c;--code:#24231f;--ok:#5ec27c;--bad:#f07a6e;--warn:#e0c060}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",
Roboto,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:24px 16px 64px}
header.site{border-bottom:1px solid var(--line);margin-bottom:24px;padding-bottom:12px}
header.site a{color:var(--fg);text-decoration:none;font-weight:600}
header.site p{margin:4px 0 0;color:var(--muted);font-size:14px}
h1{font-size:28px;line-height:1.25;margin:8px 0 12px}h2{font-size:21px;margin:32px 0 8px;padding-top:8px}
h3{font-size:17px;margin:24px 0 6px}a{color:var(--accent)}
code{font:13.5px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--code);padding:1px 4px;
border-radius:4px;overflow-wrap:anywhere}
pre{background:var(--code);padding:12px 14px;border-radius:8px;overflow-x:auto}pre code{padding:0;background:none}
.table{overflow-x:auto;margin:12px 0}table{border-collapse:collapse;font-size:14px;min-width:100%}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}th{background:var(--code)}
blockquote{margin:12px 0;padding:8px 14px;border-left:3px solid var(--accent);color:var(--muted)}
details{margin:8px 0;border:1px solid var(--line);border-radius:8px;padding:6px 12px;background:var(--card)}
summary{cursor:pointer;font-weight:500}li.todo{list-style:"\\2610  "}
.meta{color:var(--muted);font-size:14px}.pill{display:inline-block;padding:1px 9px;border-radius:999px;
font-size:13px;font-weight:600;border:1px solid currentColor}.pass{color:var(--ok)}.fail{color:var(--bad)}
.none{color:var(--muted)}
nav.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin:20px 0 8px;flex-wrap:wrap}
nav.tabs a{padding:8px 14px;text-decoration:none;color:var(--muted);border-bottom:2px solid transparent}
nav.tabs a.on{color:var(--fg);border-color:var(--accent)}section.tab{display:none}section.tab.on{display:block}
.cards{display:grid;gap:12px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px 16px}.card h2{font-size:18px;margin:0 0 6px;padding:0}.card a{text-decoration:none}
.steps{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
"""

JS = """
(function(){var tabs=[].slice.call(document.querySelectorAll('nav.tabs a'));if(!tabs.length)return;
function show(id){tabs.forEach(function(a){a.classList.toggle('on',a.hash==='#'+id)});
[].forEach.call(document.querySelectorAll('section.tab'),function(s){s.classList.toggle('on',s.id===id)})}
function route(){var h=location.hash.slice(1);var t=document.getElementById(h);
if(t&&t.classList.contains('tab'))show(h);else if(t){var s=t.closest('section.tab');if(s)show(s.id);}
else show(tabs[0].hash.slice(1))}window.addEventListener('hashchange',route);route()})();
"""


def _page(title: str, body: str, desc: str = "") -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}"><style>{CSS}</style></head><body><div class="wrap">
<header class="site"><a href="{PAGES_URL}/">Xania Builder</a><p>Research, proof and review notes for changes to
<a href="https://github.com/mattgodbolt/xania">Xania</a>, the MUD. Source: <a href="{REPO_URL}">{REPO_URL[8:]}</a></p>
</header>{body}</div><script>{JS}</script></body></html>"""


def _verdict(gate: dict | None) -> str:
    if not gate:
        return '<span class="pill none">not gated yet</span>'
    if gate.get("error"):
        return '<span class="pill fail">gate couldn\'t run</span>'
    return ('<span class="pill pass">gate passed</span>' if gate.get("passed") else
            '<span class="pill fail">gate failed</span>')


def build(dossiers: Path, out: Path) -> list[Path]:
    if out.exists():
        shutil.rmtree(out)
    (out / "dossiers").mkdir(parents=True)
    entries = []
    for folder in sorted(p for p in dossiers.iterdir() if (p / "dossier.json").exists()):
        d = json.loads((folder / "dossier.json").read_text(encoding="utf-8"))
        gate = json.loads((folder / "gate.json").read_text(encoding="utf-8")) if (folder / "gate.json").exists() else None
        pr = json.loads((folder / "pr.json").read_text(encoding="utf-8")) if (folder / "pr.json").exists() else {}
        idea = d["idea"]
        tabs = []
        for key, name, file in (("analysis", "Analysis", "analysis.md"), ("gate", "Gate", "gate.md"),
                                ("research", "Research", "dossier.md")):
            if (folder / file).exists():
                md = (folder / file).read_text(encoding="utf-8")
                md = re.sub(r"^# .*\n", "", md, count=1)  # the page has its own title
                tabs.append((key, name, markdown(md)))
        links = [f'<a href="{html.escape(idea["url"])}">{html.escape(idea["ref"])}</a>'] if idea.get("url") else []
        for p in pr.get("prs", []):
            links.append(f'<a href="{html.escape(p["url"])}">{html.escape(p["label"])}</a>')
        body = (f'<p class="meta">{" · ".join(links)}</p><h1>{_inline(idea["title"])}</h1>'
                f'<p class="meta">{_verdict(gate)} · researched at Xania <code>{d["commit"][:10]}</code>'
                + (f' · branch <code>{html.escape(gate["branch"])}</code> at <code>{gate["branch_sha"][:10]}</code>'
                   if gate else "") + "</p>"
                + '<nav class="tabs">' + "".join(f'<a href="#{k}">{n}</a>' for k, n, _ in tabs) + "</nav>"
                + "".join(f'<section class="tab" id="{k}">{h}</section>' for k, _, h in tabs))
        page = out / "dossiers" / folder.name / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(_page(idea["title"], body, f"Research and proof for {idea.get('ref') or idea['title']}"),
                        encoding="utf-8")
        for f in ("dossier.json", "gate.json"):
            if (folder / f).exists():
                shutil.copy(folder / f, page.parent / f)
        entries.append((folder.name, idea, gate))
    cards = "".join(
        f'<div class="card"><h2><a href="dossiers/{slug}/">{_inline(idea["title"])}</a></h2>'
        f'<div class="meta">{html.escape(idea.get("ref") or "")} {_verdict(gate)}</div></div>'
        for slug, idea, gate in entries)
    intro = ("<h1>Changes, researched and proven</h1><p>Each change Builder works on gets a page: the "
             "<strong>analysis</strong> (root cause, history, the fix and the alternatives, what players will "
             "notice), the <strong>gate</strong> (format, Debug and Release builds, the new tests run before and "
             "after the change, and Xania Sim's bots playing both), and the <strong>research</strong> it started "
             "from. Builder doesn't write the code: it gathers the facts, asks the questions, and checks the answer."
             f"</p><p class=\"meta\">Updated {time.strftime('%Y-%m-%d')}</p>")
    (out / "index.html").write_text(_page("Xania Builder", intro + f'<div class="cards">{cards}</div>',
                                          "Research and proof for changes to Xania"), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return [out / "index.html"] + [out / "dossiers" / s / "index.html" for s, _, _ in entries]
