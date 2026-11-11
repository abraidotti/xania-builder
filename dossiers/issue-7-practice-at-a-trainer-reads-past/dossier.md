# practice '' at a trainer reads past the end of an empty skill name (debug builds abort) (#7)

[#7](https://github.com/abraidotti/xania/issues/7) · Xania 82171fa443 · 2026-11-11 15:16

<details><summary>The idea as given</summary>

## Summary

`practice ''` (or `practice ""`) at a trainer crashes a debug build. `ArgParser::shift()` strips the quotes and
returns an **empty** `std::string_view`; `do_practice` only checks that the line had arguments (`args.empty()`), not
that the one it shifted is non-empty, and passes it to `skill_lookup`, which reads `name[0]`.

- **Debug builds** (the default `BUILD_TYPE=Debug`) abort on the libstdc++ bounds assertion (on at `-O0` since GCC
  15), taking the MUD down for everyone connected. Any player with a practice session left can do it at any trainer.
- **Release builds** read the byte the empty view starts at: undefined behaviour. For `practice ''` the view sits on
  the closing quote, so `name[0]` reads `'`, which no skill name starts with, and the player is told "You can't
  practice that.", by luck.

Present at `82171fa` (current `main` of this fork and of mattgodbolt/xania). The same family as #1 and #3: a
`string_view` indexed as if it were a NUL-terminated C string.

## How to reproduce

On a debug build: create a character, walk to any trainer (a mob you can `practice` with), and type:

```
practice ''
```

```
/usr/include/c++/15/string_view:260: ... operator[](size_type) const ...: Assertion '__pos < this->_M_len' failed.
Program received signal SIGABRT, Aborted.
```

Call chain: `skill_lookup` (lookup.cpp:39) <- `do_practice` (act_info.cpp:1583) <- `Interpreter::Impl::interpret`
(InterpreterImpl.cpp:549) <- `MudImpl::game_loop` (MudImpl.cpp:318).

## Faulty lines

| File:line | Code | Problem |
|---|---|---|
| `src/lookup.cpp:39` | `tolower(name[0]) == tolower(skill_table[sn].name[0])` | `name[0]` on an empty view is out of range |
| `src/act_info.cpp:1583` | `auto sn = skill_lookup(args.shift());` | only `args.empty()` was checked (line 1565); `''` shifts to an empty view |
| `src/ArgParser.cpp:12-24` | quote handling in `shift()` | (not a bug) `''` becomes `""`: the quotes are stripped, so an empty argument is a normal result |

The other callers that take player input are safe: `do_sset` checks `skill_name.empty()`, and `do_slookup` is
passed the raw line (quotes included). The rest pass string literals.

## Suggested fix

In `skill_lookup` itself, since no skill has an empty name and it protects every caller:

```cpp
int skill_lookup(std::string_view name) {
    if (name.empty())
        return -1;
    ...
```

`do_practice` then answers "You can't practice that." as it does for any unknown skill. A unit test: `skill_lookup("")`
returns -1 (it aborts a debug build today), and `skill_lookup("sw")` still finds sword.

## How this was found

Xania Builder's string_view detector listed `skill_lookup`'s `name[0]` among "the same pattern elsewhere" while
researching #1 (see the [dossier](https://abraidotti.github.io/xania-builder/dossiers/issue-1-do-get-reads-past-the-end/#research)),
and #1's analysis noted it as an unverified lead. A new known-bug check in
[xania-sim](https://github.com/abraidotti/xania-sim) (`pytest scenarios/test_live_bugs.py -k practice_empty`) then
confirmed it on an isolated debug MUD: a bot walks to the nearest trainer, practises once to prove the trainer is
there, and types `practice ''`.

</details>

## Focus

- `skill_lookup` (src/lookup.cpp:33, 14 lines): lookup.cpp:39 is in it
- `do_practice` (src/act_info.cpp:1561, 56 lines): act_info.cpp:1583 is in it
- `Interpreter::Impl::interpret` (src/InterpreterImpl.cpp:495, 56 lines): InterpreterImpl.cpp:549 is in it
- `MudImpl::game_loop` (src/MudImpl.cpp:180, 180 lines): MudImpl.cpp:318 is in it
- `ArgParser::shift` (src/ArgParser.cpp:5, 25 lines): src/ArgParser.cpp:12 is in it
- `do_sset` (src/act_wiz.cpp:1914, 40 lines): named in the idea
- `do_slookup` (src/act_wiz.cpp:1857, 19 lines): named in the idea
- Commands: `practice`

## 1. Explorer insights

- Bug check `code.lobby-empty-reply` (present, crash): An empty reply at a login prompt crashes debug builds. MudImpl.cpp:711, MudImpl.cpp:740, MudImpl.cpp:854, MudImpl.cpp:890, MudImpl.cpp:915

**To decide**

- [ ] The fix should turn the code check above to `fixed` (it matches the faulty pattern). Does it, and are there other occurrences to fix at the same time?

## 2. Architecture

- `skill_lookup` is defined at src/lookup.cpp:33-46 (14 lines): `int skill_lookup(std::string_view name)`
- Called from `do_lore` (src/act_info.cpp:700), `do_practice` (src/act_info.cpp:1561), `do_coma` (src/act_wiz.cpp:1745), `do_slookup` (src/act_wiz.cpp:1857), `do_sset` (src/act_wiz.cpp:1914), `try_fread_spnumber` (src/db.cpp:1310), `accept_invitation` (src/Duel.cpp:64), `one_hit` (src/fight.cpp:410), `do_berserk` (src/fight.cpp:1596), `enforce_material_vulnerability` (src/handler.cpp:408), `do_heal` (src/healer.cpp:36), `do_cast` (src/magic.cpp:586), `spell_calm` (src/magic.cpp:838), `spell_colour_spray` (src/magic.cpp:1128), `spell_holy_word` (src/magic.cpp:2597), `spell_mass_healing` (src/magic.cpp:2874), `spell_undo_spell` (src/magic.cpp:3778), `tornado_dam` (src/magic2.cpp:64), `tornado_mental` (src/magic2.cpp:72), `fread_char` (src/save.cpp:360), `fread_obj` (src/save.cpp:584), `fread_pet` (src/save.cpp:728), `do_gain` (src/skills.cpp:195), `parse_customizations` (src/skills.cpp:297), `group_add` (src/skills.cpp:519), `group_remove` (src/skills.cpp:545), `get_skill_level` (src/skills.cpp:566), `get_skill_difficulty` (src/skills.cpp:604), `concordius_fights` (src/spec_concordius.cpp:161), `dragon` (src/special.cpp:140), `spec_breath_gas` (src/special.cpp:181), `spec_cast_adept` (src/special.cpp:282), `spec_cast_cleric` (src/special.cpp:327), `spec_cast_judge` (src/special.cpp:401), `spec_cast_mage` (src/special.cpp:420), `spec_cast_undead` (src/special.cpp:496), `spec_cast_bastard` (src/special.cpp:580), `spec_puff` (src/special.cpp:672)
- `skill_lookup` calls `matches_start`
- `do_practice` is defined at src/act_info.cpp:1561-1616 (56 lines): `void do_practice(Char *ch, ArgParser args)`
- `do_practice` handles the command(s) `practice` (minimum position Sleeping, src/InterpreterImpl.cpp:114)
- `do_practice` calls `act` (7 definitions), `curr_stat`, `empty` (3 definitions), `find_prac_mob`, `get_skill_difficulty`, `get_skill_level`, `get_skill_trains`, `is_npc`, `is_pos_awake`, `send_line` (2 definitions), `shift`, `skill_lookup` and 1 more
- `Interpreter::Impl::interpret` is defined at src/InterpreterImpl.cpp:495-550 (56 lines): `void Interpreter::Impl::interpret(Char *ch, std::string_view argument) const`
- Called from `do_order` (src/act_comm.cpp:516), `do_at` (src/act_wiz.cpp:417), `do_force` (src/act_wiz.cpp:2478), `CorpseSummoner::summoner_awaits` (src/CorpseSummoner.cpp:32), `DependenciesImpl::interpret` (src/CorpseSummoner.cpp:150), `Interpreter::interpret` (src/InterpreterImpl.cpp:569), `do_mpat` (src/mob_commands.cpp:311), `do_mpforce` (src/mob_commands.cpp:400), `interpret_command` (src/MProgImpl.cpp:407), `MudImpl::game_loop` (src/MudImpl.cpp:180), `doSleepActions` (src/phil.cpp:57), `doRandomSocial` (src/phil.cpp:114), `concordius_patrols` (src/spec_concordius.cpp:119), `aquila_patrols` (src/spec_concordius.cpp:178)
- `interpret` calls `ArgParser` (3 definitions), `apply_prefix`, `bad_position_msg`, `check_enum_bit`, `check_social`, `clear_enum_bit`, `commandline_shift`, `empty` (3 definitions), `format` (8 definitions), `get` (2 definitions), `get_trust`, `is_npc` and 8 more
- `MudImpl::game_loop` is defined at src/MudImpl.cpp:180-359 (180 lines): `void MudImpl::game_loop()`
- Called from `main` (src/main.cpp:15)
- `game_loop` calls `accept`, `all` (2 definitions), `bug` (2 definitions), `character` (3 definitions), `clear_output_buffer`, `close` (6 definitions), `descriptors`, `doorman_init`, `doorman_lost`, `handle_doorman_packet`, `handle_signal_shutdown`, `has_buffered_output` and 19 more
- `game_loop` reaches persisted or shared state: player files
- `ArgParser::shift` is defined at src/ArgParser.cpp:5-29 (25 lines): `std::string_view ArgParser::shift() noexcept`
- Called from `format_act` (src/Act.cpp:27), `do_tell` (src/act_comm.cpp:144), `do_follow` (src/act_comm.cpp:391), `do_order` (src/act_comm.cpp:516), `do_group` (src/act_comm.cpp:564), `do_peek` (src/act_info.cpp:283), `do_look` (src/act_info.cpp:882), `do_examine` (src/act_info.cpp:932), `do_whois` (src/act_info.cpp:1188), `do_who` (src/act_info.cpp:1217), `do_compare` (src/act_info.cpp:1352), `do_where` (src/act_info.cpp:1417), `do_consider` (src/act_info.cpp:1456), `do_practice` (src/act_info.cpp:1561), `do_password` (src/act_info.cpp:1638), `do_open` (src/act_move.cpp:391), `do_close` (src/act_move.cpp:451), `do_lock` (src/act_move.cpp:502), `do_unlock` (src/act_move.cpp:573), `do_pick` (src/act_move.cpp:642), `do_wake` (src/act_move.cpp:854), `do_recall` (src/act_move.cpp:936), `do_train` (src/act_move.cpp:1020), `do_get` (src/act_obj.cpp:613), `do_put` (src/act_obj.cpp:729), `do_donate` (src/act_obj.cpp:841), `do_give_coins` (src/act_obj.cpp:930), `do_drop` (src/act_obj.cpp:974), `do_give` (src/act_obj.cpp:1066), `do_pour` (src/act_obj.cpp:1140), `do_fill` (src/act_obj.cpp:1229), `do_drink` (src/act_obj.cpp:1266), `do_eat` (src/act_obj.cpp:1344), `do_wear` (src/act_obj.cpp:1402), `do_remove` (src/act_obj.cpp:1423), `do_sacrifice` (src/act_obj.cpp:1435), `do_quaff` (src/act_obj.cpp:1509), `do_recite` (src/act_obj.cpp:1540), `do_zap` (src/act_obj.cpp:1657), `do_steal` (src/act_obj.cpp:1736), `do_buy` (src/act_obj.cpp:1829), `do_list` (src/act_obj.cpp:1970), `do_sell` (src/act_obj.cpp:2018), `do_value` (src/act_obj.cpp:2080), `do_throw` (src/act_obj.cpp:2111), `do_permit` (src/act_wiz.cpp:86), `do_deny` (src/act_wiz.cpp:178), `do_disconnect` (src/act_wiz.cpp:206), `do_pardon` (src/act_wiz.cpp:236), `do_pecho` (src/act_wiz.cpp:306), `do_transfer` (src/act_wiz.cpp:344), `do_at` (src/act_wiz.cpp:417), `do_goto` (src/act_wiz.cpp:458), `do_stat` (src/act_wiz.cpp:507), `do_rstat` (src/act_wiz.cpp:562), `do_ostat` (src/act_wiz.cpp:614), `do_mskills` (src/act_wiz.cpp:762), `do_mspells` (src/act_wiz.cpp:788), `do_maffects` (src/act_wiz.cpp:814), `do_mpracs` (src/act_wiz.cpp:839), `do_minfo` (src/act_wiz.cpp:860), `do_vnum` (src/act_wiz.cpp:1058), `do_mwhere` (src/act_wiz.cpp:1085), `do_snoop` (src/act_wiz.cpp:1134), `do_switch` (src/act_wiz.cpp:1170), `do_clone` (src/act_wiz.cpp:1219), `do_load` (src/act_wiz.cpp:1342), `do_purge` (src/act_wiz.cpp:1355), `do_advance` (src/act_wiz.cpp:1406), `do_trust` (src/act_wiz.cpp:1471), `do_restore` (src/act_wiz.cpp:1502), `do_freeze` (src/act_wiz.cpp:1562), `do_log` (src/act_wiz.cpp:1597), `toggle_player_comm_flag` (src/act_wiz.cpp:1630), `do_awaken` (src/act_wiz.cpp:1680), `do_owhere` (src/act_wiz.cpp:1708), `do_coma` (src/act_wiz.cpp:1745), `do_osearch` (src/act_wiz.cpp:1831), `do_set` (src/act_wiz.cpp:1879), `do_sset` (src/act_wiz.cpp:1914), `do_mset` (src/act_wiz.cpp:1956), `do_string` (src/act_wiz.cpp:2191), `do_oset` (src/act_wiz.cpp:2314), `do_rset` (src/act_wiz.cpp:2399), `do_sockets` (src/act_wiz.cpp:2440), `do_force` (src/act_wiz.cpp:2478), `do_smite` (src/act_wiz.cpp:2624), `ArgParser::commandline_shift` (src/ArgParser.cpp:31), `ArgParser::shift_numbered_arg` (src/ArgParser.cpp:45), `ArgParser::try_shift_number` (src/ArgParser.cpp:52), `begin` (src/ArgParser.hpp:68), `Bans::ban_site` (src/Ban.cpp:66), `do_noclanchan` (src/clan.cpp:126), `do_member` (src/clan.cpp:158), `mote` (src/clan.cpp:218), `do_clanset` (src/clan.cpp:274), `do_areas` (src/db.cpp:1473), `do_duel` (src/Duel.cpp:176), `do_immworth` (src/entity_balance.cpp:90), `do_bash` (src/fight.cpp:1680), `do_dirt` (src/fight.cpp:1781), `do_trip` (src/fight.cpp:1900), `do_kill` (src/fight.cpp:1994), `do_murder` (src/fight.cpp:2045), `do_backstab` (src/fight.cpp:2087), `do_rescue` (src/fight.cpp:2192), `do_headbutt` (src/fight.cpp:2259), `do_kick` (src/fight.cpp:2362), `do_slay` (src/fight.cpp:2475), `do_setinfo` (src/Finger.cpp:84), `do_finger` (src/Finger.cpp:177), `do_heal` (src/healer.cpp:36), `Interpreter::Impl::check_social` (src/InterpreterImpl.cpp:433), `do_cast` (src/magic.cpp:586), `spell_ventriloquate` (src/magic.cpp:3396), `spell_teleport_object` (src/magic.cpp:3709), `spell_undo_spell` (src/magic.cpp:3778), `do_mpkill` (src/mob_commands.cpp:71), `do_mpjunk` (src/mob_commands.cpp:105), `do_mpechoaround` (src/mob_commands.cpp:145), `do_mpechoat` (src/mob_commands.cpp:166), `do_mppurge` (src/mob_commands.cpp:254), `do_mpgoto` (src/mob_commands.cpp:286), `do_mpat` (src/mob_commands.cpp:311), `do_mptransfer` (src/mob_commands.cpp:346), `do_mpforce` (src/mob_commands.cpp:400), `give_trigger` (src/MProg.cpp:118), `show_programs` (src/MProg.cpp:173), `process_block` (src/MProgImpl.cpp:432), `MudImpl::nanny` (src/MudImpl.cpp:603), `NoteHandler::on_command` (src/Note.cpp:198), `NoteHandler::read` (src/Note.cpp:208), `parse_pronouns` (src/Pronouns.cpp:61), `do_pronouns` (src/Pronouns.cpp:79), `do_ride` (src/ride.cpp:79), `parse_customizations` (src/skills.cpp:297), `do_groups` (src/skills.cpp:431), `do_tipwizard` (src/Tips.cpp:47), `do_wiznet` (src/wiznet.cpp:101)
- `shift` calls `empty` (3 definitions), `find`, `front` (2 definitions), `ltrim`
- `do_sset` is defined at src/act_wiz.cpp:1914-1953 (40 lines): `void do_sset(Char *ch, ArgParser args)`
- Called from `do_set` (src/act_wiz.cpp:1879)
- `do_sset` calls `empty` (3 definitions), `get_char_world`, `is_npc`, `matches` (2 definitions), `send_line` (2 definitions), `shift`, `skill_lookup`, `try_shift_number`
- `do_slookup` is defined at src/act_wiz.cpp:1857-1875 (19 lines): `void do_slookup(Char *ch, std::string_view argument)`
- Called from `do_vnum` (src/act_wiz.cpp:1058)
- `do_slookup` calls `empty` (3 definitions), `matches` (2 definitions), `send_line` (2 definitions), `skill_lookup`
- `src/lookup.cpp`: 71 lines, 2 functions
- `src/act_info.cpp`: 1754 lines, 83 functions
- `src/InterpreterImpl.cpp`: 577 lines, 15 functions
- `src/MudImpl.cpp`: 1114 lines, 44 functions
- `src/ArgParser.cpp`: 62 lines, 4 functions
- `src/act_wiz.cpp`: 2679 lines, 79 functions

**To decide**

- [ ] Is the change local to these functions, or does the fix belong in a shared helper their callers use too?
- [ ] Does every caller (including automatic ones) still get the behaviour it expects?

## 3. Design patterns

- In `skill_lookup`: std::string_view x1 (modern), matches()/matches_start() x1 (modern)
- In `do_practice`: ArgParser x1 (modern), act() x4 (either)
- 140 other functions share the signature `(Char *ch, ArgParser args)`; in the same file: `do_compare`, `do_consider`, `do_examine`, `do_look`, `do_password`, `do_peek`, `do_scroll`, `do_where` and 3 more
- In `interpret`: ArgParser x1 (modern), std::string_view x1 (modern), fmt::format x2 (modern)
- In `game_loop`: range-for over contents x2 (modern)
- In `shift`: ArgParser x1 (modern), std::string_view x3 (modern)
- In `do_sset`: ArgParser x1 (modern), matches()/matches_start() x1 (modern)
- In `do_slookup`: std::string_view x1 (modern), matches()/matches_start() x1 (modern)
- Across src/: act() 779, std::string_view 625, ArgParser 402, matches()/matches_start() 291, range-for over contents 267, fmt::format 211, sprintf/strcpy/strcat 19, '\0' terminator checks 14, char buffers 10

**To decide**

- [ ] Which existing idiom does the change follow, and does it leave the function more consistent?
- [ ] Is there a helper already (in the same file or a header) that does what the change needs?

## 4. Technical debt

- `skill_lookup` indexes string_views like C strings (reading past the end when the view is that long, and never seeing a terminator): `name[0]` at src/lookup.cpp:39, `name[0]` at src/lookup.cpp:39
- `game_loop` is 180 lines long (src/ median 7).
- TODO at src/act_info.cpp:1198: can or should this be part of all_visible_to?
- TODO at src/act_info.cpp:1257: this could be much better phrased
- TODO at src/MudImpl.cpp:28: remove this
- TODO at src/MudImpl.cpp:44: move these?
- TODO at src/MudImpl.cpp:57: Move into a Universe class
- TODO at src/MudImpl.cpp:96: do something rather than return here if there's a failure
- TODO at src/MudImpl.cpp:456: remove global
- TODO at src/MudImpl.cpp:668: crypt can return null if if fails (e.g. password is truncated).
- TODO at src/act_wiz.cpp:744: #260 support Light objects.
- TODO at src/act_wiz.cpp:1955: this could be rewritten to be less procedural.
- The same pattern elsewhere in src/ (14 places in 4 functions; each is the same kind of bug unless the view is known to be long enough): `do_who` `arg[0]` :1249; `do_get` `arg1[3]` :641, `&arg1[4]` :641, `arg1[3]` :648, `&arg1[4]` :651, `arg1[3]` :707; `do_permit` `player[0]` :95, `player[0]` :98; `nanny` `argument[0]` :711, `argument[0]` :740, `argument[0]` :762, `argument[0]` :854, `argument[0]` :890, `argument[0]` :915

**To decide**

- [ ] Are the other places with the same pattern the same bug, and do they belong in this change?
- [ ] What debt does the change pay down while it's here, and what does it deliberately leave?
- [ ] Does the change add any (a special case, a duplicated check, a new legacy idiom)?

## 5. Gameplay

- Players reach this with `practice` (from position Sleeping up).
- Messages `do_practice` can show: "In your dreams, or what?"; "You can't do that here."; "You have no practice sessions left."; "You can't practice that."; "You can't practice that."; "You are already learned at {}."; "You practice $T."; "$n practices $T."; "You are now learned at $T."; "$n is now learned at $T."
- Messages `interpret` can show: "You're totally frozen!"; "never log"; "Log {} (as '{}'): {}"; "Log {}: {}"
- Messages `game_loop` can show: "Running under a debugger"; "Doorman socket not initialized, exiting!"; "Xania is ready to rock via {}."; "Game_loop: select: poll"; "Unable to read signal info - treating as term"; "Caught SIGINT but detected a debugger, trapping instead"; "Unexpected signal {}: ignoring"; "Waiting for doorman..."; "Doorman has connected."; "Unable to accept doorman connection: {}" (+2)
- Messages `do_sset` can show: "  set skill <name> <spell or skill> <value>"; "  set skill <name> all <value>"; "   (use the name of the skill, not the number)"; "They aren't here."; "Not on NPC's."; "Value must be numeric."; "Value range is 0 to 100."; "No such skill or spell: {}."
- Messages `do_slookup` can show: "Lookup which skill or spell?"; "Sn: {}  Slot: {}  Skill/spell: '{}'"; "Sn: {}  Slot: {}  Skill/spell: '{}'"; "No such skill or spell."
- Balance numbers Explorer models from these files: none (the change is behaviour, not balance; Explorer's predictions shouldn't move)

**To decide**

- [ ] What does a player notice before and after (messages, what they get, what's refused)?
- [ ] Can a careless or abusive player use the change (or the old behaviour) to their advantage?
- [ ] Does it change balance for any class, race or level range? If so, which Explorer numbers?

## 6. Documentation

- Help `PRACTICE` (area/Help.are:1079, level 0): Syntax: PRACTICE

**To decide**

- [ ] Does any help entry describe the behaviour being changed, and does it need rewording?
- [ ] Does the change need a note anywhere else (README, release notes, an issue comment)?

## 7. Test coverage

- `src/apps/test/pfutest.cpp`: includes MudImpl.hpp
- `src/test/ArgParserTest.cpp`: mentions shift, named after ArgParser.cpp, includes ArgParser.hpp
- `src/test/CharTest.cpp`: mentions skill_lookup
- `src/test/CorpseSummonerTest.cpp`: mentions interpret
- `src/test/HitChanceTest.cpp`: mentions skill_lookup
- `src/test/InterpreterImplTest.cpp`: named after InterpreterImpl.cpp, includes InterpreterImpl.hpp
- `src/test/LearningTest.cpp`: mentions skill_lookup
- `src/test/PracticeTabulatorTest.cpp`: mentions skill_lookup
- `src/test/SkillsTabulatorTest.cpp`: mentions skill_lookup
- `src/test/lookup_test.cpp`: named after lookup.cpp, mentions skill_lookup
- `src/test/magic_test.cpp`: mentions skill_lookup
- `src/test/save_test.cpp`: includes MudImpl.hpp
- No unit test calls `do_practice`.
- No unit test calls `game_loop`.
- No unit test calls `do_sset`.
- No unit test calls `do_slookup`.
- Sim `scenarios/test_live_bugs.py` sends `practice`
- Sim `scenarios/test_live_director.py` sends `practice`
- Sim `xania_sim/activities/practice.py` sends `practice`
- Sim `xania_sim/activities/tactics.py` sends `practice`
- Sim `xania_sim/trials/skill.py` sends `practice`
- Sim finding `crash:SIGABRT:lookup.cpp:skill_lookup` [known, seen 1x]: xania crashed (SIGABRT, failed assertion) in skill_lookup (lookup.cpp) (https://github.com/abraidotti/xania/issues/7)

**To decide**

- [ ] Which unit test pins the fixed behaviour (a test that fails before the change)?
- [ ] Which Sim trial or scenario shows it from a player's side, and should a new one be added?

## 8. History

- `name` is declared at src/lookup.cpp:33, a line last changed in `42406b7` (2021-11-14, snellers): Replace spell function void* with SpellTarget type.
- `name[0]` at src/lookup.cpp:39 was last changed in `42406b7` (2021-11-14, snellers): Replace spell function void* with SpellTarget type.
- `name[0]` at src/lookup.cpp:39 was last changed in `42406b7` (2021-11-14, snellers): Replace spell function void* with SpellTarget type.
- The conversion to string_view (or ArgParser): `42406b7` (2021-11-14, snellers): Replace spell function void* with SpellTarget type.. The indexing above has been on a view, with no terminator, since then
- `skill_lookup` (14 lines) comes from 4 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (10 lines); `42406b7` (2021-11-14, snellers): Replace spell function void* with SpellTarget type. (2 lines); `7a71102` (2020-07-22, Matt Godbolt): Reformat all the code with clang-format (1 lines); `3eee938` (2020-08-04, Matt Godbolt): NULL->nullptr (1 lines)
- `do_practice` (56 lines) comes from 13 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (24 lines); `4c5b464` (2020-09-15, Matt Godbolt): Last sprintfs gone from act_info; consistent use of the columner (6 lines); `7a71102` (2020-07-22, Matt Godbolt): Reformat all the code with clang-format (5 lines); `a2c31f5` (2020-09-02, Matt Godbolt): Formatting changes. (5 lines)
- `interpret` (56 lines) comes from 15 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (18 lines); `6910cfa` (2021-07-31, snellers): snprintf() => fmt:: (apply_prefix()) (12 lines); `687f6ce` (2025-05-11, snellers): Step 2 of the next big refactoring project. (7 lines); `39ee043` (2021-10-25, snellers): Macro death: convert PLR_ act flags to PlayerActFlag. (5 lines)
- `game_loop` (180 lines) comes from 18 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (50 lines); `e164685` (2020-08-13, Matt Godbolt): Clean up and use the shared FD code for some of the xania->doorman side of things (28 lines); `687f6ce` (2025-05-11, snellers): Step 2 of the next big refactoring project. (23 lines); `c6c1ce6` (2020-08-02, Matt Godbolt): Fix signal handling. (20 lines)
- `shift` (25 lines) comes from 3 commits; the most: `67c11b0` (2020-08-22, Matt Godbolt): ArgParser (22 lines); `3e61ef3` (2021-12-29, snellers): Change ArgParser to use string_utils ltrim() as it returns a string_view now. (2 lines); `8b7eaf4` (2020-08-23, Matt Godbolt): Refactor of do_look and directions (#158) (1 lines)
- `do_sset` (40 lines) comes from 8 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (14 lines); `194c4ec` (2021-12-04, snellers): set obj|mob|skill|room upgraded to ArgParser. class_lookup() now uses string_view. (11 lines); `a2c31f5` (2020-09-02, Matt Godbolt): Formatting changes. (8 lines); `d715fef` (2021-12-03, snellers): emote, exits, pour, fill, eat, force, duel commands upgraded to ArgParser or string_view. (2 lines)
- `do_slookup` (19 lines) comes from 6 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (7 lines); `bd90f27` (2021-11-17, snellers): Convert do_vnum, do_mfind, do_ofind and do_slookup to use ArgParser/string_view. (4 lines); `dce5e9b` (2021-07-31, snellers): snprintf() => fmt:: (do_advance(), do_slookup()) (4 lines); `a2c31f5` (2020-09-02, Matt Godbolt): Formatting changes. (2 lines)
- Since 42406b7 (2021-11-14), 26 commits changed the compiler or its flags; the latest: `7bd8c82` (2026-10-31, snellers): github action upgrade to Ubuntu 26.04 and g++-15; `82823ff` (2026-10-31, snellers): General tooling upgrades, largely for Ubuntu 26.04.1 compatibility conda 26.9.4-0 conan 2.33.0 cmake >= 3.31 g++-15 default, g++-13 fallback Compiles on ubunt 26.04.1; `425fd97` (2025-04-07, snellers): Docker: ubuntu 24 is the default these days. Install clang 19. Stop trying to install awscli as it's not in the ubuntu apt sources now. The session doesn't start tmux by default. [skip ci]; `e5483b6` (2025-03-28, snellers): Update g++ versions in README. Retire the g++ 10/11 toolchains.; `55c9b1b` (2025-03-28, snellers): github: upgrade to ubuntu 24 and use g++-13
- Debug builds add `-fno-omit-frame-pointer -fsanitize=leak -fsanitize=address -fsanitize=undefined`
- Release builds add `-O2 -DNDEBUG -Wno-error=array-bounds`
- Upstream issue [#194](https://github.com/mattgodbolt/xania/issues/194) (closed): cast 'disp m' doesn't map to 'dispel magic' (mentions `skill_lookup`)

**To decide**

- [ ] When did the behaviour start, and why did nobody notice until now?
- [ ] Did a toolchain change (compiler, flags, sanitizers) make it show, or change how it shows?
- [ ] Has upstream seen or tried this before, and does the change fit what was decided then?

## Gate plan

What `prototype` runs on the fork before this can ship:

- Builds: Debug (ASan, UBSan, LSan, libstdc++ assertions), Release (-O2)
- Unit tests: `src/apps/test/pfutest.cpp`, `src/test/ArgParserTest.cpp`, `src/test/CharTest.cpp`, `src/test/CorpseSummonerTest.cpp`, `src/test/HitChanceTest.cpp`, `src/test/InterpreterImplTest.cpp`, `src/test/LearningTest.cpp`, `src/test/PracticeTabulatorTest.cpp`, `src/test/SkillsTabulatorTest.cpp`, `src/test/lookup_test.cpp`, `src/test/magic_test.cpp`, `src/test/save_test.cpp`
- Sim: `smoke`: the game still boots and a player can log in
- Sim: `hunt --minutes 5`: fights and what runs after a kill (autoloot) reach it
- Sim: `churn --minutes 5`: logins and quits reach it (lifetime bugs show here)
- Sim: `pytest scenarios/test_live_bugs.py`: it sends the commands involved
- Sim: `pytest scenarios/test_live_director.py`: it sends the commands involved
- Regression: Sim finding `crash:SIGABRT:lookup.cpp:skill_lookup` should stop reproducing (https://github.com/abraidotti/xania/issues/7)
