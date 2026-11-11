`skill_lookup` compares the first letter of the name it's given with each skill's (`name[0]`) before checking the prefix. `cast ''` (in any room) and `practice ''` (at a trainer) hand it an **empty** name: ArgParser strips the quotes, and `do_cast` and `do_practice` only check that the line had arguments. Indexing an empty `std::string_view` is undefined behaviour; since GCC 15 (the default here from 2026-10-31) debug builds abort on it, so any player can take a debug MUD down by typing `cast ''`. The fix makes `skill_lookup` return -1 for an empty name, so the player is told "You don't know any spells of that name." or "You can't practice that.", which is also what release builds already said, by luck.

#7 was filed for `practice ''`; checking `skill_lookup`'s other callers for the fix found `cast ''`, the same bug
with no trainer needed. One fix covers both.

Fixes #7.

## What was wrong

| When | Commit | What happened |
|---|---|---|
| 2020-08-22 | `67c11b0` | ArgParser is added. `shift()` strips quotes, so `''` is an empty argument: correct, and unchanged since. |
| 2021-11-14 | `42406b7` | `skill_lookup(const char *)` becomes `skill_lookup(std::string_view)`; `name[0]` stays. An empty C string's `name[0]` was its terminator; an empty view has none. |
| 2021-11-16 | `49a8032` | *"Upgrade do_cast() to use ArgParser."* `do_cast` passes `args.shift()`, so `cast ''` reaches `skill_lookup` as an empty view. Undefined behaviour from here on. |
| 2021-12-04 | `5855495` | *"... practice ... upgraded to ArgParser or string_view"*. The same for `do_practice` and `practice ''`. |
| 2026-10-31 | `82823ff`, `7bd8c82` | g++-15 becomes the default; its libstdc++ checks `operator[]` at `-O0` ([GCC bug 112808](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=112808)), so Debug builds abort here. |
| 2026-11-11 | | Builder's string_view detector listed `skill_lookup`'s `name[0]` while researching #1; a Xania Sim known-bug check confirmed `practice ''` (filed as #7), and another, written while checking callers for the fix, confirmed `cast ''`. |

<details><summary>Why debug builds abort and release builds don't</summary>

As in #1 and #3: libstdc++'s assertions are on at `-O0` since GCC 15 and catch the out-of-range `operator[]`; AddressSanitizer doesn't, because the byte read is still inside the input buffer. In release builds the read goes ahead: for `cast ''` the empty view sits on the closing quote, so `name[0]` is `'`, no skill name starts with an apostrophe, and the player gets the ordinary "unknown spell" answer by accident.

</details>

## The fix

```cpp
int skill_lookup(std::string_view name) {
    // No skill has an empty name, and name[0] below needs one character (an empty argument, from "cast ''" or
    // "practice ''", used to read past the end here). Don't drop the name[0] test instead: matches_start()
    // takes "" as a prefix of every skill.
    if (name.empty())
        return -1;
```

In `skill_lookup` rather than in each command: an empty name can't name a skill whoever passes it, so the check belongs with the lookup. That is also why one change fixes both commands, and any caller added later.

<details><summary>Alternatives considered</summary>

- **Check in `do_cast` and `do_practice`**: two fixes for two callers that are reachable today, and the trap left in `skill_lookup` for the next one. Rejected.
- **`first_char(name)`** (the helper #3 adds) in the comparison: `'\0'` would match no skill, so it would work, but it hides the real rule (an empty name is never a skill) inside a character comparison, and it depends on #3.
- **Drop the `name[0]` comparison** (it's only a fast path before `matches_start`): `matches_start("", x)` is true for every `x`, so an empty name would then match the first skill in the table. That's why the comment says not to.

</details>

## What players will notice

A player who types `cast ''` is told "You don't know any spells of that name."; one who types `practice ''` at a trainer is told "You can't practice that." and keeps their session. Before, either took a debug MUD down for everyone, and `cast ''` needed nothing but a character. Release builds already gave those answers. Nothing an abusive player gains; the crash itself was the abuse.

## Verification

Run by Xania Builder's gate, in the same configurations CI uses (Debug, which here means ASan + UBSan + libstdc++ assertions, and Release -O2):

| | Check | Expected | Result |
|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean |
| ✅ | Debug build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) |
| ✅ | Unit tests, Debug, the branch | every test passes | 1072 test cases and sections, all passed |
| ✅ | Release build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) |
| ✅ | Unit tests, Release, the branch | every test passes | 1072 test cases and sections, all passed |
| ✅ | Debug build of the base with the branch's tests | it compiles (-Werror) | built in 6 s |
| ✅ | Release build of the base with the branch's tests | it compiles (-Werror) | built in 3 s |
| ✅ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | 1 of 1 new tests pin the fix |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 21 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k practice_empty` on the base | xania crashes in skill_lookup (the known-bug check sees the crash) | pytest exit 0: 1 passed, 4 deselected in 39.38s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k practice_empty` on the branch | xania answers "You can't practice that." and survives (the known-bug check reports the bug gone) | pytest exit 1: 1 failed, 4 deselected in 45.44s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k cast_empty` on the base | xania crashes in skill_lookup via do_cast (the known-bug check sees the crash) | pytest exit 0: 1 passed, 4 deselected in 36.33s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k cast_empty` on the branch | xania survives cast '' (the known-bug check reports the bug gone) | pytest exit 1: 1 failed, 4 deselected in 31.97s |
| ✅ | Sim `skill bash --classes knight --fights 2` on the branch | it runs and finds no crash | no crash in 252 s (skill bash, kind combat skill, learned by knight 5) |
| ✅ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | 2 before, 0 after |

The new tests on the code **before** the change (the branch's tests applied to the base) and after it:

| Test | Before, Debug | Before, Release | After, Debug | After, Release |
|---|---|---|---|---|
| an empty skill name matches nothing | aborted | aborted | pass | pass |

<sub>g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake version 4.2.3; Ubuntu 26.04.1 LTS. Base `82171fa443`, branch `9c1d338865`.</sub>

## Not in this PR

- Xania Sim: retire the `cast ''` and `practice ''` known-bug checks once this is merged.
- Xania Explorer: a code check for `skill_lookup` without an empty guard.

---

**More detail:** the [full write-up](https://abraidotti.github.io/xania-builder/dossiers/issue-7-practice-at-a-trainer-reads-past/) has the root-cause analysis, every question the research asked and its answer, and the gate's logs. Researched and gated with [Xania Builder](https://github.com/abraidotti/xania-builder); players simulated with [Xania Sim](https://github.com/abraidotti/xania-sim).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
