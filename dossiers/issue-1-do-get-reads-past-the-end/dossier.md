# do_get reads past the end of "all": get all / autoloot crash debug builds, skip the undroppable guard in release (#1)

[#1](https://github.com/abraidotti/xania/issues/1) · Xania 82171fa443 · 2026-11-10 11:08

<details><summary>The idea as given</summary>

## Summary

`do_get` (`src/act_obj.cpp`) still indexes its first argument the way the old C code indexed a NUL-terminated
buffer: `arg1[3]` to tell `get all` from `get all.<name>`, and `&arg1[4]` for the name. `arg1` is now a
`std::string_view`, so for the plain `"all"` (3 characters) `arg1[3]` is out of range.

- **Debug builds abort** on the libstdc++ bounds assertion, taking the whole MUD down.
- **Release builds** don't crash but read whatever byte follows `all` in the input, so the checks that rely on
  it are wrong (see Impact).

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

## The faulty lines (`src/act_obj.cpp`)

| Line | Code | Problem when `arg1 == "all"` |
|---|---|---|
| 641 | `arg1[3] == '\0' \|\| is_name(&arg1[4], obj->name)` | `arg1[3]` out of range; `&arg1[4]` too (and for `"all."`, 4 chars) |
| 648 | `if (arg1[3] == '\0')` | out of range; runs whenever nothing was picked up, so an empty room always hits it |
| 651 | `act("I see no $T here.", ..., &arg1[4], ...)` | `&arg1[4]` is a `const char*` read up to the next NUL, past the end of the view |
| 707 | `is_mass_looting_npc_undroppable_obj(obj, container, arg1[3])` | out of range for `get all <container>`; for `get all.<name> <container>` the prefix has already been removed (line 688), so `arg1[3]` is the 4th character of the name |

## Impact

- **Debug builds:** any `get all` that finds nothing, and every autoloot of a non-empty corpse, aborts the MUD.
- **Release builds:** no crash, but `arg1[3]` reads the next byte of the command line instead of a terminator:
  - `is_mass_looting_npc_undroppable_obj` gets `' '` instead of `'\0'` for `get all corpse`, so the guard against
    mass-looting undroppable items from NPC corpses (`looting_all_item_dot == '\0'`) **never applies**: `get all
    corpse` and autoloot take undroppable (`NoDrop`/`NoRemove`) items.
  - Lines 641/651 work only when the byte after `all` happens to be a NUL, which depends on how the command line
    is stored.

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
gdb, and the crash reproduces with `python -m xania_sim hunt --mob "angry cave beast"`. Case 1 was spotted in the code
next to it and confirmed the same way (a bot typing `get all` in an empty room).

</details>

## Focus

- `loot_and_sacrifice_corpse` (src/fight.cpp:559, 22 lines): src/fight.cpp:565 is in it
- `do_get` (src/act_obj.cpp:613, 115 lines): src/act_obj.cpp:648 is in it
- `is_mass_looting_npc_undroppable_obj` (src/act_obj.cpp:426, 4 lines): named in the idea
- Commands: `get`, `take`

## 1. Explorer insights

- No Explorer bug check, assessment or recommendation touches the focus.

**To decide**

- [ ] No Explorer code check covers this. Should one be added for the faulty pattern, so other places with it show up and the fix shows as `fixed`?
- [ ] Should the change also turn an open Explorer bug check to `fixed` (a code check matches the faulty pattern, so the fix should make it disappear)?

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

**To decide**

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
- Sim finding `crash:SIGABRT:act_obj.cpp:do_get` [new, seen 5x]: xania crashed (SIGABRT, failed assertion) in do_get (act_obj.cpp) (https://github.com/abraidotti/xania/issues/1)

**To decide**

- [ ] Which unit test pins the fixed behaviour (a test that fails before the change)?
- [ ] Which Sim trial or scenario shows it from a player's side, and should a new one be added?

## Gate plan

What `prototype` runs on the fork before this can ship:

- Builds: debug, asan
- Unit tests: `src/test/act_obj_test.cpp`
- Sim: `smoke`: the game still boots and a player can log in
- Sim: `hunt --minutes 5`: fights and what runs after a kill (autoloot) reach it
- Sim: `pytest scenarios/test_live_bugs.py`: it sends the commands involved
- Regression: Sim finding `crash:SIGABRT:act_obj.cpp:do_get` should stop reproducing (https://github.com/abraidotti/xania/issues/1)
