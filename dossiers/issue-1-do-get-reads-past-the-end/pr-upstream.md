`do_get` decides between `get all` and `get all.<name>` by looking at `arg1[3]`, the character after "all". That worked when `arg1` was a NUL-terminated `char[]`: `arg1[3]` was the terminator or the dot. In December 2021 `arg1` became a `std::string_view`, which has no terminator, so for the 3-character view `"all"` the read is past the end: undefined behaviour. Release builds read the next byte of the command line (a space, in `get all corpse`), so the guard that keeps autoloot from taking undroppable items has **never worked in release since then**. Debug builds didn't notice either, until the project moved to GCC 15 on 2026-10-31, whose standard library checks `operator[]` in unoptimised builds: from then on every autoloot of a non-empty corpse aborts a debug MUD. The fix decides "all" or "all.name" once, as named booleans, and passes the intent to the guard instead of a character.

Reported as abraidotti/xania#1 (with the reproduction).

## What was wrong

| When | Commit | What happened |
|---|---|---|
| 2021-04-16 | `5e72201` | The guard is added: *"'get all corpse' including the autoloot feature no longer auto loots NODROP or NOREMOVE items (NPC corpses only)... to prevent accidental looting"*. `arg1` is a `char[MAX_INPUT_LENGTH]`; `arg1[3]` is `'\0'` for `all` and `'.'` for `all.x`. Correct. |
| 2021-12-03 | `35c8f3a` | *"get, put, freeze & gain commands upgraded to ArgParser or string_view"*. `arg1` becomes `args.shift()`, a view. The container branch's own checks are converted to `is_all` / `is_all_named`, but the room branch (lines 641, 648, 651) and the guard's argument (line 707) keep reading `arg1[3]`. From here on it's undefined behaviour. |
| 2026-10-31 | `82823ff`, `7bd8c82` | g++-15 becomes the default compiler, locally and in CI. GCC 15's libstdc++ defines `_GLIBCXX_ASSERTIONS` whenever optimisation is off ([GCC bug 112808](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=112808), "Done for GCC 15"), so Debug builds start aborting on the out-of-range read. |
| 2026-11-08 | | Xania Sim's bots, playing a debug build with autoloot on, crash it within minutes. Filed as abraidotti/xania#1. |

<details><summary>Why debug builds abort and release builds don't</summary>

Checked directly with g++ 15.2 on a 10-line program that indexes `std::string_view("all corpse", 3)` at 3:

| Flags | Result |
|---|---|
| `-O0` (what `BUILD_TYPE=Debug` compiles with) | `Assertion '__pos < this->_M_len' failed`, abort |
| `-O0 -fsanitize=address,undefined` (Xania's Debug flags) | the same assertion: it's libstdc++, not the sanitizers, that catches it |
| `-O0 -D_GLIBCXX_NO_ASSERTIONS -fsanitize=address,undefined` | prints 32 (a space). **ASan and UBSan don't see it**: the byte is inside the command-line buffer, so it isn't an out-of-bounds access as far as memory goes |
| `-O2` (Release) | prints 32 |

So it is undefined behaviour in every build, as suspected; the assertion only makes it visible. The `/usr/include/x86_64-linux-gnu/c++/15/bits/c++config.h` lines that do it:

```cpp
# elif ! defined(__OPTIMIZE__) && ! defined(_GLIBCXX_NO_ASSERTIONS)
// Enable assertions for unoptimized builds.
#  define _GLIBCXX_ASSERTIONS 1
```

</details>

## The fix

```cpp
// "all" takes everything; "all.<name>" takes everything called <name>, and arg1 becomes just the <name>.
const auto is_all = matches(arg1, "all");
const auto is_all_named = matches_start("all.", arg1);
if (is_all_named)
    arg1.remove_prefix(4);
```

hoisted above the room/container split, so both branches use the same two booleans; the room branch then uses `is_all` and `arg1` (the name) exactly as the container branch already did after `35c8f3a`. The guard takes the intent instead of a character:

```cpp
bool is_mass_looting_npc_undroppable_obj(const Object *obj, const Object *container, const bool is_unnamed_all)
...
if (is_mass_looting_npc_undroppable_obj(obj, container, is_all)) {
```

That finishes the conversion `35c8f3a` started, in the idioms it chose (section 3 of the dossier: `do_get` already had `is_all = matches(arg1, "all")` and `is_all_named = matches_start("all.", arg1)`; the fix moves them up rather than adding a third way). `src/act_obj.cpp` changes by 14 lines added and 13 removed, two of the added lines being comments that say what "all" and the guard mean.

<details><summary>Alternatives considered</summary>

- **Bounds-checked reads** (`arg1.size() > 3 && arg1[3] == '.'`): keeps the C-string reasoning that caused the bug, and leaves three different ways of asking "is it all?" in one function. Rejected.
- **Only fix line 707** (the crash Sim found first): leaves the empty-room crash (648) and the short-name read. Rejected; the detector lists all five, and they're the same mistake.
- **Disable the libstdc++ assertions** (`-D_GLIBCXX_NO_ASSERTIONS`): hides the symptom, keeps the UB and the dead guard. The assertions are doing their job; nobody should do this.
- **Rewrite `do_get`** (115 lines, the dossier flags it as long): out of scope for a bug fix; would make review harder.

</details>

## What players will notice

Debug builds: no more aborts on `get all` or autoloot. **Release builds (the live game): players will notice a change**: `get all corpse` and autoloot now leave `NODROP`/`NOREMOVE` items on NPC corpses, with *"You refrain from looting $p as it appears to be undroppable. You can still 'get' it using its name."*, as the original feature meant to. Named looting (`get ring corpse`, `get all.ring corpse`) still takes them. Nothing to abuse: the change only takes away an unintended pickup. Explorer's balance models don't read `act_obj.cpp`.

## Verification

Run by Xania Builder's gate, in the same configurations CI uses (Debug, which here means ASan + UBSan + libstdc++ assertions, and Release -O2):

| | Check | Expected | Result |
|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean |
| ✅ | Debug build of the branch | it compiles (-Werror) | built in 0 s |
| ✅ | Unit tests, Debug, the branch | every test passes | 1083 test cases and sections, all passed |
| ✅ | Release build of the branch | it compiles (-Werror) | built in 0 s |
| ✅ | Unit tests, Release, the branch | every test passes | 1083 test cases and sections, all passed |
| ✅ | Debug build of the base with the branch's tests | it compiles (-Werror) | built in 10 s |
| ✅ | Release build of the base with the branch's tests | it compiles (-Werror) | built in 7 s |
| ✅ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | 2 of 2 new tests pin the fix |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 21 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k get_all` on the base | xania crashes when a bot types 'get all' in an empty room (the known-bug check sees the crash) | pytest exit 0: 1 passed, 1 deselected in 38.81s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k get_all` on the branch | xania survives it (the known-bug check reports the bug gone and asks to be retired) | pytest exit 1: 1 failed, 1 deselected in 34.89s |
| ✅ | Sim `hunt --minutes 5` on the branch | it runs and finds no crash | no crash in 308 s (fights 16, bot errors 0, crashed False) |
| ✅ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | 5 before, 0 after |

The new tests on the code **before** the change (the branch's tests applied to the base) and after it:

| Test | Before, Debug | Before, Release | After, Debug | After, Release |
|---|---|---|---|---|
| get all and get all.<name> in a room | aborted | pass | pass | pass |
| get all from an NPC corpse leaves undroppable items unless named | aborted | fail | pass | pass |

<sub>g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake version 4.2.3; Ubuntu 26.04.1 LTS. Base `82171fa443`, branch `515b3001ab` (this PR's `1ee9edf4d3` has the same code, with its history squashed).</sub>

The same change went through the fork first, where this repo's own CI (format, Debug and Release build and test) passed: https://github.com/abraidotti/xania/pull/4.

## Not in this PR

- Xania Sim: retire `test_get_all_in_an_empty_room_crashes_debug_builds` once this is merged (it asks to be).
- Xania Explorer: the `code.get-all-past-end` check.
- Builder: teach the string_view detector about `empty()` guards (2 false positives here).
- Check the `practice ''` lead with Sim.

---

**More detail:** the [full write-up](https://abraidotti.github.io/xania-builder/dossiers/issue-1-do-get-reads-past-the-end/) has the root-cause analysis, every question the research asked and its answer, and the gate's logs. Researched and gated with [Xania Builder](https://github.com/abraidotti/xania-builder); players simulated with [Xania Sim](https://github.com/abraidotti/xania-sim).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
