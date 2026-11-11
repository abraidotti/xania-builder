# Analysis: cast '' and practice '' read past the end of an empty skill name (#7)

Written by whoever made the change (here, Claude Code working from the dossier), answering the dossier's questions.
The facts it cites are in [dossier.md](dossier.md); the proof is in [gate.md](gate.md).

## In one paragraph

`skill_lookup` compares the first letter of the name it's given with each skill's (`name[0]`) before checking the
prefix. `cast ''` (in any room) and `practice ''` (at a trainer) hand it an **empty** name: ArgParser strips the
quotes, and `do_cast` and `do_practice` only check that the line had arguments. Indexing an empty
`std::string_view` is undefined behaviour; since GCC 15 (the default here from 2026-10-31) debug builds abort on
it, so any player can take a debug MUD down by typing `cast ''`. The fix makes `skill_lookup` return -1 for an
empty name, so the player is told "You don't know any spells of that name." or "You can't practice that.", which
is also what release builds already said, by luck.

#7 was filed for `practice ''`; checking `skill_lookup`'s other callers for the fix found `cast ''`, the same bug
with no trainer needed. One fix covers both.

## Root cause

| When | Commit | What happened |
|---|---|---|
| 2020-08-22 | `67c11b0` | ArgParser is added. `shift()` strips quotes, so `''` is an empty argument: correct, and unchanged since. |
| 2021-11-14 | `42406b7` | `skill_lookup(const char *)` becomes `skill_lookup(std::string_view)`; `name[0]` stays. An empty C string's `name[0]` was its terminator; an empty view has none. |
| 2021-11-16 | `49a8032` | *"Upgrade do_cast() to use ArgParser."* `do_cast` passes `args.shift()`, so `cast ''` reaches `skill_lookup` as an empty view. Undefined behaviour from here on. |
| 2021-12-04 | `5855495` | *"... practice ... upgraded to ArgParser or string_view"*. The same for `do_practice` and `practice ''`. |
| 2026-10-31 | `82823ff`, `7bd8c82` | g++-15 becomes the default; its libstdc++ checks `operator[]` at `-O0` ([GCC bug 112808](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=112808)), so Debug builds abort here. |
| 2026-11-11 | | Builder's string_view detector listed `skill_lookup`'s `name[0]` while researching #1; a Xania Sim known-bug check confirmed `practice ''` (filed as #7), and another, written while checking callers for the fix, confirmed `cast ''`. |

These commits belong to the same modernisation that produced #1 (`35c8f3a`, Dec 3) and #3 (`03e4dc4`, Dec 5):
over about three weeks, command handlers moved from C strings to `string_view`, and the same assumption (that `s[0]`
of an empty string is a harmless `'\0'`) survived in four places.

### Why debug builds abort and release builds don't

As in #1 and #3: libstdc++'s assertions are on at `-O0` since GCC 15 and catch the out-of-range `operator[]`;
AddressSanitizer doesn't, because the byte read is still inside the input buffer. In release builds the read goes
ahead: for `cast ''` the empty view sits on the closing quote, so `name[0]` is `'`, no skill name starts with an
apostrophe, and the player gets the ordinary "unknown spell" answer by accident.

## The fix

```cpp
int skill_lookup(std::string_view name) {
    // No skill has an empty name, and name[0] below needs one character (an empty argument, from "cast ''" or
    // "practice ''", used to read past the end here). Don't drop the name[0] test instead: matches_start()
    // takes "" as a prefix of every skill.
    if (name.empty())
        return -1;
```

In `skill_lookup` rather than in each command: an empty name can't name a skill whoever passes it, so the check
belongs with the lookup. That is also why one change fixes both commands, and any caller added later.

### Alternatives considered

- **Check in `do_cast` and `do_practice`**: two fixes for two callers that are reachable today, and the trap left in
  `skill_lookup` for the next one. Rejected.
- **`first_char(name)`** (the helper #3 adds) in the comparison: `'\0'` would match no skill, so it would work, but
  it hides the real rule (an empty name is never a skill) inside a character comparison, and it depends on #3.
- **Drop the `name[0]` comparison** (it's only a fast path before `matches_start`): `matches_start("", x)` is true
  for every `x`, so an empty name would then match the first skill in the table. That's why the comment says not to.

## Answers to the dossier's questions

**1. Explorer.** No Explorer check covers it yet; a `code.` check for `skill_lookup` without an empty guard would be
the natural follow-up (Explorer is a separate tool).

**2. Architecture.** One function, `skill_lookup` in `lookup.cpp`, with about 60 call sites. Most pass string
literals. Of those that pass a variable, the ones reached by player input are: `do_cast` and `do_practice`
(unguarded: the bug); `do_gain` (`argument.empty()` checked first); `do_sset` (`skill_name.empty()` checked);
`do_slookup` (the raw line, quotes included); `parse_customizations` during character creation (`args.remaining()`,
quotes kept, and checked for empty); and `spell_undo_spell` (checks `spell_name.empty()`). The rest read player and
area files and spec functions' fixed spell names. With the check in `skill_lookup`, none of them depends on getting
this right any more.

**3. Design patterns.** An early `empty()` return, as `do_get`, `do_slookup` and most `string_view` code here do.

**4. Technical debt.** Clears the last unguarded C-string read in the list Builder's detector produced while
researching #1 (#1 and #3 are the others; `do_who` and `do_permit` were guarded). Leaves `skill_lookup`'s linear scan
alone.

**5. Gameplay.** A player who types `cast ''` is told "You don't know any spells of that name."; one who types
`practice ''` at a trainer is told "You can't practice that." and keeps their session. Before, either took a debug
MUD down for everyone, and `cast ''` needed nothing but a character. Release builds already gave those answers.
Nothing an abusive player gains; the crash itself was the abuse.

**6. Documentation.** None needed.

**7. Tests.** `lookup_test.cpp` gets a test case: an empty name, an empty view, and an empty view into a longer
string (how ArgParser makes one) all return -1, and a one-letter prefix still resolves. On the base it aborts the
Debug build, and it crashes the Release build too (a segfault): a default-constructed `std::string_view{}` has a
null data pointer, so there `name[0]` reads address 0. Player input never makes a null view (it always points into
the command line), which is why release servers survived `cast ''`; the test shows what the same code does when
the luck runs out. From the player's side, two Sim known-bug checks, `cast ''` in the starting room and `practice ''` at
the nearest trainer, crash the base and survive on the branch. Sim's skill trial (practise `bash`, then fight with
it) checks that practising and using a skill still work end to end.

**8. History.** Answered under Root cause. Upstream: upstream #194 (closed, "cast 'disp m' doesn't map to 'dispel
magic'") is the only issue mentioning `skill_lookup`, about prefix matching, not this.

## Follow-ups (not in this PR)

- Xania Sim: retire the `cast ''` and `practice ''` known-bug checks once this is merged.
- Xania Explorer: a code check for `skill_lookup` without an empty guard.
