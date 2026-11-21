# compare counts only weapon dice and three armor values (upstream #144): do_compare in act_info.cpp i

Xania eec205e5fd · 2026-11-20 21:36

<details><summary>The idea as given</summary>

compare counts only weapon dice and three armor values (upstream #144): do_compare in act_info.cpp ignores damroll, hitroll, AC vs magic, AC affects and every other stat, and can't compare rings or amulets

</details>

## Focus

- `do_compare` (src/act_info.cpp:1352, 62 lines): named with --symbol
- `find_comparable` (src/act_info.cpp:1341, 9 lines): named with --symbol
- Commands: `compare`

## 1. Explorer insights

- No Explorer bug check, assessment or recommendation touches the focus.

**To decide**

- [ ] No Explorer code check covers this. Should one be added for the faulty pattern, so other places with it show up and the fix shows as `fixed`?

## 2. Architecture

- `do_compare` is defined at src/act_info.cpp:1352-1413 (62 lines): `void do_compare(Char *ch, ArgParser args)`
- `do_compare` handles the command(s) `compare` (minimum position Resting, src/InterpreterImpl.cpp:133)
- `do_compare` calls `act` (7 definitions), `empty` (3 definitions), `find_comparable`, `find_in_inventory`, `send_line` (2 definitions), `shift`
- `find_comparable` is defined at src/act_info.cpp:1341-1349 (9 lines): `Object *find_comparable(Char *ch, Object *obj_to_compare_to)`
- Called from `do_compare` (src/act_info.cpp:1352)
- `find_comparable` calls `can_see` (4 definitions), `to_int` (19 definitions)
- `src/act_info.cpp`: 1754 lines, 83 functions

**To decide**

- [ ] Is the change local to these functions, or does the fix belong in a shared helper their callers use too?
- [ ] Does every caller (including automatic ones) still get the behaviour it expects?

## 3. Design patterns

- In `do_compare`: ArgParser x1 (modern), std::string_view x1 (modern), act() x1 (either)
- 140 other functions share the signature `(Char *ch, ArgParser args)`; in the same file: `do_consider`, `do_examine`, `do_look`, `do_password`, `do_peek`, `do_practice`, `do_scroll`, `do_where` and 3 more
- In `find_comparable`: range-for over contents x1 (modern)
- Across src/: act() 779, std::string_view 626, ArgParser 402, matches()/matches_start() 289, range-for over contents 267, fmt::format 211, sprintf/strcpy/strcat 19, '\0' terminator checks 13, char buffers 10

**To decide**

- [ ] Which existing idiom does the change follow, and does it leave the function more consistent?
- [ ] Is there a helper already (in the same file or a header) that does what the change needs?

## 4. Technical debt

- `do_compare` is 62 lines long (src/ median 7).
- TODO at src/act_info.cpp:1198: can or should this be part of all_visible_to?
- TODO at src/act_info.cpp:1257: this could be much better phrased

**To decide**

- [ ] Are the other places with the same pattern the same bug, and do they belong in this change?
- [ ] What debt does the change pay down while it's here, and what does it deliberately leave?
- [ ] Does the change add any (a special case, a duplicated check, a new legacy idiom)?

## 5. Gameplay

- Players reach this with `compare` (from position Resting up).
- Messages `do_compare` can show: "Compare what to what?"; "You do not have that item."; "You aren't wearing anything comparable."; "You do not have that item."; "You compare $p to itself.  It looks about the same."; "You can't compare $p and $P."; "You can't compare $p and $P."; "$p and $P look about the same."; "$p looks better than $P."; "$p looks worse than $P."
- Balance numbers Explorer models from these files: none (the change is behaviour, not balance; Explorer's predictions shouldn't move)

**To decide**

- [ ] What does a player notice before and after (messages, what they get, what's refused)?
- [ ] Can a careless or abusive player use the change (or the old behaviour) to their advantage?
- [ ] Does it change balance for any class, race or level range? If so, which Explorer numbers?

## 6. Documentation

- Help `COMPARE` (area/Help.are:503, level 0): Syntax: compare <object-1> <object-2>

**To decide**

- [ ] Does any help entry describe the behaviour being changed, and does it need rewording?
- [ ] Does the change need a note anywhere else (README, release notes, an issue comment)?

## 7. Test coverage

- No unit test file for `src/act_info.cpp`.
- No unit test calls `do_compare`.
- No unit test calls `find_comparable`.

**To decide**

- [ ] Which unit test pins the fixed behaviour (a test that fails before the change)?
- [ ] Which Sim trial or scenario shows it from a player's side, and should a new one be added?

## 8. History

- `do_compare` (62 lines) comes from 7 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (28 lines); `72fd9ec` (2020-10-04, Matt Godbolt): New iteration-safe list (#233) (15 lines); `7a71102` (2020-07-22, Matt Godbolt): Reformat all the code with clang-format (9 lines); `a2c31f5` (2020-09-02, Matt Godbolt): Formatting changes. (4 lines)
- `find_comparable` (9 lines) comes from 4 commits; the most: `72fd9ec` (2020-10-04, Matt Godbolt): New iteration-safe list (#233) (6 lines); `e0683fb` (2021-07-03, snellers): merc.h cleanup: move OBJ_DATA to Object.hpp and rename to Object. (1 lines); `1880bb1` (2023-08-22, snellers): Rename some member and arguments from wear to worn. (1 lines); `cb7a68a` (2021-10-26, snellers): Macro death: convert ITEM_WEAR_ flags to ObjectWearFlag. (1 lines)
- Debug builds add `-fno-omit-frame-pointer -fsanitize=leak -fsanitize=address -fsanitize=undefined`
- Release builds add `-O2 -DNDEBUG -Wno-error=array-bounds`
- Upstream issue [#144](https://github.com/mattgodbolt/xania/issues/144) (open): comp command compares the damage on the weapon but not the additional stats (mentions `do_compare`)

**To decide**

- [ ] When did the behaviour start, and why did nobody notice until now?
- [ ] Did a toolchain change (compiler, flags, sanitizers) make it show, or change how it shows?
- [ ] Has upstream seen or tried this before, and does the change fit what was decided then?

## Gate plan

What `prototype` runs on the fork before this can ship:

- Builds: Debug (ASan, UBSan, LSan, libstdc++ assertions), Release (-O2)
- Unit tests: the whole suite
- Sim: `smoke`: the game still boots and a player can log in
