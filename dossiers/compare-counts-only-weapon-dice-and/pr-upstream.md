`compare` scored weapons by their dice alone and armour by three of its four AC values, ignoring every affect, and said "You can't compare" about rings, amulets and lights. Counted from the area files, that gets the verdict wrong for 19% of weapon pairs and 12% of armour pairs within five levels of each other. Damroll and AC affects alone flip them. This is option B from #144, which Faramir leaned towards: a better verdict (damroll for weapons; AC vs magic and AC affects for armour), then one vague line for each other stat that differs, with no numbers, so `identify` and `lore` stay worth having. Rings and other jewellery that share a wear slot get the stat lines alone. The other five questions on the issue take the recommended answers.

Closes #144.

## What was wrong

| When | Commit | What happened |
|---|---|---|
| 2020-07-05 | `33a9553` | The initial import: `do_compare` scores weapons `(1 + v2) * v1` and armour `v0 + v1 + v2`, as Merc did; `help compare` says it "doesn't consider any special modifiers". |
| | #144 | Reported in game by Wandera: *"comp command compares the damage on the weapon but not the additional stats"*. |
| 2026-11-14 | | Options A/B/C and six questions posted on #144, with counts from the area files. |
| 2026-11-18 | | Faramir: *"I'd lean towards option B."* |

## The fix

The scoring moves out of `do_compare` into a pure unit, `ObjectComparison` (new `ObjectComparison.hpp/.cpp`), that returns the `act()` lines to send. `do_compare` keeps its argument handling and sends them:

```cpp
    for (const auto line : ObjectComparison::compare(*obj1, *obj2).lines)
        act(line, ch, obj1, obj2, To::Char);
```

What `compare` decides:

| | Verdict | Stat lines |
|---|---|---|
| two weapons | dice average + damroll (`(1 + v2) * v1 + 2 * damroll`, both doubled to stay whole) | hitroll, AC, saves, str/dex/int/wis/con, hp, mana, moves |
| two pieces of armour | `v0 + v1 + v2 + v3 - 4 * AC affects` (an AC affect changes all four ACs) | the same, with damroll instead of AC |
| anything else sharing a wear slot (rings, amulets, a light and a held item...) | none | all of them, AC included (an armour item's own AC values count) |
| a weapon and something else, or no shared slot | "You can't compare $p and $P." | |

Each line says which way, never how much: "$p would make you weaker.", "$p would guard you better against magic.". The five saving throw locations count as one line, because `affect_modify` adds them all to the same `saving_throw`. Affects are summed the way `equip_char` applies them: the object's own, plus its index's unless it's enchanted. `compare <obj>` with one argument now finds a worn item in the same slot of any type, not only the same type, so a treasure ring is compared with a worn armour ring.

The issue's examples, now (from the unit tests and the Sim check):

```
> compare pin elven
A very sharp pin looks better than a long elven dagger.
A very sharp pin would make you weaker.
A very sharp pin would make you less healthy.

> compare protection pink
A ring of protection would protect you better than a pink ice ring.
A ring of protection would guard you better against magic.
A ring of protection would make you weaker.
A ring of protection would make you less healthy.
```

Before, the first said "A very sharp pin looks worse than a long elven dagger." and the second "You can't compare a ring of protection and a pink ice ring."

<details><summary>Alternatives considered</summary>

- **A: a better verdict only.** Fixes the 19%/12% flips but still ignores hp, mana, stats and saves. Not chosen.
- **C: exact side-by-side numbers.** Clearest, but it hands out `identify`'s output for free. Not chosen.
- **Weapon flags (sharp, vampiric, flaming...)** in the verdict: question 6 says not in this change (vampiric is being reworked in abraidotti/xania#9 at the same time).

</details>

## What players will notice

`compare` now picks the weapon that really hits harder when damroll differs, and the armour that really protects better when AC vs magic or AC affects differ. It then names, without numbers, every other way the first item would change you: stronger or weaker, healthier, better guarded against magic, more mana... Rings, amulets and other jewellery can be compared for the first time. Nothing an abusive player gains: the lines are directions only, and `identify`/`lore` still give the numbers.

## Verification

Run by Xania Builder's gate, in the same configurations CI uses (Debug, which here means ASan + UBSan + libstdc++ assertions, and Release -O2):

| | Check | Expected | Result |
|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean |
| ✅ | Debug build of the branch | it compiles (-Werror) | built in 14 s |
| ✅ | Unit tests, Debug, the branch | every test passes | 1107 test cases and sections, all passed |
| ✅ | Release build of the branch | it compiles (-Werror) | built in 11 s |
| ✅ | Unit tests, Release, the branch | every test passes | 1107 test cases and sections, all passed |
| ➖ | Debug build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof |
| ➖ | Release build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof |
| ✅ | Debug build of the base as it is (for Sim's trials on it) | it compiles and installs | built in 2 s |
| ➖ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | the new tests pass on the branch; they can't build on the base (they test code the change adds), so the base side is Sim's |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 21 s |
| ✅ | Sim `pytest scenarios/test_live_compare.py` on the base | compare says the pin looks worse than the dagger, and can't compare the two rings | pytest exit 1: 1 failed in 32.43s |
| ✅ | Sim `pytest scenarios/test_live_compare.py` on the branch | the pin looks better (its damroll counts), with the strength and hp lines; the rings get their four stat lines | pytest exit 0: 1 passed in 32.24s |
| ✅ | Proof the bug was there before the change | a new test fails on the base, or a Sim trial shows the bug on the base | Sim showed it on the base: Sim `pytest scenarios/test_live_compare.py` on the base |
| ➖ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | doesn't apply: the focus has no string_view indexing, before or after |

The new tests on the code **before** the change (the branch's tests applied to the base) and after it:

| Test | Before, Debug | Before, Release | After, Debug | After, Release |
|---|---|---|---|---|
| compare weapons | not run | not run | pass | pass |
| compare armour | not run | not run | pass | pass |
| compare things worn in the same place | not run | not run | pass | pass |
| a weapon and something else can't be compared | not run | not run | pass | pass |

<sub>g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake version 4.2.3; Ubuntu 26.04.1 LTS. Base `eec205e5fd`, branch `937fd66f2b`.</sub>

The same change went through the fork first, where this repo's own CI (format, Debug and Release build and test) passed: https://github.com/abraidotti/xania/pull/14.

## Not in this PR

- Weapon flags in `compare`, once abraidotti/xania#9's vampiric rework settles (question 6).
- `AFFECT_DATA::worth()`: the unreachable AC/saves branch and the missing `break` after mana/hit/move.

---

**More detail:** the [full write-up](https://abraidotti.github.io/xania-builder/dossiers/compare-counts-only-weapon-dice-and/) has the root-cause analysis, every question the research asked and its answer, and the gate's logs. Researched and gated with [Xania Builder](https://github.com/abraidotti/xania-builder); players simulated with [Xania Sim](https://github.com/abraidotti/xania-sim).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
