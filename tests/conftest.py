"""A tiny fake Xania checkout: enough source, help and tests for the index and research to work on."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

ACT_OBJ = textwrap.dedent('''\
    #include "act_obj.hpp"
    #include <string_view>

    namespace {
    bool is_undroppable(const Object *obj, const char dot) { return dot == '\\0' && obj->no_drop; }
    }

    /* 'get' with a { brace } in a comment */
    void do_get(Char *ch, ArgParser args) {
        auto arg1 = args.shift();
        if (arg1.empty()) {
            ch->send_line("Get what?");
            return;
        }
        const auto is_all = matches(arg1, "all");
        if (arg1[3] == '\\0')  // TODO: string_view has no terminator
            ch->send_line("I see nothing here.");
        is_undroppable(nullptr, arg1[3]);
    }

    struct Helper {
        int value() const { return 1; }
    };

    void do_drop(Char *ch, ArgParser args) {
        char buf[100];
        sprintf(buf, "%s", "x");
        ch->send_line("Drop what?");
    }
    ''')

FIGHT = textwrap.dedent('''\
    void loot(Char *looter) {
        do_get(looter, ArgParser("all corpse"));  // autoloot
    }

    void damage(Char *ch) {
        loot(ch);
    }
    ''')

INTERP = textwrap.dedent('''\
    void InterpreterImpl::register_commands() {
        add_command("get", do_get, Position::Type::Resting);
        add_command("take", do_get, Position::Type::Resting);
        add_command("drop", do_drop);
    }
    ''')

HELP = textwrap.dedent('''\
    #HELPS
    0 DROP GET TAKE~
    Syntax: get <object>
    ~

    0 'MAGIC MISSILE'~
    .  A spell.
    ~

    0 $~

    #$
    ''')

TEST = '#include "act_obj.hpp"\nTEST_CASE("drop") { do_drop(nullptr, ArgParser("x")); }\n'

ISSUE = textwrap.dedent('''\
    `do_get` reads `arg1[3]` past the end of `all`; see src/act_obj.cpp:15.

    Autoloot calls it from `loot` (`src/fight.cpp:2`), e.g. `get all corpse`.

    ```
    #6  std::basic_string_view<char>::operator[] (__pos=3) at /usr/include/c++/15/string_view:260
    #7  do_get (ch=..., args=...) at src/act_obj.cpp:17
    #8  loot (looter=...) at src/fight.cpp:2
    #9  damage (ch=...) at src/fight.cpp:6
    ```

    ```cpp
    send_line("this patch's names are not focus");
    ```
    ''')


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "xania"
    (root / "src" / "test").mkdir(parents=True)
    (root / "area").mkdir()
    (root / "src" / "act_obj.cpp").write_text(ACT_OBJ)
    (root / "src" / "fight.cpp").write_text(FIGHT)
    (root / "src" / "InterpreterImpl.cpp").write_text(INTERP)
    (root / "src" / "test" / "act_obj_test.cpp").write_text(TEST)
    (root / "area" / "help.are").write_text(HELP)
    return root


@pytest.fixture
def cfg(checkout: Path, tmp_path: Path):
    from xania_builder.config import Config

    return Config(source=checkout, sim_repo=tmp_path / "no-sim", explorer_repo=None)
