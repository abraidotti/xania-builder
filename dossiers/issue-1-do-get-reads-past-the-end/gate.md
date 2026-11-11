# Gate: issue-1-do-get-reads-past-the-end

Branch `fix/1-do-get-all` at `d87fcdd647` against base `82171fa443`: **passed** in 13 min, 2026-11-11 14:38.

Environment: gcc g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake cmake version 4.2.3; os Ubuntu 26.04.1 LTS; distro Ubuntu-26.04

Changes: 2 files changed, 170 insertions(+), 13 deletions(-)

- `d87fcdd do_get: decide 'all' vs 'all.<name>' once instead of indexing past the end (#1)`

| | Step | Expected | Result | Time |
|---|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean | 2 s |
| ✅ | Debug build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) | 0 s |
| ✅ | Unit tests, Debug, the branch | every test passes | 1083 test cases and sections, all passed | 4 s |
| ✅ | Release build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) | 0 s |
| ✅ | Unit tests, Release, the branch | every test passes | 1083 test cases and sections, all passed | 0 s |
| ✅ | Debug build of the base with the branch's tests | it compiles (-Werror) | built in 99 s | 99 s |
| ➖ | Unit tests, Debug, the base with the branch's tests | the new tests fail here (they pin the bug) | aborted: Assertion '__pos < this->_M_len' failed | 1 s |
| ✅ | Release build of the base with the branch's tests | it compiles (-Werror) | built in 109 s | 109 s |
| ➖ | Unit tests, Release, the base with the branch's tests | the new tests fail here (they pin the bug) | 1 of 1083 failed: get all from an NPC corpse leaves undroppable items unless named/get all corpse (autoloot sends the same) takes the bread, refrains from the nodrop and noremove items | 0 s |
| ✅ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | 2 of 2 new tests pin the fix | 0 s |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 22 s | 22 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k get_all` on the base | xania crashes when a bot types 'get all' in an empty room (the known-bug check sees the crash) | pytest exit 0: 1 passed, 3 deselected in 37.88s | 38 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k get_all` on the branch | xania survives it (the known-bug check reports the bug gone and asks to be retired) | pytest exit 1: 1 failed, 3 deselected in 34.71s | 35 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k autoloot_of_a_corpse` on the base | xania crashes in do_get when autoloot loots the corpse (the known-bug check sees the crash) | pytest exit 0: 1 passed, 3 deselected in 83.98s (0:01:23) | 84 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k autoloot_of_a_corpse` on the branch | the bot loots the sword and xania survives (the known-bug check reports the bug gone) | pytest exit 1: 1 failed, 3 deselected in 73.72s (0:01:13) | 74 s |
| ✅ | Sim `hunt --minutes 5` on the branch | it runs and finds no crash | no crash in 306 s (fights 16, bot errors 0, crashed False) | 306 s |
| ✅ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | 5 before, 0 after | 0 s |

## The new tests, before and after

| Test | Base, Debug | Base, Release | Branch, Debug | Branch, Release | |
|---|---|---|---|---|---|
| get all and get all.<name> in a room | aborted | pass | pass | pass | pins the fix |
| get all from an NPC corpse leaves undroppable items unless named | aborted | fail | pass | pass | pins the fix |

## Detectors, base against branch

| Function | Base | Branch |
|---|---|---|
| `loot_and_sacrifice_corpse` | none | none |
| `do_get` | `arg1[3]` at src/act_obj.cpp:641, `&arg1[4]` at src/act_obj.cpp:641, `arg1[3]` at src/act_obj.cpp:648, `&arg1[4]` at src/act_obj.cpp:651, `arg1[3]` at src/act_obj.cpp:707 | none |
| `is_mass_looting_npc_undroppable_obj` | none | none |

## Logs

<details><summary>➖ Unit tests, Debug, the base with the branch's tests</summary>

```
/usr/include/c++/15/string_view:260: constexpr const std::basic_string_view<_CharT, _Traits>::value_type& std::basic_string_view<_CharT, _Traits>::operator[](size_type) const [with _CharT = char; _Traits = std::char_traits<char>; const_reference = const char&; size_type = long unsigned int]: Assertion '__pos < this->_M_len' failed.
```

</details>

<details><summary>✅ Sim `smoke` on the branch</summary>

```
smoke: Smoke: create a bot, look, quit (22 s, Xania d87fcdd647)
  transcript: runs\20261111-144155\Smokea.log
  result: clean
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_bugs.py -k get_all` on the base</summary>

```
.                                                                        [100%]
1 passed, 3 deselected in 37.88s
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_bugs.py -k get_all` on the branch</summary>

```
F                                                                        [100%]
================================== FAILURES ===================================
_____________ test_get_all_in_an_empty_room_crashes_debug_builds ______________
mud = <xania_sim.core.server.TestMud object at 0x000001FBBAE6A3C0>
names = <function names.<locals>.<lambda> at 0x000001FBBBD05DD0>, found = []
    async def test_get_all_in_an_empty_room_crashes_debug_builds(mud, names, found):
        """act_obj.cpp do_get: 'get all' reads arg1[3] where arg1 is "all" (3 chars) when nothing is found (line 648).
        Each run that still sees it adds an occurrence to the finding (so the dispatch shows it's still there)."""
        bot = Bot(names(), "simpass1", host=mud.host, port=mud.port)
        await bot.enter(Profile())
        crashed = await _crashes_after(mud, bot, "get all")
        report = mud.crash_report() if crashed else ""
        await bot.close()
        if crashed:
            found.append(crash_finding(report, 'python -m pytest scenarios/test_live_bugs.py -k get_all',
                                       "A bot typed 'get all' in an empty room (a known-bug check)."))
            await mud.restart()
>       assert crashed, "'get all' no longer crashes xania: the bug looks fixed, retire this test"
E       AssertionError: 'get all' no longer crashes xania: the bug looks fixed, retire this test
E       assert False
scenarios\test_live_bugs.py:48: AssertionError
=========================== short test summary info ===========================
FAILED scenarios/test_live_bugs.py::test_get_all_in_an_empty_room_crashes_debug_builds
1 failed, 3 deselected in 34.71s
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_bugs.py -k autoloot_of_a_corpse` on the base</summary>

```
.                                                                        [100%]
1 passed, 3 deselected in 83.98s (0:01:23)
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_bugs.py -k autoloot_of_a_corpse` on the branch</summary>

```
            if not mud.alive():
                crashed = True
                break
            try:
                inv = await bot.do("inventory", expect=r"You are carrying", timeout=5)
            except Exception:  # noqa: BLE001 - the connection may close as xania dies
                continue
            if "a small sword" in inv.text.split("You are carrying", 1)[-1]:  # not the bot's title ("the Swordpupil")
                looted = True
                break
        report = mud.crash_report() if crashed else ""
        if not crashed:
            await bot.close()
            assert looted, "the beggar wasn't killed and looted in 45 s, so the check didn't run"
        if crashed:
            found.append(crash_finding(report, "python -m pytest scenarios/test_live_bugs.py -k autoloot_of_a_corpse",
                                       "A bot with autoloot on killed a mob carrying a sword (a known-bug check)."))
            await mud.restart()
>       assert crashed, "autoloot no longer crashes xania: the bug looks fixed, retire this test"
E       AssertionError: autoloot no longer crashes xania: the bug looks fixed, retire this test
E       assert False
scenarios\test_live_bugs.py:132: AssertionError
=========================== short test summary info ===========================
FAILED scenarios/test_live_bugs.py::test_autoloot_of_a_corpse_with_something_in_it_crashes_debug_builds
1 failed, 3 deselected in 73.72s (0:01:13)
```

</details>

<details><summary>✅ Sim `hunt --minutes 5` on the branch</summary>

```
hunt: Hunt: angry cave beast, 4 bots (306 s, Xania d87fcdd647)
  fights 16, bot errors 0, crashed False
  result: clean
```

</details>
