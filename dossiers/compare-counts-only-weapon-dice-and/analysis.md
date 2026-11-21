# Analysis: compare counts only weapon dice and three armour values (upstream #144)

Written by whoever made the change (here, Claude Code working from the dossier), answering the dossier's questions.
The facts it cites are in [dossier.md](dossier.md); the proof is in [gate.md](gate.md).

## In one paragraph

`compare` scored weapons by their dice alone and armour by three of its four AC values, ignoring every affect, and
said "You can't compare" about rings, amulets and lights. Counted from the area files, that gets the verdict wrong
for 19% of weapon pairs and 12% of armour pairs within five levels of each other. Damroll and AC affects alone flip
them. This is option B from upstream #144, which Faramir leaned towards: a better verdict (damroll for weapons; AC vs
magic and AC affects for armour), then one vague line for each other stat that differs, with no numbers, so
`identify` and `lore` stay worth having. Rings and other jewellery that share a wear slot get the stat lines alone.
The other five questions on the issue take the recommended answers.

## Root cause

| When | Commit | What happened |
|---|---|---|
| 2020-07-05 | `33a9553` | The initial import: `do_compare` scores weapons `(1 + v2) * v1` and armour `v0 + v1 + v2`, as Merc did; `help compare` says it "doesn't consider any special modifiers". |
| | upstream #144 | Reported in game by Wandera: *"comp command compares the damage on the weapon but not the additional stats"*. |
| 2026-11-14 | | Options A/B/C and six questions posted on upstream #144, with counts from the area files. |
| 2026-11-18 | | Faramir: *"I'd lean towards option B."* |

## The fix

The scoring moves out of `do_compare` into a pure unit, `ObjectComparison` (new `ObjectComparison.hpp/.cpp`), that
returns the `act()` lines to send. `do_compare` keeps its argument handling and sends them:

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

Each line says which way, never how much: "$p would make you weaker.", "$p would guard you better against magic.".
The five saving throw locations count as one line, because `affect_modify` adds them all to the same
`saving_throw`. Affects are summed the way `equip_char` applies them: the object's own, plus its index's unless it's
enchanted. `compare <obj>` with one argument now finds a worn item in the same slot of any type, not only the same
type, so a treasure ring is compared with a worn armour ring.

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

Before, the first said "A very sharp pin looks worse than a long elven dagger." and the second "You can't compare a
ring of protection and a pink ice ring."

### Alternatives considered

- **A: a better verdict only.** Fixes the 19%/12% flips but still ignores hp, mana, stats and saves. Not chosen.
- **C: exact side-by-side numbers.** Clearest, but it hands out `identify`'s output for free. Not chosen.
- **Weapon flags (sharp, vampiric, flaming...)** in the verdict: question 6 says not in this change (vampiric is
  being reworked in #9 at the same time).

## Answers to the dossier's questions

The six questions on upstream #144, with the answers this follows (question 1 answered by Faramir, 2-6 the
recommended answers):

1. **Style:** B. 2. **Damroll in the weapon verdict:** yes, flat damage on every hit. 3. **Hitroll:** its own
line, since hit chance and damage don't share a unit. 4. **Armour:** count `v3` and AC affects, an AC affect once
per AC value. 5. **Rings, amulets, lights:** compare by stat lines when they share a wear slot. 6. **Weapon flags:**
not in this change.

**1. Explorer.** Explorer's area parser gave the counts (19% / 12% flips). Its item worth (`entity_balance.cpp`)
isn't what `compare` uses and isn't changed.

**2. Architecture.** `do_compare` and `find_comparable` in `act_info.cpp`, and the new `ObjectComparison` unit.
Only the `compare` command calls them.

**3. Design patterns.** Affects are summed as `equip_char` / `unequip_char` apply them (index affects unless
`enchanted`, then the object's own), and saves grouped as `AFFECT_DATA::modify` groups them. The lines are `act()`
formats, so `$p` / `$P` follow the viewer's ability to see each object, as before.

**4. Technical debt.** The scoring is now testable without a character or a room. Leaves `AFFECT_DATA::worth()`
alone. It has an unreachable branch (`if (modifier < 0) if (modifier > 0)`) and a missing `break`, a separate fix.

**5. Gameplay.** `compare` now picks the weapon that really hits harder when damroll differs, and the armour that
really protects better when AC vs magic or AC affects differ. It then names, without numbers, every other way the
first item would change you: stronger or weaker, healthier, better guarded against magic, more mana... Rings,
amulets and other jewellery can be compared for the first time. Nothing an abusive player gains: the lines are
directions only, and `identify`/`lore` still give the numbers.

**6. Documentation.** `help compare` rewritten: what the verdict counts, the stat lines, jewellery, and that weapon
flags aren't compared. The old "doesn't consider any special modifiers" line is gone.

**7. Tests.** `ObjectComparisonTest.cpp` builds the issue's real items (pin 16018, elven dagger 1603, rings 3043
and 6601) and others: the damroll flip, the hitroll line, damroll staying out of a weapon's lines, an enchanted
item ignoring its index's affects, AC vs magic and AC affects in the armour verdict, armour's damroll and saves
lines, the rings' four lines, saving throws as one, an armour ring's own AC, and what can't be compared. From the
player's side, Sim's feature check `test_live_compare.py` gives a new character the four items and types both
commands: it fails on the base and passes on the branch.

**8. History.** Answered under Root cause.

## Follow-ups (not in this PR)

- Weapon flags in `compare`, once #9's vampiric rework settles (question 6).
- `AFFECT_DATA::worth()`: the unreachable AC/saves branch and the missing `break` after mana/hit/move.
