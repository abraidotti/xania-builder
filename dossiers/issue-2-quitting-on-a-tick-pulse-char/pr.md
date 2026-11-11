When a player quits, `extract_char` unhooks the descriptor from the character (`desc->character(nullptr)`) but not the character from the descriptor: `ch->desc` keeps pointing at it. Since September 2023 an extracted character isn't removed from `char_list` straight away; it waits there for `collect_all_garbage()` at the end of the pulse. In between, the game loop frees the closed descriptor (`reap_closed()`) and, on the one pulse in 120 that is a tick, `char_update()` walks `char_list`, finds the departed character and follows its dangling `ch->desc`. AddressSanitizer builds abort with a heap-use-after-free; other builds read freed memory, which is usually harmless and occasionally isn't. The fix clears `ch->desc` in `extract_char`, so the character is detached both ways before anything can free the descriptor.

Fixes #2.

## What was wrong

| When | Commit | What happened |
|---|---|---|
| 2020-07-05 | `33a9553` | The Merc-era `extract_char` already only did `ch->desc->character = nullptr` (one way). Harmless then: the character was deleted on the spot, so nothing could follow its `desc` afterwards. |
| 2023-09-08 | `dc2b39c` | *"Implement new solution for collecting garbage Object & Char. This enables extract_char() and extract_obj() to mark entities reapable while the owning vector is being iterated on."* `char_list.erase(...)` becomes `reapable_chars.push_back(ch)`. The character now outlives the call until the end of the pulse, still pointing at its descriptor. |
| | | From here on, a quit (or an immortal's `purge` of a player) followed in the same pulse by a tick reads the freed descriptor. |
| 2026-11-09 | | Xania Sim's regression suite hits it about one run in three on an ASan build; its `churn` trial then reproduces it in about a minute (42 quits). Filed as #2. |

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

Every reader in `char_update` already treats a null `desc` as "no connection" (a link-dead player has one), so the departed character is simply treated as link-dead for the rest of its last pulse: no trust lookup through the descriptor, no autosave.

The callers are fine with it: `do_quit` and `do_purge` both copy `ch->desc` into a local *before* calling `extract_char`, and close that; `raw_kill` of a player uses `extract_char(victim, false)`, which returns before this code (the player stays connected, and the new test checks that); the other callers extract NPCs, which only have a descriptor while an immortal is switched into them, and `extract_char` already returns the immortal to their own body (`do_return`) before this point.

<details><summary>Alternatives considered</summary>

- **Skip extracted characters in `char_update`** (the issue's second suggestion): `char_update` would need to know who's in `reapable_chars`, and so would the other per-tick loops. It's the better long-term invariant (see below), but it's a wider change than the bug needs.
- **Run `collect_all_garbage()` before `update_handler`, or `reap_closed()` after it**: changes the order of the game loop for everything, to fix one dangling pointer. Rejected.
- **Have `Descriptor::close()` or `reap_closed()` clear its character's `desc`**: the descriptor no longer knows the character by then (`extract_char` cleared that link first), so it can't.

</details>

## What players will notice

Nothing a player can see: quitting works as before. A debug MUD stops crashing when someone quits on a tick, and a release MUD stops reading freed memory then (and can no longer re-save a departed character on a stale channel number).

## Verification

Run by Xania Builder's gate, in the same configurations CI uses (Debug, which here means ASan + UBSan + libstdc++ assertions, and Release -O2):

| | Check | Expected | Result |
|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean |
| ✅ | Debug build of the branch | it compiles (-Werror) | built in 23 s |
| ✅ | Unit tests, Debug, the branch | every test passes | 1074 test cases and sections, all passed |
| ✅ | Release build of the branch | it compiles (-Werror) | built in 21 s |
| ✅ | Unit tests, Release, the branch | every test passes | 1074 test cases and sections, all passed |
| ✅ | Debug build of the base with the branch's tests | it compiles (-Werror) | built in 20 s |
| ✅ | Release build of the base with the branch's tests | it compiles (-Werror) | built in 21 s |
| ✅ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | 1 of 1 new tests pin the fix |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 21 s |
| ✅ | Sim `churn --bots 6 --minutes 15` on the base | it reproduces `heap-use-after-free` (the bug is there) | reproduced: xania crashed (AddressSanitizer: heap-use-after-free) in Descriptor::is_switched (Descriptor.hpp) |
| ✅ | Sim `churn --bots 6 --minutes 15` on the branch | it runs and finds no crash | no crash in 912 s (quits 1260, bot errors 0, crashed False) |
| ✅ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | 0 before, 0 after |

The new tests on the code **before** the change (the branch's tests applied to the base) and after it:

| Test | Before, Debug | Before, Release | After, Debug | After, Release |
|---|---|---|---|---|
| extract_char detaches the character from its descriptor both ways | fail | fail | pass | pass |

<sub>g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake version 4.2.3; Ubuntu 26.04.1 LTS. Base `82171fa443`, branch `c6aac511ea` (this PR's `7c99b35ac3` has the same code, with its history squashed).</sub>

## Not in this PR

- An issue: extracted characters are still processed for the rest of their pulse (above).
- Xania Sim: mark the two `Descriptor` use-after-free findings fixed once this is merged.

---

**More detail:** the [full write-up](https://abraidotti.github.io/xania-builder/dossiers/issue-2-quitting-on-a-tick-pulse-char/) has the root-cause analysis, every question the research asked and its answer, and the gate's logs. Researched and gated with [Xania Builder](https://github.com/abraidotti/xania-builder); players simulated with [Xania Sim](https://github.com/abraidotti/xania-sim).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
