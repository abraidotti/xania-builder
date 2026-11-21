`spell_harm` has dealt `DamageType::Fire` since d165e77 (2020), the commit that moved the direct-damage spells to table lookups. It's the only spell whose damage type that commit changed, and harm shares its damage table with fireball (`FireballHarmDamage`), so it looks like a copy-paste slip. The original import, the three cause spells and ROM 2.4 all deal Harm damage, which `check_damage_tolerance` tests against a mob's **Magic** tolerance. So harm has been hurting Magic-immune mobs, shrugged off by fire-immune ones, doing 1.5x to trolls, and using fire verbs ("roasts", "chars"). This puts back `DamageType::Harm`, option A on #11, which Faramir chose ("moving it to Fire was probably a mistake"). Damage amounts don't change.

Fixes #11.

## What was wrong

| When | Commit | What happened |
|---|---|---|
| 2020-07-05 | `33a9553` | The initial import: `damage( ch, victim, dam, sn, DAM_HARM );`, like `cause light`, `cause serious` and `cause critical`. |
| 2020-09-23 | `d165e77` | *"Make most of the direct damage spells use table based lookups."* harm gets `FireballHarmDamage`, the table it shares with fireball, and `DAM_FIRE`. Every other spell in the commit keeps its type. |
| 2021-11-06 | `659cf22` | *"Macro death: Damage Types"*: `DAM_FIRE` becomes `DamageType::Fire`, unchanged in meaning. |
| 2026-11-14 | | Found reading the direct-damage spells (harm was the odd one out in its group), filed as #11 with the counts, and confirmed live with a Sim known-bug check. |
| 2026-11-18 | | Option A agreed on #11. |

## The fix

```cpp
void spell_harm(int sn, int level, Char *ch, const SpellTarget &spell_target) {
    ...
    damage(ch, victim, dam_level.first, &skill_table[sn], DamageType::Harm);
}
```

One word at `magic.cpp:2454`. Everything that depends on the type then follows on its own: `DamageTolerance.cpp` already maps Harm to the Magic tolerance (covered by `DamageToleranceTest.cpp`), `DamageMessages.cpp` picks the generic verbs the cause spells use, and `fight.cpp`'s mount-fall code already has its own `DamageType::Harm` case.

**Live, in the gate.** Sim's known-bug check casts each spell at a freshly loaded mob, as a level-30 cleric with both at 100%:

| Mob | Its tolerances | `cause critical` (Harm, the control) | `harm` before | `harm` after |
|---|---|---|---|---|
| the snotling (13015) | immune to Magic | unaffected | hurts it, with a fire verb | **unaffected** |
| the red bat (4151) | immune to Fire | MASSACRES (kills it) | unaffected | **UNSPEAKABLE** (kills it) |

On the base the check passes (the bug is there); on the branch it fails at its "harm deals Harm damage again, retire this test" assertion.

<details><summary>Alternatives considered</summary>

- **Keep Fire on purpose (option B on #11).** No code change, but harm would stay a second fire nuke for clerics who take Attack (flamestrike) too, the help entry would have to stop grouping it with the cause spells, and the comment above `spell_harm` would need to say why. Not chosen.
- **Give Harm its own damage verbs.** Not in this fix (question 3 on #11): the whole Harmful group stays consistent, and new verbs can be their own change.

</details>

## What players will notice

Harm hurts the same amount as before, but through Magic tolerance instead of Fire: of the 334 placed mobs whose damage changes, 145 take more (giants, modrons, newts, fire-immune mobs such as the fire elemental and the red bat), 189 take less (trolls lose their fire vulnerability, and many town NPCs that `is_safe` already protects are immune to Magic), and the 5 Dwarven Day Care dolls (levels 1-3) become immune, as they already are to the cause spells. Its messages use the generic verbs the cause spells use instead of fire's, and a rider hit by harm is thrown more often (`fight.cpp`'s Harm case: +10 to the fall chance rather than fire's +40, which clamps to "never"). Players are barely affected as victims: no PC race has a Fire or Magic tolerance. Nothing an abusive player gains.

## Verification

Run by Xania Builder's gate, in the same configurations CI uses (Debug, which here means ASan + UBSan + libstdc++ assertions, and Release -O2):

| | Check | Expected | Result |
|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean |
| ✅ | Debug build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) |
| ✅ | Unit tests, Debug, the branch | every test passes | 1090 test cases and sections, all passed |
| ✅ | Release build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) |
| ✅ | Unit tests, Release, the branch | every test passes | 1090 test cases and sections, all passed |
| ✅ | Debug build of the base with the branch's tests | it compiles (-Werror) | up to date (nothing to rebuild) |
| ✅ | Release build of the base with the branch's tests | it compiles (-Werror) | up to date (nothing to rebuild) |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 22 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k harm_deals_fire` on the base | harm hurts the Magic-immune snotling with a fire verb and can't touch the Fire-immune bat: the opposite of cause critical | pytest exit 0: 1 passed, 6 deselected in 41.59s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k harm_deals_fire` on the branch | harm behaves like cause critical: the snotling is unaffected (Magic immunity), so the known-bug check reports the bug gone | pytest exit 1: 1 failed, 6 deselected in 42.03s |
| ✅ | Sim `skill harm --classes cleric --fights 2` on the branch | it runs and finds no crash | no crash in 126 s (skill harm, kind spell, learned by cleric 23) |
| ✅ | Proof the bug was there before the change | a new test fails on the base, or a Sim trial shows the bug on the base | Sim showed it on the base: Sim `pytest scenarios/test_live_bugs.py -k harm_deals_fire` on the base |
| ➖ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | doesn't apply: the focus has no string_view indexing, before or after |

<sub>g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake version 4.2.3; Ubuntu 26.04.1 LTS. Base `eec205e5fd`, branch `58ba177c28`.</sub>

## Not in this PR

- Xania Sim: retire the `harm_deals_fire` known-bug check once this is merged.

---

**More detail:** the [full write-up](https://abraidotti.github.io/xania-builder/dossiers/issue-11-harm-deals-fire-damage-unlike-the/) has the root-cause analysis, every question the research asked and its answer, and the gate's logs. Researched and gated with [Xania Builder](https://github.com/abraidotti/xania-builder); players simulated with [Xania Sim](https://github.com/abraidotti/xania-sim).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
