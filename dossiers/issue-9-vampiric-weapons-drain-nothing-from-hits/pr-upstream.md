`damage()` drained `(adjusted_damage / 100) * 10` hit points per hit for a vampiric weapon: integer arithmetic, so any hit under 100 drained **nothing**, and below about level 65 the flag did nothing at all. A live Sim trial showed it: no drain in 98 hits with the black demon blade at level 20, and steps of exactly 10 at levels 65 and 91. Following Faramir's answers on abraidotti/xania#9, the drain is now **5% of each ordinary weapon hit**, rounded. Spells and skill attacks such as backstab don't drain. Victims immune to negative energy give nothing, and resistant ones give less. The wielder heals no further than max hit points and loses a point of alignment per draining hit. Both sides now see a message. The victim's position is worked out after the drain, not before.

Reported as abraidotti/xania#9 (with the reproduction).

## What was wrong

| When | Commit | What happened |
|---|---|---|
| 2020-07-05 | `33a9553` | The initial import: `ch->hit += (dam / 100) * 10;` (and the same off the victim), inside `damage()`, after `update_pos(victim)`, with no cap and no message. Unchanged in meaning since; `dam` became `adjusted_damage`. |
| 2026-11-14 | | Found reading the weapon flags; measured live with a new Sim `weapon` trial (every round's hp change accounted for); filed as abraidotti/xania#9 with two options and seven questions. |
| 2026-11-18 | | Faramir's answers: option A at 5% rather than 10%; melee only, not backstab; no overheal; a drain message; an alignment cost; the undead/negative-energy check; no new vampiric weapons. |

## The fix

The drain itself is a small unit, `VampiricDrain` (new `VampiricDrain.hpp/.cpp`), so it can be unit-tested without a world:

```cpp
inline constexpr int Percent = 5;

int amount(const int damage_dealt, const DamageTolerance negative_tolerance) {
    if (damage_dealt <= 0)
        return 0;
    auto drained = (damage_dealt * Percent + 50) / 100;  // rounded: a hit of 10 drains 1
    switch (negative_tolerance) {
    case DamageTolerance::Immune: return 0;
    case DamageTolerance::Resistant: drained -= drained / 3; break;
    case DamageTolerance::Vulnerable: drained += drained / 2; break;
    case DamageTolerance::None: break;
    }
    return drained;
}

int drain(Char &wielder, Char &victim, const int damage_dealt) {
    const auto drained = amount(damage_dealt, check_damage_tolerance(&victim, DamageType::Negative));
    if (drained == 0)
        return 0;
    victim.hit -= drained;
    if (wielder.hit < wielder.max_hit)
        wielder.hit = std::min<int>(wielder.hit + drained, wielder.max_hit);
    wielder.alignment = std::max<int>(Alignment::Satanic, wielder.alignment - 1);
    return drained;
}
```

and `damage()` calls it in place of the old block:

```cpp
    victim->hit -= adjusted_damage;
    apply_immortal_floor();
    update_pos(victim);

    // A vampiric weapon drinks from ordinary weapon hits only: spells and skill attacks (backstab, bash...) arrive
    // here as a skill_type, and a hit that killed has nothing left to drink.
    wield = get_eq_char(ch, Worn::Wield);
    if (victim != ch && std::holds_alternative<const attack_type *>(atk_type) && !victim->is_pos_dead()
        && wield != nullptr && wield->type == ObjectType::Weapon
        && check_enum_bit(wield->value[4], WeaponFlag::Vampiric)) {
        if (VampiricDrain::drain(*ch, *victim, adjusted_damage) > 0) {
            act("$p drinks from $N.", ch, wield, victim, To::Char);
            act("You feel $p drinking your life.", ch, wield, victim, To::Vict);
            apply_immortal_floor();
            update_pos(victim);
        }
    }
```

**Why it stays in `damage()`.** The issue suggested moving the drain to `one_hit()`, next to Poisoned and Plagued. But `damage()` is where the damage actually dealt (after sanctuary, protection and tolerances) is known, and where the victim is certainly still in the world. After `damage()` returns from a killing blow, the victim may already be extracted. `damage()` can already tell an ordinary weapon hit apart: `one_hit` passes the weapon's `attack_type` when it has no skill, and a `skill_type` for backstab, bash, spells and everything else. The other caller with an `attack_type`, the self-damage in `update.cpp`, has `victim == ch`. So the check gets the "melee only" rule without changing `damage()`'s signature.

**Rounding.** At 5%, truncating would bring the old bug back at low levels: the level-11 black demon blade averages 14 a hit at level 20, and `14 * 5 / 100` is 0. Rounded, a hit of 10 or more drains at least 1: about 1 HP a hit at the low end, and 4-5 for the level-90/91 weapons (a level-91 knight's hits average 79 in the live trial).

**Live, in the gate.** Sim's `weapon` trial: a knight fights a 30,000 hp beggar for 40 rounds with each weapon, and every round's hp change (plus the damage taken) is compared with what each model of the drain predicts from the knight's own hits. A round is "explained" when a model predicts it exactly. 4 rounds in each fight held a regen tick, which no model explains.

| Weapon (knight level) | Side | Hits (mean) | Rounds explained by `(d/100)*10` | by 5% rounded | Drained | Drain messages |
|---|---|---|---|---|---|---|
| a black demon blade (20) | before | 73 (13.9) | **36** of 40 | 2 | 0 | 0 |
| | after | 70 (13.1) | 2 | **36** of 40 | 56 in the explained rounds | 63 |
| Executioner's Axe (65) | before | 68 (62.8) | **36** of 40 | 0 | 10 | 0 |
| | after | 60 (64.8) | 0 | **36** of 40 | 172 in the explained rounds | 60 |
| Sword of Ashen-Shugar (91) | before | 64 (82.2) | **36** of 40 | 0 | 100 | 0 |
| | after | 65 (79.5) | 0 | **36** of 40 | 232 in the explained rounds | 65 |

The blade's 63 messages are its 63 hits of 10 or more: smaller hits round to 0 and stay silent.

<details><summary>Alternatives considered</summary>

- **ROM 2.4's level-based extra hit (option B on abraidotti/xania#9).** Not chosen: Faramir chose option A.
- **10% (my original recommendation).** Faramir thought it a bit high; `Percent` is the one constant to tune.
- **Probabilistic rounding** (drain the remainder as a chance of +1) would make the expected drain exactly 5%, but the drain would then need the RNG and tests would need a mock. Rounding to the nearest point is deterministic and within half a point.

</details>

## What players will notice

A vampiric weapon now visibly drinks from every ordinary hit: "Executioner's Axe drinks from the beggar." to the wielder and "You feel Executioner's Axe drinking your life." to the victim. That's 5% of the hit, about 1 HP a hit with the level-11 black demon blade and 4-5 with the level-90/91 four. Backstab, bash, spells and breath don't drain, and the undead (immune to negative energy) give nothing. The wielder can't go over max hit points, and each draining hit costs a point of alignment. A fighter landing a few hundred hits an hour will drift toward evil within a session. Alignment decides which items zap you, and zapping happens after a kill (`fight.cpp:1375`), so a good-aligned wielder will eventually lose anti-evil gear. That's the cost of the weapon, as in ROM. Nothing an abusive player gains: the drain can't overheal, and skill attacks don't multiply it.

## Verification

Run by Xania Builder's gate, in the same configurations CI uses (Debug, which here means ASan + UBSan + libstdc++ assertions, and Release -O2):

| | Check | Expected | Result |
|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean |
| ✅ | Debug build of the branch | it compiles (-Werror) | built in 141 s |
| ✅ | Unit tests, Debug, the branch | every test passes | 1101 test cases and sections, all passed |
| ✅ | Release build of the branch | it compiles (-Werror) | built in 145 s |
| ✅ | Unit tests, Release, the branch | every test passes | 1101 test cases and sections, all passed |
| ➖ | Debug build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof |
| ➖ | Release build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof |
| ✅ | Debug build of the base as it is (for Sim's trials on it) | it compiles and installs | built in 2 s |
| ➖ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | the new tests pass on the branch; they can't build on the base (they test code the change adds), so the base side is Sim's |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 22 s |
| ✅ | Sim `weapon --rounds 40 --expect code today` on the base | the old (damage / 100) * 10 explains the rounds best for every weapon: nothing below 100 damage | no crash in 476 s |
| ✅ | Sim `weapon --rounds 40 --expect #9` on the branch | 5% of each hit, rounded, explains the rounds best for every weapon, with a drain message on each draining hit | no crash in 477 s |
| ✅ | Sim `skill bash --classes knight --fights 2` on the branch | it runs and finds no crash | no crash in 185 s (skill bash, kind combat skill, learned by knight 5) |
| ✅ | Sim `hunt --minutes 5` on the branch | it runs and finds no crash | no crash in 306 s (fights 12, bot errors 0, crashed False) |
| ✅ | Proof the bug was there before the change | a new test fails on the base, or a Sim trial shows the bug on the base | Sim showed it on the base: Sim `weapon --rounds 40 --expect code today` on the base |
| ➖ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | doesn't apply: the focus has no string_view indexing, before or after |

The new tests on the code **before** the change (the branch's tests applied to the base) and after it:

| Test | Before, Debug | Before, Release | After, Debug | After, Release |
|---|---|---|---|---|
| vampiric drain amount | not run | not run | pass | pass |
| vampiric drain | not run | not run | pass | pass |

<sub>g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake version 4.2.3; Ubuntu 26.04.1 LTS. Base `eec205e5fd`, branch `7901035a37`.</sub>

The same change went through the fork first, where this repo's own CI (format, Debug and Release build and test) passed: https://github.com/abraidotti/xania/pull/12.

## Not in this PR

- Xania Explorer: model the 5% drain in the weapon numbers.
- More vampiric weapons in the area files (Faramir: "that would be cool to have", but not now).

---

**More detail:** the [full write-up](https://abraidotti.github.io/xania-builder/dossiers/issue-9-vampiric-weapons-drain-nothing-from-hits/) has the root-cause analysis, every question the research asked and its answer, and the gate's logs. Researched and gated with [Xania Builder](https://github.com/abraidotti/xania-builder); players simulated with [Xania Sim](https://github.com/abraidotti/xania-sim).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
