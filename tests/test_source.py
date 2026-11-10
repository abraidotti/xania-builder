from xania_builder import helps
from xania_builder.source import Index, mask


def test_mask_blanks_comments_strings_and_preprocessor():
    text = '#include "a.hpp"\nint f() { return 1; } // {\nconst char *s = "{}"; /* { */\n'
    m = mask(text)
    assert len(m) == len(text) and m.count("\n") == text.count("\n")
    assert m.count("{") == 1 and "include" not in m and '"  "' in m


def test_functions_lines_and_scopes(checkout):
    ix = Index(checkout)
    names = {f.name for f in ix.functions}
    assert {"is_undroppable", "do_get", "value", "do_drop", "loot", "damage",
            "InterpreterImpl::register_commands"} <= names
    get = ix.find("do_get")[0]
    assert (get.file, get.line, get.end) == ("src/act_obj.cpp", 9, 19)
    assert get.signature == "void do_get(Char *ch, ArgParser args)"
    assert {"matches", "is_undroppable", "send_line"} <= get.calls
    assert ix.at("act_obj.cpp", 15) is get and ix.at("src/act_obj.cpp", 2) is None


def test_callers_commands_tests(checkout):
    ix = Index(checkout)
    get = ix.find("do_get")[0]
    assert [f.name for f in ix.callers(get)] == ["loot"]
    assert [(c.name, c.position) for c in ix.commands_for(get)] == [("get", "Position::Type::Resting"),
                                                                    ("take", "Position::Type::Resting")]
    assert ix.command("drop")[0].position == ""
    assert "Get what?" in ix.strings(get)
    tests = ix.tests_for("src/act_obj.cpp", ["do_drop", "do_get"])
    assert tests == {"src/test/act_obj_test.cpp": ["named after act_obj.cpp", "includes act_obj.hpp",
                                                    "mentions do_drop"]}


def test_helps(checkout):
    hs = helps.load(checkout)
    assert [h.keywords for h in hs] == [["DROP", "GET", "TAKE"], ["MAGIC MISSILE"]]
    assert hs[0].matches("get") and hs[0].matches("ta") is False and hs[1].matches("magic missile")
    assert hs[1].text == "  A spell." and hs[0].line == 2
