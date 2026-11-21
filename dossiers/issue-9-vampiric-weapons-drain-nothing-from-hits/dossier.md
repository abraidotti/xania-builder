# Vampiric weapons drain nothing from hits under 100 damage ((damage / 100) * 10 is integer arithmetic) (#9)

[#9](https://github.com/abraidotti/xania/issues/9) · Xania eec205e5fd · 2026-11-20 21:29

<details><summary>The idea as given</summary>

## Summary

Vampiric weapons almost never drain anything. `damage()` gives the wielder `(adjusted_damage / 100) * 10` hit points
per hit and takes the same from the victim. That's integer arithmetic, so a hit under 100 drains **0**, 100-199
drains 10, 200-299 drains 20, and so on. The intent was almost certainly "10% of the damage".

In practice:

- **Below about level 65 a vampiric weapon is a plain weapon.** Hits don't reach 100. A live test at level 20 with
  the lowest-level one (the black demon blade, Moria) drained nothing in 98 hits.
- **At level 65-91 it works now and then.** In live tests 3 of 99 hits with the Executioner's Axe and 10 of 98 with
  the Sword of Ashen-Shugar reached 100, so each drained 10 HP. A 10% drain would have given about 20 times as much.
- **It's silent.** There's no message, so players can't tell whether it works.

The nine vampiric weapons in the area files run from level 11 to 91, and every one is worn by a mob. The flag also
adds 1 to an item's worth in `entity_balance.cpp`, the same as Sharp, for an effect that isn't really there.

While reading the block I found three smaller problems that a fix to the arithmetic alone would expose. They're in
the table below.

Present at `82171fa` (current `main` of this fork and of mattgodbolt/xania). The code has been the same since the
initial import (`33a9553`, 2020).

## How to reproduce

From level 20 every damage message shows its amount, so the drain can be read off the prompt:

1. As an immortal: `load obj 10066` (Executioner's Axe, level 65), give it to a level-65 character, and `wield` it.
2. Fight anything that takes a while to kill, for example `load mob 3065` (a beggar), then `set char beggar hp 30000`
   and `restore beggar`.
3. Watch the hit points in the prompt after each round. Hits under 100 change nothing. A hit of 100 or more adds
   exactly 10, even above max HP:

```
Your chop splits the beggar's head. (111)
<bot 673/663 ...>
```

Live results, accounting for every round: the hp change plus the damage the wielder took, compared with each
model's prediction from the wielder's own hits. A level-1 beggar with 30,000 hp was the target, the wielder was a
knight with skills at 100%, and there were 60 rounds per weapon.

| Weapon (level) | Wielder level | Hits | Mean / max hit | Hits of 100+ | Drained (seen) | `(d/100)*10` predicts | 10% would give |
|---|---|---|---|---|---|---|---|
| a black demon blade (11) | 20 | 98 | 14 / 22 | 0 | 0 | 0 | 100 |
| Executioner's Axe (65) | 65 | 99 | 64 / 108 | 3 | 30 | 30 | 593 |
| Sword of Ashen-Shugar (91) | 91 | 98 | 79 / 132 | 10 | 90 | 100 | 725 |

`(d/100)*10` explains 169 of the 180 rounds exactly, and 10% explains 5. The other 10 had a regen tick in them,
which adds hit points or clamps them back to max (`update.cpp:672-675`); that's where the missing 10 in the last row
went.

## Faulty lines

| File:line | Code | Problem |
|---|---|---|
| `src/fight.cpp:718-719` | `ch->hit += (adjusted_damage / 100) * 10;` | integer division: 0 below 100 damage, steps of 10 above |
| `src/fight.cpp:712` then `716-720` | `update_pos(victim);` then the drain | the victim's position is worked out *before* the drain takes more hp, so a drain that crosses a threshold (stunned, dying, dead) doesn't count until something else calls `update_pos` |
| `src/fight.cpp:710-711` then `719` | the immortal floor (`hit = 1`), then `victim->hit -= ...` | the drain runs after the floor, so it can take an immortal below 1 |
| `src/fight.cpp:718` | `ch->hit += ...` | no cap at `max_hit`, so the wielder goes over max until the next tick clamps it (seen live: `673/663`) |
| `src/fight.cpp:714-717` | the drain lives in `damage()` | `damage()` handles every kind of damage, so a vampiric weapon also drains on spells, skills and breath, as long as it's wielded |

The vampiric weapons, from the area files (all of them are equipped by a mob):

| Vnum | Weapon | Level | Dice | Area | Worn by |
|---|---|---|---|---|---|
| 4100 | a black demon blade | 11 | 3d4 | Moria | the troll (12) |
| 13007 | the draconian mace | 39 | 6d7 | Flying Citadel | the evil draconian cleric (40) |
| 27020 | a soup ladle | 50 | 10d5 | Seminary | Madam Breakfast (50) |
| 10066 | Executioner's Axe | 65 | 6d11 | Wolf Pointe | the executioner (65) |
| 18121 | The Reaper's Scythe | 85 | 9d9 | Den of Monsters | the Grim Reaper's minion (85) |
| 1006 | The Fangs of Nitrius | 90 | 13d7 | Heavens | Nitrius (100) |
| 18128 | The Fangs of the Vampire | 90 | 10d9 | Den of Monsters | Dracula (105) |
| 28021 | Sword of Ashen-Shugar | 91 | 13d7 | Sethanon | a golden warrior (105) |
| 10129 | an axe | 91 | 15d6 | Uruk's Fortress | Uruk's armourer (94) |

Immortals can also make any carried weapon vampiric with the `vampire` spell (`magic.cpp:2144`).

## Suggested fix

Fix the bug, and make the drain apply to melee only. The arithmetic itself is a balance decision, so here are two
options with numbers, followed by the questions I'd like answered before opening a PR.

**Where it goes (either option):** move the drain out of `damage()` into `one_hit()`, next to the Poisoned and
Plagued on-hit effects (`fight.cpp:541`). Then only weapon hits drain, not spells, skills or breath. It needs the
damage actually dealt (after tolerances), which `damage()` doesn't return today, and it should only run if the
victim is still alive and fighting the wielder (ROM checks `ch->fighting == victim`).

**Option A: 10% of the damage dealt** (what the code seems to have meant)

```cpp
const auto drain = dealt / 10;
victim->hit -= drain;
ch->hit = std::min(ch->hit + drain, ch->max_hit);
update_pos(victim);  // after the drain, and with the immortal floor applied after it too
```

Expected drain per hit, from Explorer's model of `one_hit` (typical gear, skills as Explorer assumes):

| Weapon (level) | Barbarian / knight | Cleric | Mage |
|---|---|---|---|
| black demon blade (11) | 0.5-0.8 | 0.2 | 0.2 |
| draconian mace (39) | 3.5-3.7 | 2.3 | 2.3 |
| Executioner's Axe (65) | 5.4-5.6 | 5.4 | 3.6 |
| The Reaper's Scythe (85) | 8.0-8.2 | 8.1 | 5.7 |
| the level-90/91 four | 9.5-10.2 | 9.5-10.0 | 7.0-7.3 |

At 2-3 hits a round that's 20-30 HP a round for a level-91 fighter, about 2-3% of max HP. For comparison, Sharp is
worth about +2% expected damage.

**Option B: ROM 2.4's vampiric weapon**, for comparison (ROM's `fight.c` `one_hit`): after each hit, a separate
`number_range(1, wield->level / 5 + 1)` of negative-energy damage, so a victim immune or resistant to negative takes
less. The wielder heals half of it and loses 1 alignment, and there are messages: "$p draws life from $n." to the
room and "You feel $p drawing your life away." to the victim. For a level-91 weapon that's 1-19 extra damage
(average 10) and about 5 HP healed per hit. Xania already has `DamageType::Negative`. This one scales with the
weapon's level rather than the hit, so it's gentler on the high-damage hits and a backstab doesn't drain huge
amounts.

**My recommendation:** Option A, melee only, capped at max HP, with the position check after the drain. It's the
smallest change from what's there, it's what the formula was clearly trying to do, and it keeps the stepped bug from
coming back.

### Questions before a PR

Each question has a recommended answer. Disagree with any of them and I'll change the plan before writing code.

1. **Rate:** 10% of the damage dealt (Option A), ROM's level-based extra hit (Option B), or something else, such as
   5%?

   *Recommended: 10% of the damage dealt.* It's what the formula was trying to do, and it grows with the hit as the
   rest of combat does. At the top it's 20-30 HP a round, about 2-3% of a level-91 fighter's max HP: noticeable,
   but not enough to make these weapons must-haves. If that turns out too strong, the rate is one constant to tune.

2. **Which hits count:** plain weapon hits only, or also skill hits that go through `one_hit` (backstab, for
   example, which multiplies damage by 2 + level/10)?

   *Recommended: plain weapon hits only* (`one_hit` with no `opt_skill`). A level-91 backstab does 11 to 13 times
   normal damage, so a 10% drain on it would heal 50-100 HP in one blow, far more than the flag is worth elsewhere.
   Leaving skill hits out also keeps the rule easy to explain: "your weapon drinks a little from every ordinary hit".

3. **Cap:** heal up to max HP only, or allow overheal until the next tick, as today?

   *Recommended: cap at max HP.* Healing works that way everywhere else in the game, and today's overheal is only
   lost again at the next tick (`update.cpp:672-675`), so it adds nothing but confusing prompts.

4. **Messages:** add a drain message (ROM's, or a Xania one), or keep it silent?

   *Recommended: a short message to the wielder and the victim, and nothing to the room*, only when the drain is
   above 0. Players should be able to tell the flag works, and combat output is already busy, so the room doesn't
   need it. For example: "You feel $p drinking your life." to the victim and "$p drinks from $N." to the wielder.

5. **Alignment:** should drinking life cost alignment, as in ROM?

   *Recommended: no.* A fighter lands hundreds of hits an hour, so even -1 a hit would push wielders to -1000 within
   a session. Alignment decides which items zap you, so that would quietly cost players their gear. If an evil
   flavour is wanted, AntiGood on the weapons in the area files does that more visibly.

6. **Undead:** should victims immune or resistant to negative damage resist the drain? This is free with Option B and
   would need a check with Option A.

   *Recommended: yes*, with the rule `damage()` already uses: no drain from a victim immune to negative damage, a
   third less from a resistant one, half again from a vulnerable one (`check_damage_tolerance` with
   `DamageType::Negative`). Draining life from the undead makes no sense, and it costs one call.

7. **Mobs:** the nine mobs that wield these heal from players with a working drain, for example Dracula (105) and
   Nitrius (100). Is that fine, or should some area files change at the same time?

   *Recommended: fine as it is, with no area file changes in the PR.* Dracula healing as he bites is exactly the
   flavour the builders put there, and about 10 HP a hit is small next to these mobs' hit points. A Sim area trial
   of Den of Monsters before and after the fix would show whether those fights get noticeably longer, and any
   retuning can go in its own change.

Tests a PR would add: a unit test of the drain amount (a hit of 50 drains 5, not 0) and of the cap; and the live
weapon trial below, which should show the new model explaining the rounds.

## How this was found

Xania Explorer's code checks flagged `(adjusted_damage / 100) * 10` (check `code.vampiric-integer-drain`) when it
started modelling weapon flags. The weapon counts above come from Explorer's area-file parser. The live numbers come
from a new Xania Sim trial, `python -m xania_sim weapon`
([trials/weapon.py](https://github.com/abraidotti/xania-sim/blob/main/xania_sim/trials/weapon.py)).
In it, a bot wields each
weapon and fights a beggar given 30,000 hp, and every round's hp change is accounted for from the damage amounts in
the combat messages. ROM's code was read from the ROM 2.4b6 source (`fight.c` `one_hit`) in
[avinson/rom24-quickmud](https://github.com/avinson/rom24-quickmud).

</details>

## Focus

- `damage` (src/fight.cpp:586, 288 lines): named with --symbol
- `one_hit` (src/fight.cpp:410, 145 lines): named with --symbol
- `char_update` (src/update.cpp:655, 167 lines): update.cpp:672 is in it
- `spell_vampire` (src/magic.cpp:2144, 21 lines): magic.cpp:2144 is in it
- `update_pos` (src/fight.cpp:1130, 24 lines): named in the idea
- `check_damage_tolerance` (src/DamageTolerance.cpp:16, 46 lines): named in the idea
- `src/entity_balance.cpp`
- Commands: `load`, `wield`, `set`, `restore`, `hit`

## 1. Explorer insights

- Bug check `code.vampiric-integer-drain` (present, wrong-behaviour): Vampiric weapons drain nothing from hits under 100 damage. fight.cpp:718, fight.cpp:719
- Bug check `code.elemental-weapon-flags` (present, wrong-behaviour): Flaming and frost weapons do nothing in combat. entity_balance.cpp:57, entity_balance.cpp:59
- Bug check `code.harm-fire-damage` (present, wrong-behaviour): The harm spell does fire damage. magic.cpp:2447
- Bug check `code.lose-level-asymmetry` (present, wrong-behaviour): Losing a level doesn't undo what gaining it gave. update.cpp:480, update.cpp:539
- The **Skills & spells** assessment reads magic.cpp; a change here can move its numbers (ok).
- Skills & spells finding `skills.nothing-new` (impact 2): Nothing new to learn after level 70
- Skills & spells finding `skills.practice-budget` (impact 2): Practices only catch up with the default package by level 79
- Recommendation `skills.practice-budget.more-practices`: Give 3 more practices per level
- Skills & spells finding `skills.spells-vs-hp` (impact 3): Attack spells fall behind mob HP: 41 casts per kill by level 91
- Recommendation `skills.spells-vs-hp.scale-damage`: Let attack-spell damage keep growing after the 30s

**To decide**

- [ ] The fix should turn the code check above to `fixed` (it matches the faulty pattern). Does it, and are there other occurrences to fix at the same time?

## 2. Architecture

- `damage` is defined at src/fight.cpp:586-873 (288 lines): `bool damage(Char *ch, Char *victim, const int raw_damage, const AttackType atk_type, const DamageType damage_type)`
- Called from `one_hit` (src/fight.cpp:410), `do_bash` (src/fight.cpp:1680), `do_dirt` (src/fight.cpp:1781), `do_trip` (src/fight.cpp:1900), `do_backstab` (src/fight.cpp:2087), `do_headbutt` (src/fight.cpp:2259), `do_kick` (src/fight.cpp:2362), `spell_acid_blast` (src/magic.cpp:671), `spell_burning_hands` (src/magic.cpp:795), `spell_call_lightning` (src/magic.cpp:805), `spell_cause_light` (src/magic.cpp:950), `spell_cause_critical` (src/magic.cpp:960), `spell_cause_serious` (src/magic.cpp:970), `spell_chain_lightning` (src/magic.cpp:980), `spell_chill_touch` (src/magic.cpp:1106), `spell_colour_spray` (src/magic.cpp:1128), `spell_exorcise` (src/magic.cpp:1350), `spell_demonfire` (src/magic.cpp:1378), `spell_dispel_evil` (src/magic.cpp:1522), `spell_dispel_good` (src/magic.cpp:1545), `spell_earthquake` (src/magic.cpp:1584), `spell_energy_drain` (src/magic.cpp:2203), `spell_fireball` (src/magic.cpp:2231), `spell_flamestrike` (src/magic.cpp:2246), `spell_harm` (src/magic.cpp:2447), `spell_holy_word` (src/magic.cpp:2597), `spell_lightning_bolt` (src/magic.cpp:2804), `spell_magic_missile` (src/magic.cpp:2863), `spell_shocking_grasp` (src/magic.cpp:3231), `spell_acid_breath` (src/magic.cpp:3480), `spell_fire_breath` (src/magic.cpp:3544), `spell_frost_breath` (src/magic.cpp:3603), `spell_gas_breath` (src/magic.cpp:3634), `spell_lightning_breath` (src/magic.cpp:3651), `spell_general_purpose` (src/magic.cpp:3670), `spell_high_explosive` (src/magic.cpp:3680), `tornado_dam` (src/magic2.cpp:64), `fallen_off_mount` (src/ride.cpp:62), `char_update` (src/update.cpp:655)
- `damage` calls `ArgParser` (3 definitions), `act` (7 definitions), `affect_strip`, `announce`, `bug` (2 definitions), `check_damage_tolerance`, `check_dodge`, `check_enum_bit`, `check_improve`, `check_killer`, `check_material_vulnerability`, `check_parry` and 49 more
- `one_hit` is defined at src/fight.cpp:410-554 (145 lines): `void one_hit(Char *ch, Char *victim, const skill_type *opt_skill)`
- Called from `multi_hit` (src/fight.cpp:239), `mob_hit` (src/fight.cpp:292)
- `one_hit` calls `HitChance`, `SpellTarget` (3 definitions), `act` (7 definitions), `at`, `calculate`, `check_enum_bit`, `check_improve`, `damage`, `dice` (2 definitions), `find_affect`, `get_damroll`, `get_eq_char` and 17 more
- `char_update` is defined at src/update.cpp:655-821 (167 lines): `void char_update()`
- Called from `update_handler` (src/update.cpp:856)
- `char_update` calls `act` (7 definitions), `affect_join`, `affect_remove`, `at`, `channel`, `check_damage_tolerance`, `check_duel_timeout`, `clear_enum_bit`, `damage`, `delta_hunger`, `delta_inebriation`, `delta_thirst` and 27 more
- `char_update` reaches persisted or shared state: character lifetimes, object lifetimes, player files
- `spell_vampire` is defined at src/magic.cpp:2144-2164 (21 lines): `void spell_vampire(int sn, int level, Char *ch, const SpellTarget &spell_target)`
- No caller found for `spell_vampire` in src/ (it may be called through a table or pointer).
- `spell_vampire` calls `getObject`, `is_immortal`, `send_line` (2 definitions), `set_enum_bit`
- `update_pos` is defined at src/fight.cpp:1130-1153 (24 lines): `void update_pos(Char *victim)`
- Called from `do_restore` (src/act_wiz.cpp:1502), `damage` (src/fight.cpp:586), `stop_fighting` (src/fight.cpp:1174), `spell_cure_critical` (src/magic.cpp:1237), `spell_cure_light` (src/magic.cpp:1270), `spell_cure_serious` (src/magic.cpp:1303), `spell_heal` (src/magic.cpp:2581), `char_update` (src/update.cpp:655)
- `update_pos` calls `is_npc`, `is_pos_stunned_or_dying`
- `check_damage_tolerance` is defined at src/DamageTolerance.cpp:16-61 (46 lines): `DamageTolerance check_damage_tolerance(const Char *ch, const DamageType damage_type)`
- Called from `damage` (src/fight.cpp:586), `char_to_room` (src/handler.cpp:274), `spell_psy_tornado` (src/magic2.cpp:95), `char_update` (src/update.cpp:655)
- `check_damage_tolerance` calls `check_enum_bit`
- `src/fight.cpp`: 2498 lines, 47 functions
- `src/update.cpp`: 892 lines, 19 functions
- `src/magic.cpp`: 3824 lines, 125 functions
- `src/DamageTolerance.cpp`: 61 lines, 1 functions
- `src/entity_balance.cpp`: 109 lines, 3 functions

**To decide**

- [ ] Is the change local to these functions, or does the fix belong in a shared helper their callers use too?
- [ ] Does every caller (including automatic ones) still get the behaviour it expects?

## 3. Design patterns

- In `damage`: ArgParser x1 (modern), fmt::format x1 (modern), matches()/matches_start() x1 (modern), range-for over contents x1 (modern), act() x6 (either)
- In `one_hit`: act() x8 (either)
- In `char_update`: range-for over contents x3 (modern), act() x7 (either)
- Across src/: act() 779, std::string_view 626, ArgParser 402, matches()/matches_start() 289, range-for over contents 267, fmt::format 211, sprintf/strcpy/strcat 19, '\0' terminator checks 13, char buffers 10

**To decide**

- [ ] Which existing idiom does the change follow, and does it leave the function more consistent?
- [ ] Is there a helper already (in the same file or a header) that does what the change needs?

## 4. Technical debt

- `damage` is 288 lines long (src/ median 7).
- `one_hit` is 145 lines long (src/ median 7).
- `char_update` is 167 lines long (src/ median 7).
- TODO at src/magic.cpp:211: perhaps the code for this and do_cast can be unified as they're similar.
- TODO at src/magic.cpp:2730: #259 support more types
- TODO at src/magic.cpp:2833: wth was this supposed to be?*/) {
- TODO at src/DamageTolerance.cpp:21: sort this out.
- TODO at src/DamageTolerance.cpp:24: I think we should ditch this catch all case and apply specific tolerance bits to

**To decide**

- [ ] Are the other places with the same pattern the same bug, and do they belong in this change?
- [ ] What debt does the change pay down while it's here, and what does it deliberately leave?
- [ ] Does the change add any (a special case, a duplicated check, a new legacy idiom)?

## 5. Gameplay

- Players reach this with `load` (from position Dead up).
- Players reach this with `wield` (from position Resting up).
- Players reach this with `set` (from position Dead up).
- Players reach this with `restore` (from position Dead up).
- Players reach this with `hit` (from position Fighting up).
- Messages `damage` can show: "Player {} fighting {} in #{}, damage {} exceeds {} cap!"; "$n fades into existence."; "|r$n is mortally wounded, and will die soon, if not aided.|w"; "|rYou are mortally wounded, and will die soon, if not aided.|w"; "|r$n is incapacitated and will slowly die, if not aided.|w"; "|rYou are incapacitated and will slowly die, if not aided.|w"; "|r$n is stunned, but will probably recover.|w"; "|rYou are stunned, but will probably recover.|w"; "|R$n is DEAD!!|w"; "|RYou have been KILLED!!|w" (+7)
- Messages `one_hit` can show: "In your confused state, you attack yourself!"; "$n stumbles and in a confused state, hits $r."; "Sunlight glints off your sharpened blade!"; "Sunlight glints off $n's sharpened blade!"; "Sunlight glints off $n's sharpened blade!"; "With a blood curdling scream you leap forward swinging\n\ryour weapon in a great arc."; "$n screams and leaps forwards swinging $s weapon in a great arc."; "$n screams and leaps towards you swinging $s weapon in a great arc."
- Messages `char_update` can show: "$p goes out."; "$p flickers and goes out."; "$p flickers."; "$n fits violently before decaying in to a pile of dust."; "$n writhes in agony as plague sores erupt from $s skin."; "You writhe in agony from the plague."; "You feel hot and feverish."; "$n shivers and looks very ill."; "$n shivers and suffers."; "You shiver and suffer."
- Messages `spell_vampire` can show: "That isn't a weapon."; "The item must be carried to be vampiric."; "You suck the life force from the weapon leaving it hungry for blood."
- Balance numbers Explorer models from these files: Skills & spells

**To decide**

- [ ] What does a player notice before and after (messages, what they get, what's refused)?
- [ ] Can a careless or abusive player use the change (or the old behaviour) to their advantage?
- [ ] Does it change balance for any class, race or level range? If so, which Explorer numbers?

## 6. Documentation

- Help `LOAD` (area/Help.are:1322, level 96): Syntax: load mob <vnum>
- Help `HOLD REMOVE WEAR WIELD` (area/Help.are:699, level 0): Syntax: hold   <object>
- Help `SET` (area/Help.are:1335, level 98): Syntax: set mob   <mobile> <field> <value>
- Help `SETINFO` (area/Help.are:1352, level 0): This command can be used to store a message that other characters can
- Help `RESTORE` (area/Help.are:1447, level 96): Syntax: restore <character>
- Help `DAMAGE` mentions `damage` (area/Help.are:243)
- Help `COMPARE` mentions `damage` (area/Help.are:503)
- Help `WIMPY` mentions `damage` (area/Help.are:854)

**To decide**

- [ ] Does any help entry describe the behaviour being changed, and does it need rewording?
- [ ] Does the change need a note anywhere else (README, release notes, an issue comment)?

## 7. Test coverage

- `src/apps/test/pfutest.cpp`: includes update.hpp
- `src/test/DamageMessagesTest.cpp`: mentions damage
- `src/test/DamageToleranceTest.cpp`: mentions check_damage_tolerance, named after DamageTolerance.cpp, includes DamageTolerance.hpp
- `src/test/MobIndexDataTest.cpp`: mentions damage
- `src/test/ObjectTest.cpp`: includes update.hpp
- `src/test/magic_test.cpp`: named after magic.cpp
- `src/test/save_test.cpp`: includes update.hpp
- No unit test calls `one_hit`.
- No unit test calls `char_update`.
- No unit test calls `spell_vampire`.
- No unit test calls `update_pos`.
- Sim `scenarios/test_live_activities.py` sends `load`
- Sim `scenarios/test_live_bugs.py` sends `load`, `restore`
- Sim `scenarios/test_live_tactics.py` sends `load`, `wield`
- Sim `xania_sim/activities/gear.py` sends `wield`
- Sim `xania_sim/activities/items.py` sends `wield`
- Sim `xania_sim/activities/practice.py` sends `set`
- Sim `xania_sim/trials/skill.py` sends `load`
- Sim `xania_sim/trials/weapon.py` sends `load`, `wield`

**To decide**

- [ ] Which unit test pins the fixed behaviour (a test that fails before the change)?
- [ ] Which Sim trial or scenario shows it from a player's side, and should a new one be added?

## 8. History

- `damage` (288 lines) comes from 37 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (143 lines); `3152dd6` (2021-06-10, snellers): Refactoring damage(), one_hit(), multi_hit() and dam_message() to use a variant (18 lines); `67c49c7` (2020-08-04, Phil Norman): s/FALSE/false/g;s/TRUE/true/g (16 lines); `659cf22` (2021-11-06, snellers): Macro death: Damage Types (9 lines)
- `one_hit` (145 lines) comes from 26 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (75 lines); `3152dd6` (2021-06-10, snellers): Refactoring damage(), one_hit(), multi_hit() and dam_message() to use a variant (11 lines); `5216c9f` (2020-08-12, Matt Godbolt): act() refactor: introduce a strong type for "To" (5 lines); `fff7494` (2022-07-04, snellers): * Extract the to hit calculations into HitChance class and add tests. (5 lines)
- `char_update` (167 lines) comes from 39 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (79 lines); `805127b` (2020-08-30, Matt Godbolt): More changes to use AffectList functions directly (18 lines); `e3432e7` (2021-05-18, snellers): C++ifying player char 'conditions' (#256): (6 lines); `794d45b` (2023-09-04, snellers): - char_list takes ownership of all Chars. Replace all remaining naked new/delete! (4 lines)
- `spell_vampire` (21 lines) comes from 8 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (8 lines); `42406b7` (2021-11-14, snellers): Replace spell function void* with SpellTarget type. (4 lines); `a2c31f5` (2020-09-02, Matt Godbolt): Formatting changes. (3 lines); `7a71102` (2020-07-22, Matt Godbolt): Reformat all the code with clang-format (2 lines)
- `update_pos` (24 lines) comes from 5 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (10 lines); `9be5fe8` (2021-05-28, snellers): Convert Char position to an enum and wrapper class. Char position accessor methods. (7 lines); `7a71102` (2020-07-22, Matt Godbolt): Reformat all the code with clang-format (5 lines); `b1c5588` (2020-08-29, Matt Godbolt): CHAR_DATA -> Char (1 lines)
- `check_damage_tolerance` (46 lines) comes from 3 commits; the most: `659cf22` (2021-11-06, snellers): Macro death: Damage Types (23 lines); `71e55b1` (2021-07-04, snellers): merc.h cleanup: simplifying the concept of damage tolerance a bit, removing (14 lines); `1007912` (2021-10-29, snellers): Macro death: convert DMG_TOL_ bits to ToleranceFlag. (9 lines)
- Debug builds add `-fno-omit-frame-pointer -fsanitize=leak -fsanitize=address -fsanitize=undefined`
- Release builds add `-O2 -DNDEBUG -Wno-error=array-bounds`
- Upstream issue [#257](https://github.com/mattgodbolt/xania/issues/257) (open): Some melee skills should be dodgeable/parryable/shield blockable? (mentions `damage`, `one_hit`)
- Upstream issue [#207](https://github.com/mattgodbolt/xania/issues/207) (closed): "Bram" char has word of recall spell but no other spell groups (mentions `damage`)
- Upstream issue [#169](https://github.com/mattgodbolt/xania/issues/169) (closed): crash bug in death_cry() (mentions `damage`)
- Upstream issue [#166](https://github.com/mattgodbolt/xania/issues/166) (closed): IMM: Psychic tornado damage more than 1000 points (mentions `damage`)
- Upstream issue [#144](https://github.com/mattgodbolt/xania/issues/144) (open): comp command compares the damage on the weapon but not the additional stats (mentions `damage`)

**To decide**

- [ ] When did the behaviour start, and why did nobody notice until now?
- [ ] Did a toolchain change (compiler, flags, sanitizers) make it show, or change how it shows?
- [ ] Has upstream seen or tried this before, and does the change fit what was decided then?

## Gate plan

What `prototype` runs on the fork before this can ship:

- Builds: Debug (ASan, UBSan, LSan, libstdc++ assertions), Release (-O2)
- Unit tests: `src/apps/test/pfutest.cpp`, `src/test/DamageMessagesTest.cpp`, `src/test/DamageToleranceTest.cpp`, `src/test/MobIndexDataTest.cpp`, `src/test/ObjectTest.cpp`, `src/test/magic_test.cpp`, `src/test/save_test.cpp`
- Sim: `smoke`: the game still boots and a player can log in
- Sim: `hunt --minutes 5`: fights and what runs after a kill (autoloot) reach it
- Sim: `churn --minutes 5`: logins and quits reach it (lifetime bugs show here)
- Sim: `skill "vampire"`: `spell_vampire` is a spell
- Sim: `pytest scenarios/test_live_activities.py`: it sends the commands involved
- Sim: `pytest scenarios/test_live_bugs.py`: it sends the commands involved
- Sim: `pytest scenarios/test_live_tactics.py`: it sends the commands involved
