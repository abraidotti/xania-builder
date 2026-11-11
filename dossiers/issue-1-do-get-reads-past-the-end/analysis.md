# Analysis: do_get reads past the end of "all" (#1)

Written by whoever made the change (here, Claude Code working from the dossier), answering the dossier's questions.
The facts it cites are in [dossier.md](dossier.md); the proof is in [gate.md](gate.md).

## In one paragraph

`do_get` decides between `get all` and `get all.<name>` by looking at `arg1[3]`, the character after "all". That
worked when `arg1` was a NUL-terminated `char[]`: `arg1[3]` was the terminator or the dot. In December 2021 `arg1`
became a `std::string_view`, which has no terminator, so for the 3-character view `"all"` the read is past the end:
undefined behaviour. Release builds read the next byte of the command line (a space, in `get all corpse`), so the
guard that keeps autoloot from taking undroppable items has **never worked in release since then**. Debug builds
didn't notice either, until the project moved to GCC 15 on 2026-10-31, whose standard library checks
`operator[]` in unoptimised builds: from then on every autoloot of a non-empty corpse aborts a debug MUD. The fix
decides "all" or "all.name" once, as named booleans, and passes the intent to the guard instead of a character.

## Root cause

The timeline, from section 8 of the dossier and the commits it points at:

| When | Commit | What happened |
|---|---|---|
| 2021-04-16 | `5e72201` | The guard is added: *"'get all corpse' including the autoloot feature no longer auto loots NODROP or NOREMOVE items (NPC corpses only)... to prevent accidental looting"*. `arg1` is a `char[MAX_INPUT_LENGTH]`; `arg1[3]` is `'\0'` for `all` and `'.'` for `all.x`. Correct. |
| 2021-12-03 | `35c8f3a` | *"get, put, freeze & gain commands upgraded to ArgParser or string_view"*. `arg1` becomes `args.shift()`, a view. The container branch's own checks are converted to `is_all` / `is_all_named`, but the room branch (lines 641, 648, 651) and the guard's argument (line 707) keep reading `arg1[3]`. From here on it's undefined behaviour. |
| 2026-10-31 | `82823ff`, `7bd8c82` | g++-15 becomes the default compiler, locally and in CI. GCC 15's libstdc++ defines `_GLIBCXX_ASSERTIONS` whenever optimisation is off ([GCC bug 112808](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=112808), "Done for GCC 15"), so Debug builds start aborting on the out-of-range read. |
| 2026-11-08 | | Xania Sim's bots, playing a debug build with autoloot on, crash it within minutes. Filed as #1. |

### Why debug builds abort and release builds don't

Checked directly with g++ 15.2 on a 10-line program that indexes `std::string_view("all corpse", 3)` at 3:

| Flags | Result |
|---|---|
| `-O0` (what `BUILD_TYPE=Debug` compiles with) | `Assertion '__pos < this->_M_len' failed`, abort |
| `-O0 -fsanitize=address,undefined` (Xania's Debug flags) | the same assertion: it's libstdc++, not the sanitizers, that catches it |
| `-O0 -D_GLIBCXX_NO_ASSERTIONS -fsanitize=address,undefined` | prints 32 (a space). **ASan and UBSan don't see it**: the byte is inside the command-line buffer, so it isn't an out-of-bounds access as far as memory goes |
| `-O2` (Release) | prints 32 |

So it is undefined behaviour in every build, as suspected; the assertion only makes it visible. The
`/usr/include/x86_64-linux-gnu/c++/15/bits/c++config.h` lines that do it:

```cpp
# elif ! defined(__OPTIMIZE__) && ! defined(_GLIBCXX_NO_ASSERTIONS)
// Enable assertions for unoptimized builds.
#  define _GLIBCXX_ASSERTIONS 1
```

### What each faulty line did, in release

- **707**, `get all corpse` and autoloot: the guard got `' '` instead of `'\0'`, so it never refused anything. Every
  `NODROP` and `NOREMOVE` item on an NPC corpse was looted. The gate's before/after table shows it: on the base, in
  Release, the new test finds the ring and the axe in the player's inventory.
- **707**, `get all.<name> corpse`: by then `arg1` has had `"all."` removed, so `arg1[3]` was the 4th character of
  the name. For names of 4 or more characters that's not `'\0'`, so named looting was allowed (by luck). For
  shorter names (`get all.bo corpse`) it read past the end again. The issue missed this one; the dossier's detector
  found it.
- **641, 648, 651**, `get all` / `get all.<name>` in a room: these read the byte after the view; they worked when it
  happened to be a NUL (a command typed alone on the line), and `&arg1[4]` was a `const char*` read up to the next NUL.

## The fix

```cpp
// "all" takes everything; "all.<name>" takes everything called <name>, and arg1 becomes just the <name>.
const auto is_all = matches(arg1, "all");
const auto is_all_named = matches_start("all.", arg1);
if (is_all_named)
    arg1.remove_prefix(4);
```

hoisted above the room/container split, so both branches use the same two booleans; the room branch then uses
`is_all` and `arg1` (the name) exactly as the container branch already did after `35c8f3a`. The guard takes the
intent instead of a character:

```cpp
bool is_mass_looting_npc_undroppable_obj(const Object *obj, const Object *container, const bool is_unnamed_all)
...
if (is_mass_looting_npc_undroppable_obj(obj, container, is_all)) {
```

That finishes the conversion `35c8f3a` started, in the idioms it chose (section 3 of the dossier: `do_get` already
had `is_all = matches(arg1, "all")` and `is_all_named = matches_start("all.", arg1)`; the fix moves them up rather
than adding a third way). `src/act_obj.cpp` changes by 14 lines added and 13 removed, two of the added lines being
comments that say what "all" and the guard mean.

### Alternatives considered

- **Bounds-checked reads** (`arg1.size() > 3 && arg1[3] == '.'`): keeps the C-string reasoning that caused the
  bug, and leaves three different ways of asking "is it all?" in one function. Rejected.
- **Only fix line 707** (the crash Sim found first): leaves the empty-room crash (648) and the short-name read.
  Rejected; the detector lists all five, and they're the same mistake.
- **Disable the libstdc++ assertions** (`-D_GLIBCXX_NO_ASSERTIONS`): hides the symptom, keeps the UB and the dead
  guard. The assertions are doing their job; nobody should do this.
- **Rewrite `do_get`** (115 lines, the dossier flags it as long): out of scope for a bug fix; would make review harder.

## Answers to the dossier's questions

**1. Explorer.** Xania Explorer's Bugs page has a check for this pattern (`code.get-all-past-end`), added while the
issue was filed; it lists the faulty lines in `do_get` and will show them as fixed once this is merged.

**2. Architecture.** The change is local to `do_get` and its file-local helper. The only automatic caller,
`loot_and_sacrifice_corpse` (autoloot), passes `"all corpse"` and now gets the behaviour `5e72201` intended. No
other caller of the helper exists.

**3. Design patterns.** It follows the idiom already in the function (named booleans from `matches` /
`matches_start`, `remove_prefix`). No new helper was needed.

**4. Technical debt.** Pays down all five C-string reads in the focus (the gate's detector step: 5 before, 0
after) and removes a duplicated `is_all` computation. Leaves `do_get`'s length alone. The same pattern elsewhere in
`src/` (dossier section 4), place by place:
- `MudImpl::nanny` (6 places): one is guarded (`GetAnsi`); the other five are real, filed as #3, separate PR.
- `do_who` `arg[0]`, `do_permit` `player[0]`: guarded (an `empty()` check comes first); false positives. The
  detector should learn about guards.
- `skill_lookup` `name[0]`: **a real bug, confirmed since and filed as #7.** `do_practice` passes `args.shift()`
  after checking only `args.empty()`, and `practice ''` at a trainer shifts an empty view (ArgParser strips the
  quotes), so it reads past the end. A Sim known-bug check crashes a debug MUD with it. Its own change, not this one.

**5. Gameplay.** Debug builds: no more aborts on `get all` or autoloot. **Release builds (the live game): players
will notice a change**: `get all corpse` and autoloot now leave `NODROP`/`NOREMOVE` items on NPC corpses, with
*"You refrain from looting $p as it appears to be undroppable. You can still 'get' it using its name."*, as the
original feature meant to. Named looting (`get ring corpse`, `get all.ring corpse`) still takes them. Nothing to
abuse: the change only takes away an unintended pickup. Explorer's balance models don't read `act_obj.cpp`.

**6. Documentation.** The help entry `DROP GET GIVE PUT TAKE` doesn't describe the guard; the in-game message
explains it when it happens. No help change. The PR says the release behaviour changes.

**7. Tests.** New `src/test/GetTest.cpp`, 2 test cases and 10 sections, driving `do_get` itself on `MockMud`: empty
room (`all`, `all.sword`, `all.`), picking up, the corpse guard (`NODROP`, `NOREMOVE`, a plain item), named looting,
a short name, and a container (not a corpse) that isn't guarded. On the base they abort the Debug build and fail in
Release (the gate's before/after table); on the branch they pass in both. From the player's side: Sim's
known-bug scenario (a bot types `get all` in an empty room) crashes the base and no longer crashes the branch, and
a 5-minute `hunt` (four bots killing cave beasts with autoloot on) runs clean on the branch. The hunt isn't used as
proof on the base: the guard's read only happens for a corpse with something in it, and cave beasts rarely carry
anything (the first gate run saw 16 kills on the base without a crash). The corpse path's proof is the unit test.

**8. History.** Answered under Root cause. Upstream has no issue or PR about it (the search finds only upstream #72, a
different autoloot bug, closed).

## Follow-ups (not in this PR)

- Xania Sim: retire `test_get_all_in_an_empty_room_crashes_debug_builds` once this is merged (it asks to be).
- Builder: teach the string_view detector about `empty()` guards (2 false positives here).
- #7, `practice ''`: the same family, found by the same detector; its own PR.
