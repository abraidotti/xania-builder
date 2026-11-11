import json

from xania_builder import gate, ship, site

JUNIT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites><testsuite name="xania_test" tests="3" failures="1">
<testcase classname="xania_test.global" name="get all/get all in an empty room" time="0.001"/>
<testcase classname="xania_test.global" name="get all/get all picks everything up" time="0.001">
<failure message="sword.obj.carried_by == &amp;scene.player" type="CHECK"/></testcase>
<testcase classname="xania_test.global" name="other" time="0.001"/>
</testsuite></testsuites>"""


def test_parse_junit_and_case_status():
    r = gate.parse_junit(JUNIT)
    assert r["get all/get all in an empty room"] == "pass"
    assert r["get all/get all picks everything up"] == "fail"
    assert gate.case_status(r, "get all", aborted=False) == "fail"
    assert gate.case_status(r, "other", aborted=False) == "pass"
    assert gate.case_status({}, "get all", aborted=True) == "aborted"
    assert gate.case_status(gate.parse_junit("<testsuites><testsuite>"), "x", aborted=False) == "missing"
    assert gate.parse_junit("\n" + JUNIT) == r  # as it comes out of the shell, after a marker line


def test_new_test_cases_from_a_diff():
    diff = '+TEST_CASE("get all and get all.<name> in a room") {\n TEST_CASE("old one") {\n+  TEST_CASE("b") {'
    assert gate.new_test_cases(diff) == ["get all and get all.<name> in a room", "b"]


def test_wsl_path():
    assert gate.wsl_path("C:\\Users\\a\\x") == "/mnt/c/Users/a/x"


def test_find_dossier(tmp_path):
    (tmp_path / "issue-1-foo").mkdir()
    (tmp_path / "issue-1-foo" / "dossier.json").write_text("{}")
    (tmp_path / "issue-12-bar").mkdir()
    assert gate.find_dossier(tmp_path, "#1").name == "issue-1-foo"


def test_markdown_subset():
    out = site.markdown("## A `x` heading\n\nSome **bold** and *it* and [a link](gate.md).\n\n"
                        "| a | b |\n|---|---|\n| `x\\|y` | 2 |\n\n- one\n  more\n- [ ] todo\n\n```cpp\nint a<b;\n```\n")
    assert '<h2 id="a-x-heading">A <code>x</code> heading</h2>' in out
    assert "<strong>bold</strong>" in out and "<em>it</em>" in out and 'href="#gate"' in out
    assert "<td><code>x|y</code></td>" in out
    assert "<li>one more</li>" in out and '<li class="todo">todo</li>' in out
    assert "int a&lt;b;" in out


ANALYSIS = """# Analysis

## In one paragraph

It read past the end.

## Root cause

| When | What |
|---|---|
| 2021 | it broke |

### Why debug builds abort and release builds don't

Assertions.

## The fix

Decide once.

### Alternatives considered

- bounds checks

## Answers to the dossier's questions

**5. Gameplay.** Autoloot leaves undroppable items.

**6. Documentation.** None.

## Follow-ups (not in this PR)

- retire the Sim check
"""


def test_pr_body(tmp_path):
    (tmp_path / "analysis.md").write_text(ANALYSIS, encoding="utf-8")
    g = {"base_sha": "a" * 40, "branch_sha": "b" * 40, "environment": {"gcc": "g++ 15"},
         "steps": [{"key": "format", "title": "clang-format", "expected": "clean", "detail": "clean", "ok": True},
                   {"key": "unit.base.debug", "title": "x", "expected": "", "detail": "", "ok": None},
                   {"key": "before-after", "title": "t", "expected": "", "detail": "", "ok": True,
                    "data": {"table": [{"case": "get all", "base.debug": "aborted", "base.release": "fail",
                                        "branch.debug": "pass", "branch.release": "pass"}]}}]}
    b = ship.body(tmp_path, g, "fork", "#1", "abraidotti/xania")
    assert b.startswith("It read past the end.")
    assert "Fixes #1." in b and "| 2021 | it broke |" in b and "Decide once." in b
    assert "Autoloot leaves undroppable items." in b and "retire the Sim check" in b
    assert "| get all | aborted | fail | pass | pass |" in b
    assert "| ✅ | clang-format |" in b and "| ➖ | x |" not in b
    assert ship.ATTRIBUTION in b
    up = ship.body(tmp_path, g, "upstream", "#1", "abraidotti/xania")
    assert "Reported as abraidotti/xania#1" in up and "Fixes #1" not in up


def test_site_build(tmp_path):
    d = tmp_path / "dossiers" / "issue-1-x"
    d.mkdir(parents=True)
    (d / "dossier.json").write_text(json.dumps({"commit": "c" * 40, "idea": {
        "title": "do_get reads past the end", "ref": "#1", "url": "https://example.com/1"}}))
    (d / "analysis.md").write_text(ANALYSIS, encoding="utf-8")
    pages = site.build(tmp_path / "dossiers", tmp_path / "out")
    page = (tmp_path / "out" / "dossiers" / "issue-1-x" / "index.html").read_text(encoding="utf-8")
    assert len(pages) == 2 and "not gated yet" in page and 'id="analysis"' in page
    assert "do_get reads past the end" in (tmp_path / "out" / "index.html").read_text(encoding="utf-8")


def test_markdown_bold_around_code():
    assert site._inline("**Skip `ch` here** and *`x`*") == \
        "<strong>Skip <code>ch</code> here</strong> and <em><code>x</code></em>"
    assert site._inline("`a*b*c` and `<p>`") == "<code>a*b*c</code> and <code>&lt;p&gt;</code>"


def test_retarget_issue_references():
    md = "Fixes #1; see upstream #279 and `arr#3`.\n```\n#2 in code\n```\nabraidotti/xania#4"
    fork = ship.retarget(md, "fork", "abraidotti/xania", "mattgodbolt/xania")
    assert "Fixes #1; see mattgodbolt/xania#279 and `arr#3`." in fork and "#2 in code" in fork
    up = ship.retarget(md, "upstream", "abraidotti/xania", "mattgodbolt/xania")
    assert "Fixes abraidotti/xania#1; see #279" in up and "\n#2 in code\n" in up and up.endswith("abraidotti/xania#4")


def test_unwrap_joins_paragraphs_only():
    md = ("One line\nwraps here.\n\n- item\n  continues\n- two\n\n| a |\n|---|\n\n```\nx\ny\n```\n"
          "<details><summary>s</summary>\n\nbody\nmore\n\n</details>\n## Head\ntext")
    out = ship.unwrap(md)
    assert "One line wraps here." in out and "- item continues" in out and "- two" in out
    assert "```\nx\ny\n```" in out and "| a |\n|---|" in out and "body more" in out and "## Head\ntext" in out


def test_redact_paths_and_user_names(monkeypatch):
    monkeypatch.setattr(gate, "PRIVATE_NAMES", {"Zorblat"})
    out = gate.redact(r"NO_BUILD /home/zorblat/x and C:\Users\Zorblat\y and /tmp/.xania-9100-zorblat.")
    assert "orblat" not in out.lower()
    assert out == r"NO_BUILD ~/x and ~\y and /tmp/.xania-9100-user."


def test_disk_check_thresholds(monkeypatch):
    from xania_builder import disk

    monkeypatch.setattr(disk, "workspaces", lambda cfg: [disk.Workspace("issue-1-x", 13.0, 0)])
    monkeypatch.setattr(disk, "host_free_gb", lambda path=None: 100.0)
    assert disk.check(None, "issue-1-x")[0] is True                    # reuses its workspace
    monkeypatch.setattr(disk, "host_free_gb", lambda path=None: 25.0)
    ok, why = disk.check(None, "issue-9-new")                          # 25 - 7 (a new branch worktree) < 20: refuse
    assert not ok and "clean" in why
    monkeypatch.setattr(disk, "host_free_gb", lambda path=None: 30.0)
    ok, why = disk.check(None, "issue-1-x")                            # 30 free, no new workspace: warn only
    assert ok and "Getting low" in why
