import json

from conftest import ISSUE

from xania_builder import idea as idea_mod
from xania_builder import research
from xania_builder.idea import Idea
from xania_builder.source import Index


def _issue():
    return Idea("issue", "#1", "do_get reads past the end of all", ISSUE, "https://example/1")


def test_focus_from_prose_and_backtrace(checkout):
    ix = Index(checkout)
    fo = idea_mod.focus(_issue(), ix)
    assert [f.name for f in fo.functions] == ["do_get", "loot"]
    assert fo.files == ["src/act_obj.cpp", "src/fight.cpp"]
    assert fo.commands == ["get", "take"]  # `get all corpse`, plus take (same handler)
    assert fo.stack == [("do_get", "src/act_obj.cpp:17"), ("loot", "src/fight.cpp:2"), ("damage", "src/fight.cpp:6")]
    assert "send_line" not in {f.name for f in fo.functions}  # names in a patch block aren't focus


def test_focus_hints_and_empty(checkout):
    ix = Index(checkout)
    fo = idea_mod.focus(Idea("text", "", "make dropping nicer", "make dropping nicer"), ix, commands=["drop"])
    assert [f.name for f in fo.functions] == ["do_drop"] and fo.commands == ["drop"]
    assert idea_mod.focus(Idea("text", "", "nothing", "nothing"), ix).empty


def test_resolve_text_and_slug(cfg):
    i = idea_mod.resolve("Add a bank\nwith interest", cfg)
    assert (i.kind, i.title, i.slug) == ("text", "Add a bank", "add-a-bank")
    assert Idea("issue", "#12", "Fix: the thing!", "").slug == "issue-12-fix-the-thing"


def test_dossier(checkout, cfg, tmp_path):
    ix = Index(checkout)
    fo = idea_mod.focus(_issue(), ix)
    d = research.build(_issue(), fo, ix, cfg, world=None)
    keys = [s.key for s in d.sections]
    assert keys == ["explorer", "architecture", "patterns", "debt", "gameplay", "docs", "tests"]
    by = {s.key: s for s in d.sections}
    assert "isn't available" in by["explorer"].note
    assert any("`arg1[3]` at src/act_obj.cpp:16" in f for f in by["debt"].facts)
    assert any(f.startswith("TODO at src/act_obj.cpp:16") for f in by["debt"].facts)
    assert any("is_all = matches(arg1, \"all\")" in f for f in by["patterns"].facts)
    assert any("runs on its own from `loot`" in f for f in by["gameplay"].facts)
    assert any("Reported call path" in f for f in by["architecture"].facts)
    assert any(f.startswith("Help `DROP GET TAKE`") for f in by["docs"].facts)
    assert all(s.questions for s in d.sections if not s.note)  # a section that couldn't run asks nothing
    assert d.gate["unit_tests"] == ["src/test/act_obj_test.cpp"]
    assert [t["command"].split()[0] for t in d.gate["sim"]] == ["smoke", "hunt"]  # fight.cpp calls it
    folder = research.write(d, tmp_path / "dossiers")
    md = (folder / "dossier.md").read_text()
    assert md.startswith("# do_get reads past the end of all (#1)") and "## 7. Test coverage" in md
    data = json.loads((folder / "dossier.json").read_text())
    assert data["schema"] == research.SCHEMA and data["focus"]["commands"] == ["get", "take"]


def test_a_failing_section_does_not_lose_the_rest(checkout, cfg, monkeypatch):
    ix = Index(checkout)
    fo = idea_mod.focus(_issue(), ix)
    monkeypatch.setattr(research, "patterns_section", lambda *a: 1 / 0)
    d = research.build(_issue(), fo, ix, cfg)
    by = {s.key: s for s in d.sections}
    assert "ZeroDivisionError" in by["patterns"].note and by["debt"].facts
