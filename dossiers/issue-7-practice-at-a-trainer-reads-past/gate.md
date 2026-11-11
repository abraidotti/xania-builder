# Gate: issue-7-practice-at-a-trainer-reads-past

Branch `fix/7-practice-empty` at `9c1d338865` against base `82171fa443`: **passed** in 8 min, 2026-11-11 15:31.

Environment: gcc g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake cmake version 4.2.3; os Ubuntu 26.04.1 LTS; distro Ubuntu-26.04

Changes: 2 files changed, 16 insertions(+)

- `9c1d338 skill_lookup: an empty name matches nothing instead of reading past the end`

| | Step | Expected | Result | Time |
|---|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean | 2 s |
| ✅ | Debug build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) | 0 s |
| ✅ | Unit tests, Debug, the branch | every test passes | 1072 test cases and sections, all passed | 3 s |
| ✅ | Release build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) | 0 s |
| ✅ | Unit tests, Release, the branch | every test passes | 1072 test cases and sections, all passed | 0 s |
| ✅ | Debug build of the base with the branch's tests | it compiles (-Werror) | built in 6 s | 6 s |
| ➖ | Unit tests, Debug, the base with the branch's tests | the new tests fail here (they pin the bug) | aborted: Assertion '__pos < this->_M_len' failed | 1 s |
| ✅ | Release build of the base with the branch's tests | it compiles (-Werror) | built in 3 s | 3 s |
| ➖ | Unit tests, Release, the base with the branch's tests | the new tests fail here (they pin the bug) | aborted: SIGSEGV (a segfault) | 0 s |
| ✅ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | 1 of 1 new tests pin the fix | 0 s |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 21 s | 22 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k practice_empty` on the base | xania crashes in skill_lookup (the known-bug check sees the crash) | pytest exit 0: 1 passed, 4 deselected in 39.38s | 40 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k practice_empty` on the branch | xania answers "You can't practice that." and survives (the known-bug check reports the bug gone) | pytest exit 1: 1 failed, 4 deselected in 45.44s | 46 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k cast_empty` on the base | xania crashes in skill_lookup via do_cast (the known-bug check sees the crash) | pytest exit 0: 1 passed, 4 deselected in 36.33s | 37 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k cast_empty` on the branch | xania survives cast '' (the known-bug check reports the bug gone) | pytest exit 1: 1 failed, 4 deselected in 31.97s | 32 s |
| ✅ | Sim `skill bash --classes knight --fights 2` on the branch | it runs and finds no crash | no crash in 252 s (skill bash, kind combat skill, learned by knight 5) | 253 s |
| ✅ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | 2 before, 0 after | 0 s |

## The new tests, before and after

| Test | Base, Debug | Base, Release | Branch, Debug | Branch, Release | |
|---|---|---|---|---|---|
| an empty skill name matches nothing | aborted | aborted | pass | pass | pins the fix |

## Detectors, base against branch

| Function | Base | Branch |
|---|---|---|
| `skill_lookup` | `name[0]` at src/lookup.cpp:39, `name[0]` at src/lookup.cpp:39 | none |
| `do_practice` | none | none |
| `Interpreter::Impl::interpret` | none | none |
| `MudImpl::game_loop` | none | none |
| `ArgParser::shift` | none | none |
| `do_sset` | none | none |
| `do_slookup` | none | none |

## Logs

<details><summary>➖ Unit tests, Debug, the base with the branch's tests</summary>

```
/usr/include/c++/15/string_view:260: constexpr const std::basic_string_view<_CharT, _Traits>::value_type& std::basic_string_view<_CharT, _Traits>::operator[](size_type) const [with _CharT = char; _Traits = std::char_traits<char>; const_reference = const char&; size_type = long unsigned int]: Assertion '__pos < this->_M_len' failed.
```

</details>

<details><summary>✅ Sim `smoke` on the branch</summary>

```
smoke: Smoke: create a bot, look, quit (21 s, Xania 9c1d338865)
  transcript: runs\20261111-153208\Smokea.log
  result: clean
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_bugs.py -k practice_empty` on the base</summary>

```
.                                                                        [100%]
1 passed, 4 deselected in 39.38s
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_bugs.py -k practice_empty` on the branch</summary>

```
            # A real practice first: proves a trainer is here (and that the bot has sessions) before the odd one.
            r = await bot.do("practice sword", expect=r"You practice|already learned|can't practice|can't do that here|"
                                                      r"no practice sessions")
            if "can't do that here" in r.text:
                continue
            at_trainer = "no practice sessions" not in r.text
            if at_trainer:
                crashed = await _crashes_after(mud, bot, "practice ''")
            break
        report = mud.crash_report() if crashed else ""
        if not crashed:
            await bot.close()
        if not at_trainer:
            pytest.skip("no trainer with a session to spare was reached; the check didn't run")
        if crashed:
            found.append(crash_finding(report, "python -m pytest scenarios/test_live_bugs.py -k practice_empty",
                                       "A bot typed practice '' at a trainer (a known-bug check)."))
            await mud.restart()
>       assert crashed, "practice '' no longer crashes xania: the bug looks fixed (or isn't there), retire this test"
E       AssertionError: practice '' no longer crashes xania: the bug looks fixed (or isn't there), retire this test
E       assert False
scenarios\test_live_bugs.py:84: AssertionError
=========================== short test summary info ===========================
FAILED scenarios/test_live_bugs.py::test_practice_empty_quotes_at_a_trainer_crashes_debug_builds
1 failed, 4 deselected in 45.44s
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_bugs.py -k cast_empty` on the base</summary>

```
.                                                                        [100%]
1 passed, 4 deselected in 36.33s
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_bugs.py -k cast_empty` on the branch</summary>

```
F                                                                        [100%]
================================== FAILURES ===================================
_________________ test_cast_empty_quotes_crashes_debug_builds _________________
mud = <xania_sim.core.server.TestMud object at 0x000002C1F050A3C0>
names = <function names.<locals>.<lambda> at 0x000002C1F137DF30>, found = []
    async def test_cast_empty_quotes_crashes_debug_builds(mud, names, found):
        """magic.cpp do_cast -> lookup.cpp skill_lookup: `cast ''` anywhere. Like practice '' (abraidotti/xania#7), but
        any player can type it in any room: do_cast only checks that the line had arguments."""
        bot = Bot(names(), "simpass1", host=mud.host, port=mud.port)
        await bot.enter(Profile())
        crashed = await _crashes_after(mud, bot, "cast ''")
        report = mud.crash_report() if crashed else ""
        if not crashed:
            await bot.close()
        if crashed:
            found.append(crash_finding(report, "python -m pytest scenarios/test_live_bugs.py -k cast_empty",
                                       "A bot typed cast '' (a known-bug check)."))
            await mud.restart()
>       assert crashed, "cast '' no longer crashes xania: the bug looks fixed, retire this test"
E       AssertionError: cast '' no longer crashes xania: the bug looks fixed, retire this test
E       assert False
scenarios\test_live_bugs.py:149: AssertionError
=========================== short test summary info ===========================
FAILED scenarios/test_live_bugs.py::test_cast_empty_quotes_crashes_debug_builds
1 failed, 4 deselected in 31.97s
```

</details>

<details><summary>✅ Sim `skill bash --classes knight --fights 2` on the branch</summary>

```
[00:00] skill trial: planned (skill=bash kind=combat skill classes=knight 5)
[01:13] skill knight 5: staged (ok=True)
[01:13] skill knight 5: practising
[01:26] skill knight 5: using (practice=1->28)
[04:09] skill knight 5: done (uses=5 worked=2 fights=the small troll: won, the small troll: won)
skill: Skill: bash (252 s, Xania 9c1d338865)
  skill bash, kind combat skill, learned by knight 5
  xania_log: runs\skill-20261111-153450\xania.log
  transcripts: runs\skill-20261111-153450
  result: clean
```

</details>
