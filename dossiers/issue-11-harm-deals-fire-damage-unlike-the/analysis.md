# Analysis: harm deals fire damage, unlike the rest of the Harmful group (#11)

Written by whoever made the change (here, Claude Code working from the dossier), answering the dossier's questions.
The facts it cites are in [dossier.md](dossier.md); the proof is in [gate.md](gate.md).

## In one paragraph

`spell_harm` has dealt `DamageType::Fire` since d165e77 (2020), the commit that moved the direct-damage spells to
table lookups. It's the only spell whose damage type that commit changed, and harm shares its damage table with
fireball (`FireballHarmDamage`), so it looks like a copy-paste slip. The original import, the three cause spells
and ROM 2.4 all deal Harm damage, which `check_damage_tolerance` tests against a mob's **Magic** tolerance. So harm
has been hurting Magic-immune mobs, shrugged off by fire-immune ones, doing 1.5x to trolls, and using fire verbs
("roasts", "chars"). This puts back `DamageType::Harm`, option A on #11, which Faramir chose ("moving it to Fire
was probably a mistake"). Damage amounts don't change.

## Root cause

| When | Commit | What happened |
|---|---|---|
| 2020-07-05 | `33a9553` | The initial import: `damage( ch, victim, dam, sn, DAM_HARM );`, like `cause light`, `cause serious` and `cause critical`. |
| 2020-09-23 | `d165e77` | *"Make most of the direct damage spells use table based lookups."* harm gets `FireballHarmDamage`, the table it shares with fireball, and `DAM_FIRE`. Every other spell in the commit keeps its type. |
| 2021-11-06 | `659cf22` | *"Macro death: Damage Types"*: `DAM_FIRE` becomes `DamageType::Fire`, unchanged in meaning. |
| 2026-11-14 | | Found reading the direct-damage spells (harm was the odd one out in its group), filed as #11 with the counts, and confirmed live with a Sim known-bug check. |
| 2026-11-18 | | Option A agreed on #11. |

Nobody noticed for six years because nothing crashes and the damage amounts are right: only the tolerances, the
verbs and the mount-fall chance changed, and those show only against particular mobs.

## The fix

```cpp
void spell_harm(int sn, int level, Char *ch, const SpellTarget &spell_target) {
    ...
    damage(ch, victim, dam_level.first, &skill_table[sn], DamageType::Harm);
}
```

One word at `magic.cpp:2454`. Everything that depends on the type then follows on its own: `DamageTolerance.cpp`
already maps Harm to the Magic tolerance (covered by `DamageToleranceTest.cpp`), `DamageMessages.cpp` picks the
generic verbs the cause spells use, and `fight.cpp`'s mount-fall code already has its own `DamageType::Harm` case.

**Live, in the gate.** Sim's known-bug check casts each spell at a freshly loaded mob, as a level-30 cleric with
both at 100%:

| Mob | Its tolerances | `cause critical` (Harm, the control) | `harm` before | `harm` after |
|---|---|---|---|---|
| the snotling (13015) | immune to Magic | unaffected | hurts it, with a fire verb | **unaffected** |
| the red bat (4151) | immune to Fire | MASSACRES (kills it) | unaffected | **UNSPEAKABLE** (kills it) |

On the base the check passes (the bug is there); on the branch it fails at its "harm deals Harm damage again, retire
this test" assertion.

### Alternatives considered

- **Keep Fire on purpose (option B on #11).** No code change, but harm would stay a second fire nuke for clerics who
  take Attack (flamestrike) too, the help entry would have to stop grouping it with the cause spells, and the
  comment above `spell_harm` would need to say why. Not chosen.
- **Give Harm its own damage verbs.** Not in this fix (question 3 on #11): the whole Harmful group stays consistent,
  and new verbs can be their own change.

## Answers to the dossier's questions

**1. Explorer.** Explorer's combat model already treats Harm as Magic (`tolerance()` in `assess/combat.py`), so its
predictions for harm become right once the server matches; no Explorer change is needed.

**2. Architecture.** One call in `spell_harm` (`magic.cpp`). Its callers: players casting harm (clerics at 23,
knights at 26, through the Harmful group), `spec_cast_cleric` mobs from level 30, and the bone bomb in Flying Citadel
(obj 13023), all through the spell function, so all get the fix.

**3. Design patterns.** Matches `spell_cause_light`, `spell_cause_serious` and `spell_cause_critical` exactly.

**4. Technical debt.** None added. The comment above `spell_harm` (about level and mana efficiency) stays correct.

**5. Gameplay.** Harm hurts the same amount as before, but through Magic tolerance instead of Fire: of the 334
placed mobs whose damage changes, 145 take more (giants, modrons, newts, fire-immune mobs such as the fire elemental
and the red bat), 189 take less (trolls lose their fire vulnerability, and many town NPCs that `is_safe` already
protects are immune to Magic), and the 5 Dwarven Day Care dolls (levels 1-3) become immune, as they already are to
the cause spells. Its messages use the generic verbs the cause spells use instead of fire's, and a rider hit by harm is
thrown more often (`fight.cpp`'s Harm case: +10 to the fall chance rather than fire's +40, which clamps to "never").
Players are barely affected as victims: no PC race has a Fire or Magic tolerance. Nothing an abusive player gains.

**6. Documentation.** None needed: `help harm` already lists it with the cause spells.

**7. Tests.** No unit test can call `spell_harm` without a world (`damage()` needs rooms, fighting and the global
RNG), and the type mapping itself is already pinned by `DamageToleranceTest.cpp` (Harm -> Magic). So the test is
Sim's known-bug check `test_harm_deals_fire_damage_not_harm`: a level-30 cleric casts harm and, as the control,
cause critical at a Magic-immune snotling (13015) and a Fire-immune red bat (4151). On the base harm does the
opposite of cause critical; on the branch it does the same, so the check fails, as it says it should once this is
fixed. Sim's skill trial casts harm through whole fights as a cleric.

**8. History.** Answered under Root cause. No toolchain change involved. Upstream: no issue or PR mentions it.

## Follow-ups (not in this PR)

- Xania Sim: retire the `harm_deals_fire` known-bug check once this is merged.
