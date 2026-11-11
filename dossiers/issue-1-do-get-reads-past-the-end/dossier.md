# do_get reads past the end of "all": get all / autoloot crash debug builds, skip the undroppable guard in release (#1)

[#1](https://github.com/abraidotti/xania/issues/1) · Xania 82171fa443 · 2026-11-11 14:10

<details><summary>The idea as given</summary>

## Summary

`do_get` (`src/act_obj.cpp`) still indexes its first argument the way the old C code indexed a NUL-terminated
buffer: `arg1[3]` to tell `get all` from `get all.<name>`, and `&arg1[4]` for the name. `arg1` is now a
`std::string_view`, so for the plain `"all"` (3 characters) `arg1[3]` is out of range.

- **Debug builds abort** on the libstdc++ bounds assertion, taking the whole MUD down: any `get all` that finds
  nothing, and every autoloot of a non-empty corpse.
- **Release builds** don't crash, but `arg1[3]` reads the next byte of the command line instead of a terminator:
  - `is_mass_looting_npc_undroppable_obj` gets `' '` instead of `'\0'` for `get all corpse`, so the guard against
    mass-looting undroppable items from NPC corpses (`looting_all_item_dot == '\0'`) **never applies**: `get all
    corpse` and autoloot take undroppable (`NoDrop`/`NoRemove`) items.
  - Lines 641/651 work only when the byte after `all` happens to be a NUL, which depends on how the command line
    is stored.

Present at `82171fa` (current `main` of both this fork and mattgodbolt/xania).

## How to reproduce

Either of these crashes a debug build (`make`, the default `BUILD_TYPE=Debug`):

1. Type `get all` in a room with nothing in it.
2. Kill a mob that carries something, with autoloot on (the default for new characters). Autoloot calls
   `do_get(looter, ArgParser("all corpse"))` from `loot_and_sacrifice_corpse` (`src/fight.cpp:565`). A level-1
   character killing an angry cave beast in Mud School (room 3713) does it within a couple of minutes.

```
/usr/include/c++/15/string_view:260: ... operator[](size_type) const ...: Assertion '__pos < this->_M_len' failed.
Program received signal SIGABRT, Aborted.
```

Backtrace for case 2:

```
#6  std::basic_string_view<char>::operator[] (__pos=3) at /usr/include/c++/15/string_view:260
#7  do_get (ch=..., args=...) at src/act_obj.cpp:707
#8  loot_and_sacrifice_corpse (looter=..., victim=..., victim_room_vnum=3713) at src/fight.cpp:565
#9  damage (ch=..., victim=..., raw_damage=2, ...) at src/fight.cpp:813
#10 one_hit (...) at src/fight.cpp:535
#11 multi_hit (...) at src/fight.cpp:263
#13 violence_update () at src/fight.cpp:110
#14 update_handler (mud=...) at src/update.cpp:874
#15 MudImpl::game_loop (...) at src/MudImpl.cpp:332
```

Case 1 stops at `do_get ... at src/act_obj.cpp:648`.

## Faulty lines

All in `src/act_obj.cpp`:

| Line | Code | Problem when `arg1 == "all"` |
|---|---|---|
| 641 | `arg1[3] == '\0' \|\| is_name(&arg1[4], obj->name)` | `arg1[3]` out of range; `&arg1[4]` too (and for `"all."`, 4 chars) |
| 648 | `if (arg1[3] == '\0')` | out of range; runs whenever nothing was picked up, so an empty room always hits it |
| 651 | `act("I see no $T here.", ..., &arg1[4], ...)` | `&arg1[4]` is a `const char*` read up to the next NUL, past the end of the view |
| 707 | `is_mass_looting_npc_undroppable_obj(obj, container, arg1[3])` | out of range for `get all <container>`; for `get all.<name> <container>` the prefix has already been removed (line 688), so `arg1[3]` is the 4th character of the name |

## Suggested fix

Decide "all" vs "all.name" once, and pass that intent instead of a character:

```cpp
// 'get all' or 'get all.obj' (in the room)
const auto is_all = matches(arg1, "all");
const auto named = is_all ? std::string_view{} : arg1.substr(4);  // after "all."
found = false;
for (auto *obj : ch->in_room->contents) {
    if ((is_all || is_name(named, obj->name)) && ch->can_see(*obj)) {
        found = true;
        get_obj(ch, obj, nullptr);
    }
}
if (!found) {
    if (is_all)
        ch->send_line("I see nothing here.");
    else
        act("I see no $T here.", ch, nullptr, named, To::Char);
}
```

```cpp
bool is_mass_looting_npc_undroppable_obj(const Object *obj, const Object *container, const bool unnamed_all) {
    return container->type == ObjectType::Npccorpse && unnamed_all && (obj->is_no_drop() || obj->is_no_remove());
}
// line 707:
if (is_mass_looting_npc_undroppable_obj(obj, container, is_all)) {
```

Tests worth adding (there's `MockMud` in `src/test/`):

- `get all` in an empty room says "I see nothing here." (and doesn't abort a debug build);
- `get all corpse` on an NPC corpse holding a `NoDrop` item leaves that item behind, while `get <item> corpse`
  takes it;
- `get all.sword corpse` takes a `NoDrop` sword (named looting is allowed).

## How this was found

Bots from [xania-sim](https://github.com/abraidotti/xania-sim) playing a debug build: its test MUD runs xania under
gdb, and the crash reproduces with `python -m xania_sim hunt --mob "angry cave beast"`. Case 1 was spotted in the
code next to it and confirmed the same way (a bot typing `get all` in an empty room). A check for it
(`code.get-all-past-end`) is on its way to Xania Explorer's Bugs page, where it will turn to "fixed" once these
lines change.

</details>

## Focus

- `loot_and_sacrifice_corpse` (src/fight.cpp:559, 22 lines): src/fight.cpp:565 is in it
- `do_get` (src/act_obj.cpp:613, 115 lines): src/act_obj.cpp:648 is in it
- `is_mass_looting_npc_undroppable_obj` (src/act_obj.cpp:426, 4 lines): named in the idea
- Commands: `get`, `take`

## 1. Explorer insights

- Bug check `code.get-all-past-end` (present, crash): `get all` and autoloot read past the end of "all". act_obj.cpp:641, act_obj.cpp:641, act_obj.cpp:648, act_obj.cpp:651, act_obj.cpp:707
- Bug check `code.vampiric-integer-drain` (present, wrong-behaviour): Vampiric weapons drain nothing from hits under 100 damage. fight.cpp:718, fight.cpp:719

**To decide**

- [ ] The fix should turn the code check above to `fixed` (it matches the faulty pattern). Does it, and are there other occurrences to fix at the same time?

## 2. Architecture

- Reported call path (innermost first): `do_get` (src/act_obj.cpp:707) <- `loot_and_sacrifice_corpse` (src/fight.cpp:565) <- `damage` (src/fight.cpp:813) <- `one_hit` (src/fight.cpp:535) <- `multi_hit` (src/fight.cpp:263) <- `violence_update` (src/fight.cpp:110) <- `update_handler` (src/update.cpp:874) <- `MudImpl::game_loop` (src/MudImpl.cpp:332)
- `loot_and_sacrifice_corpse` is defined at src/fight.cpp:559-580 (22 lines): `void loot_and_sacrifice_corpse(Char *looter, Char *victim, sh_int victim_room_vnum)`
- Called from `damage` (src/fight.cpp:586)
- `loot_and_sacrifice_corpse` calls `ArgParser` (3 definitions), `check_enum_bit`, `do_get`, `do_sacrifice`, `empty` (3 definitions), `get_obj_list`, `is_npc`, `is_pc`
- `do_get` is defined at src/act_obj.cpp:613-727 (115 lines): `void do_get(Char *ch, ArgParser args)`
- `do_get` handles the command(s) `get` (minimum position Resting, src/InterpreterImpl.cpp:104), `take` (minimum position Resting, src/InterpreterImpl.cpp:238)
- Called from `loot_and_sacrifice_corpse` (src/fight.cpp:559); so it also runs without a player typing it
- `do_get` calls `act` (7 definitions), `can_loot`, `can_see` (4 definitions), `check_enum_bit`, `empty` (3 definitions), `get_obj`, `get_obj_here`, `get_obj_list`, `is_mass_looting_npc_undroppable_obj`, `is_mortal`, `is_name`, `matches` (2 definitions) and 3 more
- `is_mass_looting_npc_undroppable_obj` is defined at src/act_obj.cpp:426-429 (4 lines): `bool is_mass_looting_npc_undroppable_obj(const Object *obj, const Object *container, const char looting_all_item_dot)`
- Called from `do_get` (src/act_obj.cpp:613)
- `is_mass_looting_npc_undroppable_obj` calls `is_no_drop`, `is_no_remove` (2 definitions)
- `src/fight.cpp`: 2498 lines, 47 functions
- `src/act_obj.cpp`: 2199 lines, 43 functions

**To decide**

- [ ] Is the change local to these functions, or does the fix belong in a shared helper their callers use too?
- [ ] Does every caller (including automatic ones) still get the behaviour it expects?

## 3. Design patterns

- In `loot_and_sacrifice_corpse`: ArgParser x3 (modern)
- In `do_get`: ArgParser x1 (modern), matches()/matches_start() x7 (modern), range-for over contents x2 (modern), act() x9 (either), '\0' terminator checks x2 (legacy)
- `do_get` mixes modern (ArgParser, matches()/matches_start(), range-for over contents) and legacy ('\0' terminator checks) idioms: the modern ones already in the function are the pattern to follow.
- `do_get` already names a test as a value: `is_all = matches(arg1, "all")`
- `do_get` already names a test as a value: `is_all_named = matches_start("all.", arg1)`
- 140 other functions share the signature `(Char *ch, ArgParser args)`; in the same file: `do_buy`, `do_donate`, `do_drink`, `do_drop`, `do_eat`, `do_fill`, `do_give`, `do_list` and 15 more
- In `is_mass_looting_npc_undroppable_obj`: '\0' terminator checks x1 (legacy)
- Across src/: act() 779, std::string_view 625, ArgParser 402, matches()/matches_start() 291, range-for over contents 267, fmt::format 211, sprintf/strcpy/strcat 19, '\0' terminator checks 14, char buffers 10

**To decide**

- [ ] Which existing idiom does the change follow, and does it leave the function more consistent?
- [ ] Is there a helper already (in the same file or a header) that does what the change needs?

## 4. Technical debt

- `do_get` indexes string_views like C strings (reading past the end when the view is that long, and never seeing a terminator): `arg1[3]` at src/act_obj.cpp:641, `&arg1[4]` at src/act_obj.cpp:641, `arg1[3]` at src/act_obj.cpp:648, `&arg1[4]` at src/act_obj.cpp:651, `arg1[3]` at src/act_obj.cpp:707
- `do_get` is 115 lines long (src/ median 7).
- Legacy idioms in `do_get`: '\0' terminator checks
- Legacy idioms in `is_mass_looting_npc_undroppable_obj`: '\0' terminator checks
- The same pattern elsewhere in src/ (11 places in 4 functions; each is the same kind of bug unless the view is known to be long enough): `do_who` `arg[0]` :1249; `do_permit` `player[0]` :95, `player[0]` :98; `skill_lookup` `name[0]` :39, `name[0]` :39; `nanny` `argument[0]` :711, `argument[0]` :740, `argument[0]` :762, `argument[0]` :854, `argument[0]` :890, `argument[0]` :915

**To decide**

- [ ] Are the other places with the same pattern the same bug, and do they belong in this change?
- [ ] What debt does the change pay down while it's here, and what does it deliberately leave?
- [ ] Does the change add any (a special case, a duplicated check, a new legacy idiom)?

## 5. Gameplay

- Players reach this with `get` (from position Resting up).
- Players reach this with `take` (from position Resting up).
- Messages `loot_and_sacrifice_corpse` can show: "all corpse"; "gold corpse"
- `do_get` also runs on its own from `loot_and_sacrifice_corpse` (src/fight.cpp:559): players who never type the command are affected too (e.g. through an auto setting).
- Messages `do_get` can show: "Get what?"; "I see no $T here."; "I see nothing here."; "I see no $T here."; "You can't do that."; "I see no $T here."; "That's not a container."; "You can't do that."; "The $d is closed."; "I see nothing like that in the $T." (+6)
- Balance numbers Explorer models from these files: none (the change is behaviour, not balance; Explorer's predictions shouldn't move)

**To decide**

- [ ] What does a player notice before and after (messages, what they get, what's refused)?
- [ ] Can a careless or abusive player use the change (or the old behaviour) to their advantage?
- [ ] Does it change balance for any class, race or level range? If so, which Explorer numbers?

## 6. Documentation

- Help `DROP GET GIVE PUT TAKE` (area/Help.are:467, level 0): Syntax: drop <object>

**To decide**

- [ ] Does any help entry describe the behaviour being changed, and does it need rewording?
- [ ] Does the change need a note anywhere else (README, release notes, an issue comment)?

## 7. Test coverage

- No unit test file for `src/fight.cpp`.
- `src/test/act_obj_test.cpp`: named after act_obj.cpp
- No unit test calls `loot_and_sacrifice_corpse`.
- No unit test calls `do_get`.
- No unit test calls `is_mass_looting_npc_undroppable_obj`.
- Sim `scenarios/test_live_bugs.py` sends `get`
- Sim `xania_sim/activities/loot.py` sends `get`
- Sim finding `crash:SIGABRT:act_obj.cpp:do_get` [known, seen 9x]: xania crashed (SIGABRT, failed assertion) in do_get (act_obj.cpp) (https://github.com/abraidotti/xania/issues/1)

**To decide**

- [ ] Which unit test pins the fixed behaviour (a test that fails before the change)?
- [ ] Which Sim trial or scenario shows it from a player's side, and should a new one be added?

## 8. History

- `arg1` is declared at src/act_obj.cpp:617, a line last changed in `35c8f3a` (2021-12-03, snellers): get, put, freeze & gain commands upgraded to ArgParser or string_view....
- `arg1[3]` at src/act_obj.cpp:641 was last changed in `5939d45` (2022-07-04, snellers): Remove can_see_obj().
- `&arg1[4]` at src/act_obj.cpp:641 was last changed in `5939d45` (2022-07-04, snellers): Remove can_see_obj().
- `arg1[3]` at src/act_obj.cpp:648 was last changed in `6f770fb` (2021-06-20, snellers): merc.h & xania.cpp cleanup: moving check_material_vulernability(), can_loot(), obj_move_violates_uniqueness() into act_obj.[ch]pp.
- `&arg1[4]` at src/act_obj.cpp:651 was last changed in `5216c9f` (2020-08-12, Matt Godbolt): act() refactor: introduce a strong type for "To"
- `arg1[3]` at src/act_obj.cpp:707 was last changed in `5e72201` (2021-04-16, snellers): 'get all corpse' including the autoloot feature no longer auto loots NODROP or NOREMOVE items (NPC corpses only).  Instead the looter and other chars in the room are warned. This is to prevent accidental looting of nodrop/noremove items.
- The conversion to string_view (or ArgParser): `35c8f3a` (2021-12-03, snellers): get, put, freeze & gain commands upgraded to ArgParser or string_view..... The indexing above has been on a view, with no terminator, since then
- `loot_and_sacrifice_corpse` (22 lines) comes from 8 commits; the most: `5db75c2` (2020-07-30, snellers): If a pet gets the killing blow, its owner is chosen as the autolooter. Resolves #60 (9 lines); `39ee043` (2021-10-25, snellers): Macro death: convert PLR_ act flags to PlayerActFlag. (6 lines); `35c8f3a` (2021-12-03, snellers): get, put, freeze & gain commands upgraded to ArgParser or string_view.... (2 lines); `b1c5588` (2020-08-29, Matt Godbolt): CHAR_DATA -> Char (1 lines)
- `do_get` (115 lines) comes from 16 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (41 lines); `35c8f3a` (2021-12-03, snellers): get, put, freeze & gain commands upgraded to ArgParser or string_view.... (17 lines); `6f770fb` (2021-06-20, snellers): merc.h & xania.cpp cleanup: moving check_material_vulernability(), can_loot(), obj_move_violates_uniqueness() into act_obj.[ch]pp. (13 lines); `5216c9f` (2020-08-12, Matt Godbolt): act() refactor: introduce a strong type for "To" (7 lines)
- `is_mass_looting_npc_undroppable_obj` (4 lines) comes from 4 commits; the most: `e0683fb` (2021-07-03, snellers): merc.h cleanup: move OBJ_DATA to Object.hpp and rename to Object. (1 lines); `49cb513` (2021-07-05, snellers): merc.h cleanup: ITEM_ type defines converted to ObjectType enum.... (1 lines); `88ff199` (2021-07-08, snellers): merc.h cleanup: replace IS_OBJ_STAT macro with object extra checker methods. (1 lines); `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (1 lines)
- Since 35c8f3a (2021-12-03), 26 commits changed the compiler or its flags; the latest: `7bd8c82` (2026-10-31, snellers): github action upgrade to Ubuntu 26.04 and g++-15; `82823ff` (2026-10-31, snellers): General tooling upgrades, largely for Ubuntu 26.04.1 compatibility conda 26.9.4-0 conan 2.33.0 cmake >= 3.31 g++-15 default, g++-13 fallback Compiles on ubunt 26.04.1; `425fd97` (2025-04-07, snellers): Docker: ubuntu 24 is the default these days. Install clang 19. Stop trying to install awscli as it's not in the ubuntu apt sources now. The session doesn't start tmux by default. [skip ci]; `e5483b6` (2025-03-28, snellers): Update g++ versions in README. Retire the g++ 10/11 toolchains.; `55c9b1b` (2025-03-28, snellers): github: upgrade to ubuntu 24 and use g++-13
- Debug builds add `-fno-omit-frame-pointer -fsanitize=leak -fsanitize=address -fsanitize=undefined`
- Release builds add `-O2 -DNDEBUG -Wno-error=array-bounds`
- Upstream PR [#307](https://github.com/mattgodbolt/xania/pull/307) (open): do_get: decide 'all' vs 'all.<name>' once instead of indexing past the end (mentions `do_get`, `is_mass_looting_npc_undroppable_obj`)
- Upstream issue [#72](https://github.com/mattgodbolt/xania/issues/72) (closed): The autoloot routine loot_and_sacrifice_corpse() has a chance it might target the wrong corpse. (mentions `loot_and_sacrifice_corpse`)

**To decide**

- [ ] When did the behaviour start, and why did nobody notice until now?
- [ ] Did a toolchain change (compiler, flags, sanitizers) make it show, or change how it shows?
- [ ] Has upstream seen or tried this before, and does the change fit what was decided then?

## Gate plan

What `prototype` runs on the fork before this can ship:

- Builds: Debug (ASan, UBSan, LSan, libstdc++ assertions), Release (-O2)
- Unit tests: `src/test/act_obj_test.cpp`
- Sim: `smoke`: the game still boots and a player can log in
- Sim: `hunt --minutes 5`: fights and what runs after a kill (autoloot) reach it
- Sim: `pytest scenarios/test_live_bugs.py`: it sends the commands involved
- Regression: Sim finding `crash:SIGABRT:act_obj.cpp:do_get` should stop reproducing (https://github.com/abraidotti/xania/issues/1)
