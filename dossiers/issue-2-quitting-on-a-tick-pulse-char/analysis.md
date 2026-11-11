# Analysis: quitting on a tick pulse reads a freed Descriptor (#2)

Written by whoever made the change (here, Claude Code working from the dossier), answering the dossier's questions.
The facts it cites are in [dossier.md](dossier.md); the proof is in [gate.md](gate.md).

## In one paragraph

When a player quits, `extract_char` unhooks the descriptor from the character (`desc->character(nullptr)`) but
not the character from the descriptor: `ch->desc` keeps pointing at it. Since September 2023 an extracted
character isn't removed from `char_list` straight away; it waits there for `collect_all_garbage()` at the end of
the pulse. In between, the game loop frees the closed descriptor (`reap_closed()`) and, on the one pulse in 120
that is a tick, `char_update()` walks `char_list`, finds the departed character and follows its dangling
`ch->desc`. AddressSanitizer builds abort with a heap-use-after-free; other builds read freed memory, which is
usually harmless and occasionally isn't. The fix clears `ch->desc` in `extract_char`, so the character is detached
both ways before anything can free the descriptor.

## Root cause

| When | Commit | What happened |
|---|---|---|
| 2020-07-05 | `33a9553` | The Merc-era `extract_char` already only did `ch->desc->character = nullptr` (one way). Harmless then: the character was deleted on the spot, so nothing could follow its `desc` afterwards. |
| 2023-09-08 | `dc2b39c` | *"Implement new solution for collecting garbage Object & Char. This enables extract_char() and extract_obj() to mark entities reapable while the owning vector is being iterated on."* `char_list.erase(...)` becomes `reapable_chars.push_back(ch)`. The character now outlives the call until the end of the pulse, still pointing at its descriptor. |
| | | From here on, a quit (or an immortal's `purge` of a player) followed in the same pulse by a tick reads the freed descriptor. |
| 2026-11-09 | | Xania Sim's regression suite hits it about one run in three on an ASan build; its `churn` trial then reproduces it in about a minute (42 quits). Filed as #2. |

The order of events in one pulse (`MudImpl::game_loop`):

1. Input: the player's `quit` runs `do_quit`: `save_char_obj`, `d = ch->desc`, `extract_char(ch, true)`, `d->close()`.
2. MudImpl.cpp:327, `descriptors().reap_closed()`: the closed `Descriptor` is erased from its map and freed.
3. MudImpl.cpp:332, `update_handler()`: on a tick pulse it runs `char_update()` (update.cpp:882), which walks
   `char_list`, where the extracted character still is.
4. update.cpp:890, `collect_all_garbage()`: only now is the character removed and deleted.

Step 3 follows the dangling `ch->desc` in (at least) three places:

| Where | How it reaches `desc` | Seen |
|---|---|---|
| update.cpp:705 `ch->is_immortal()` | `get_trust()` → `desc->is_switched()` | the ASan report in #2 |
| update.cpp:678 `mana_gain(ch)` | `get_skill()` → `Char::player()` → `desc->person()` | Sim's area trial, a second signature with the same cause |
| update.cpp:815 the autosave loop | `ch->desc != nullptr && ch->desc->channel() % save_every_n == save_number` | by reading: and if the stale channel number matched, `save_char_obj` would re-save a character that had already quit, with `in_room == nullptr` |

A tick is every 120th pulse (`PULSE_TICK` = 30 s at 4 pulses a second, update.cpp:879), so a single quit has a
1-in-120 chance of landing on one: rare for people, routine for anything that connects a lot. (The issue said
ticks come every 30-60 s; the code says exactly 30.)

## The fix

```cpp
// Detach both ways. ch stays in char_list until collect_all_garbage() at the end of the pulse, and the descriptor
// may be closed and freed before then (do_quit closes it, DescriptorList::reap_closed() frees it), so the
// character must not keep pointing at it: char_update()'s get_trust(), get_skill() and autosave all follow
// ch->desc.
if (ch->desc) {
    ch->desc->character(nullptr);
    ch->desc = nullptr;
}
```

Every reader in `char_update` already treats a null `desc` as "no connection" (a link-dead player has one), so the
departed character is simply treated as link-dead for the rest of its last pulse: no trust lookup through the
descriptor, no autosave.

The callers are fine with it: `do_quit` and `do_purge` both copy `ch->desc` into a local *before* calling
`extract_char`, and close that; `raw_kill` of a player uses `extract_char(victim, false)`, which returns before
this code (the player stays connected, and the new test checks that); the other callers extract NPCs, which only
have a descriptor while an immortal is switched into them, and `extract_char` already returns the immortal to
their own body (`do_return`) before this point.

### Alternatives considered

- **Skip extracted characters in `char_update`** (the issue's second suggestion): `char_update` would need to know
  who's in `reapable_chars`, and so would the other per-tick loops. It's the better long-term invariant (see
  below), but it's a wider change than the bug needs.
- **Run `collect_all_garbage()` before `update_handler`, or `reap_closed()` after it**: changes the order of the
  game loop for everything, to fix one dangling pointer. Rejected.
- **Have `Descriptor::close()` or `reap_closed()` clear its character's `desc`**: the descriptor no longer knows the
  character by then (`extract_char` cleared that link first), so it can't.

## Answers to the dossier's questions

**1. Explorer.** No Explorer check covers lifetimes; nothing to update.

**2. Architecture.** The fix is in `extract_char`, the one place every exit from the world goes through, so it
covers `quit`, `delete`, `deny` (both via `do_quit`), `purge` of a player, and the idle auto-quit in
`char_update` itself. Every caller still gets what it expects (see The fix).

**3. Design patterns.** It mirrors the line above it: the code already cleared one side of the link; now it clears
both, the usual way to break a two-way pointer.

**4. Technical debt.** Pays down the dangling pointer. Deliberately leaves the larger debt the dossier's research
points at: since `dc2b39c`, an extracted character still gets the rest of its pulse in every loop over
`char_list` (regeneration, affects wearing off, plague and poison damage), with `in_room == nullptr`. It no longer
reads freed memory, but it's still processed. That's worth its own issue: a `Char::is_extracted()` that loops
skip, or a filtered view of `char_list`.

**5. Gameplay.** Nothing a player can see: quitting works as before. A debug MUD stops crashing when someone quits
on a tick, and a release MUD stops reading freed memory then (and can no longer re-save a departed character on
a stale channel number).

**6. Documentation.** None needed.

**7. Tests.** `ExtractCharTest.cpp`: after `extract_char(ch, true)` neither side points at the other and the
character is queued for garbage collection; after `extract_char(ch, false)` (a player's death) the connection is
kept. On the base the first section fails (`ch->desc` is still set) in both builds. From the player's side, Sim's
`churn` (six bots creating characters and quitting in a loop on the AddressSanitizer build) reproduces the crash on
the base and has to run clean for 15 minutes on the branch.

Because the bug depends on timing, a clean run only counts as evidence if it's long enough. In the gate, the base
crashed after **42 quits** (68 s); the branch survived **1,260 quits** in 15 minutes. If each quit had the 1-in-120
chance of landing on a tick worked out above, the chance of 1,260 quits all missing with the bug still there would
be (119/120)^1260 ≈ 0.000026, about 1 in 38,000. (That model is an estimate: bots quitting in step aren't fully
independent. It's the order of magnitude that matters.)

**8. History.** Answered under Root cause. Upstream: upstream #182 (closed) was about lists mutated while iterated, the
problem `dc2b39c` solved; upstream #127 (closed, "Heap use after free in xania") was an earlier lifetime bug in the same
area.

## Follow-ups (not in this PR)

- An issue: extracted characters are still processed for the rest of their pulse (above).
- Xania Sim: mark the two `Descriptor` use-after-free findings fixed once this is merged.
