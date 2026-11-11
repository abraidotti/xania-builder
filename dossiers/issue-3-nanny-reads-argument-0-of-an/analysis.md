# Analysis: nanny reads argument[0] of an empty reply (#3)

Written by whoever made the change (here, Claude Code working from the dossier), answering the dossier's questions.
The facts it cites are in [dossier.md](dossier.md); the proof is in [gate.md](gate.md).

## In one paragraph

Five of the lobby's prompts (the questions a connecting player answers before playing) look at the first letter of
the reply with `argument[0]`, without checking there is one. `argument` has been a `std::string_view` since December
2021, and indexing an empty view is undefined behaviour, so pressing Enter at "Did I hear that right (Y/N)?" (or
four other prompts) reads past the end. Since the project moved to GCC 15 on 2026-10-31, debug builds abort on the
standard library's bounds assertion there, taking the whole MUD down for everyone connected. Release builds get
away with it, by luck rather than design: the byte past the end happens to be a NUL terminator. The fix reads the first letter through a tiny `first_char()` that returns `'\0'` for an
empty reply, so each prompt falls into the `default:` branch it already has and simply asks again, as the ANSI
prompt already does for an empty reply.

## Root cause

| When | Commit | What happened |
|---|---|---|
| 2021-12-05 | `03e4dc4` | *"nanny() lobby func upgraded to use string_view"*. `argument` goes from `const char *` to `std::string_view`. With a C string, `argument[0]` on an empty reply was the terminator, `'\0'`. Two states tested for it explicitly (`if (argument[0] == '\0')` in `GetName` and `GetAnsi`), and the commit correctly turned those into `argument.empty()`. The other five relied on `'\0'` matching no `case` and falling into `default:`; there was no test to convert, so they kept `argument[0]`, which is now out of range on an empty view. |
| 2025-05-11 | `687f6ce` | nanny moves from `comm.cpp` into `MudImpl` (the dossier's history uses move-aware blame, so the faulty lines are still credited to `03e4dc4`). |
| 2026-10-31 | `82823ff`, `7bd8c82` | g++-15 becomes the default. Its libstdc++ turns `_GLIBCXX_ASSERTIONS` on for unoptimised builds ([GCC bug 112808](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=112808)), so Debug builds start aborting here. |
| 2026-11-10 | | Builder's string_view detector flags the lines while researching #1 (the same mistake, made two days earlier in `35c8f3a`); Xania Sim's `lobby` trial confirms all five. Filed as #3. |

### Why debug builds abort and release builds don't

The same reason as #1, checked the same way with g++ 15.2: at `-O0` libstdc++ checks `operator[]` and aborts; at
`-O2` (and at `-O0` with `-D_GLIBCXX_NO_ASSERTIONS`) the read goes ahead silently, and AddressSanitizer doesn't
report it, because the byte after the view is still inside the input buffer. So it is undefined behaviour in every
build, and the assertion is only what makes it visible.

What release builds actually read: every caller passes a view of something NUL-terminated (the `std::string`
`pop_incomm` returns, or the literal `""` on reconnect), and `ltrim` only moves the start of the view. So the byte
just past an empty view is always a `'\0'`, which matches no `case` and lands in `default:`, the right answer by
accident. (The issue said release builds "switch on whatever byte follows"; in practice that byte is always the
terminator. The optimiser is still entitled to assume the read never happens, which is why it's worth fixing
anyway.)

One contrast that explains why only these lines are affected: `Descriptor::pop_incomm` does `next_line[0]` on the
same empty line, but `next_line` is a `std::string`, and `s[s.size()]` on a `std::string` is defined (it's the
terminator). Only `std::string_view` has no terminator to read.

### A second way in, checked and found unreachable

Not every empty reply comes from a player. On a doorman **reconnect** (`PACKET_RECONNECT`, when doorman hands
xania back an already-authenticated connection, e.g. after xania restarts), `handle_doorman_packet` calls
`nanny(d, "")` itself, twice (MudImpl.cpp:506 and 509). If the first call found the character already playing on
another connection, `check_playing` would move the descriptor to `BreakConnect` and the second call would index the
empty literal there.

That needs doorman to hold **two authenticated channels for the same character**, and normal play can't produce
that. Doorman marks a channel authenticated only on `PACKET_AUTHORIZED`, which xania sends in one place: a fresh
login finishing the MOTD (MudImpl.cpp:978). A second login as the same character always meets `check_playing`
first; answering Y closes the old channel and gets in through `check_reconnect`, which doesn't send
`PACKET_AUTHORIZED`. So the path is effectively unreachable (short of two new characters with one name being created
at the same moment, the race upstream #280 fixed). The fix covers it anyway: `BreakConnect` would get `'\0'` and
answer "Please type Y or N?".

The same reading confirms a separate, already-known gap: a player who gets back in through "connect anyway" or a
link-dead reconnect is never re-authorized with doorman, so a xania restart can't reconnect them. That's upstream
#178 (open), not this change.

## The fix

```cpp
// The first character of str, or '\0' if str is empty. For code that switches on the first letter of a reply,
// where str[0] on an empty string_view would read past its end.
[[nodiscard]] constexpr char first_char(std::string_view str) noexcept { return str.empty() ? '\0' : str.front(); }
```

in `string_utils.hpp`, next to `is_vowel` and `has_prefix`, and in the five prompts:

```cpp
switch (first_char(argument)) {                       // BreakConnect, ConfirmNewName, GetAlignment, DefaultChoice
if (auto sex = Sex::try_from_char(first_char(argument))) {   // GetNewSex
```

`'\0'` matches no `case`, so each prompt does what it already does for a reply it doesn't understand:

| Prompt | What an empty reply now gets |
|---|---|
| BreakConnect | "Please type Y or N?" |
| ConfirmNewName | "It's quite simple - type Yes or No:" |
| GetNewSex | "Please specify (M)ale, (F)emale or (O)ther." |
| GetAlignment | "That's not a valid alignment." and the question again |
| DefaultChoice | "Please answer (Y/N)?" |

That's what the C version did before `03e4dc4`, so the behaviour is restored, not invented.

### Alternatives considered

- **An `if (argument.empty())` block in each of the five states**, as `GetAnsi` has: five copies of a re-prompt
  that each `default:` already writes, and five more places for them to drift apart. Rejected.
- **`switch (argument.empty() ? '\0' : argument[0])` inline**: the same idea without a name, repeated five times.
  A named helper says why and can be tested.
- **Reject empty lines before `nanny`** (in `pop_incomm` or the game loop): would also change states where an empty
  line means something (`GetAnsi` treats it as "no"; the MOTD's "press return"), and wouldn't cover the reconnect
  path, which calls `nanny` directly. Rejected.
- **Refactor nanny** (444 lines; upstream #279 proposes a `Lobby` class): the right long-term home for this, but
  not in a bug fix. `first_char` will move with the code.

## Answers to the dossier's questions

**1. Explorer.** Xania Explorer's Bugs page has a check for this (`code.lobby-empty-reply`), added when the issue
was filed; it lists any of the five prompts still indexing `argument[0]`, and will show them as fixed once this is
merged.

**2. Architecture.** Local to `MudImpl::nanny`, plus a header-only helper. Every caller of `nanny` benefits: the
game loop (player input) and both doorman reconnect calls.

**3. Design patterns.** `string_utils.hpp` is where small `string_view` helpers live (`is_vowel`, `has_prefix`,
`matches`); `first_char` is `constexpr` and `noexcept` like the trivial ones. Each prompt's existing `default:` is
reused instead of a new branch.

**4. Technical debt.** Pays down the five unguarded reads. Leaves `GetAnsi`'s `argument[0]` (line 762) as it is:
it's guarded by the `empty()` check above it, and changing it would only be churn. (Builder's detector still lists
it; it doesn't yet understand guards.) The same pattern elsewhere: `do_get` is #1; `do_who` and `do_permit` are
guarded (false positives); `skill_lookup` (`practice ''`) is a real bug of the same family, confirmed with Sim and
filed as #7.

**5. Gameplay.** A player who presses Enter at one of the five prompts is asked again instead of crashing a debug
MUD. Release builds already asked again (by accident, see above), so on the live game nothing visible changes.
Nothing new for an abusive player:
before the fix, pressing Enter at a prompt could take a debug MUD down for everyone, which was the real exploit.
No balance numbers involved.

**6. Documentation.** None needed: the prompts' messages already exist and are what players see.

**7. Tests.** `first_char` gets a unit test (including an empty view into a longer string, the case that bites, and a
`static_assert`). `nanny` is private to `MudImpl` and needs a whole MUD, so the end-to-end proof is Xania Sim's
`lobby` trial: a careless player pressing Enter at each of the five prompts. The gate runs it on the base (it
should crash at every prompt) and on the branch (every prompt must be reached and survive), and the before/after
proof comes from that.

**8. History.** Answered under Root cause. Upstream: no issue about empty replies; upstream #279 (open) wants nanny broken up;
upstream #129 (closed, "Splat in reconnect") is about the same reconnect code; upstream #178 (open) is the gap the
reconnect reading confirmed (see above).

## Follow-ups (not in this PR)

- Builder: teach the detector about `empty()` guards (it flags line 762 and two other guarded places).
