Five of the lobby's prompts (the questions a connecting player answers before playing) look at the first letter of the reply with `argument[0]`, without checking there is one. `argument` has been a `std::string_view` since December 2021, and indexing an empty view is undefined behaviour, so pressing Enter at "Did I hear that right (Y/N)?" (or four other prompts) reads past the end. Since the project moved to GCC 15 on 2026-10-31, debug builds abort on the standard library's bounds assertion there, taking the whole MUD down for everyone connected. Release builds get away with it, by luck rather than design: the byte past the end happens to be a NUL terminator. The fix reads the first letter through a tiny `first_char()` that returns `'\0'` for an empty reply, so each prompt falls into the `default:` branch it already has and simply asks again, as the ANSI prompt already does for an empty reply.

Reported as abraidotti/xania#3 (with the reproduction).

## What was wrong

| When | Commit | What happened |
|---|---|---|
| 2021-12-05 | `03e4dc4` | *"nanny() lobby func upgraded to use string_view"*. `argument` goes from `const char *` to `std::string_view`. With a C string, `argument[0]` on an empty reply was the terminator, `'\0'`. Two states tested for it explicitly (`if (argument[0] == '\0')` in `GetName` and `GetAnsi`), and the commit correctly turned those into `argument.empty()`. The other five relied on `'\0'` matching no `case` and falling into `default:`; there was no test to convert, so they kept `argument[0]`, which is now out of range on an empty view. |
| 2025-05-11 | `687f6ce` | nanny moves from `comm.cpp` into `MudImpl` (the dossier's history uses move-aware blame, so the faulty lines are still credited to `03e4dc4`). |
| 2026-10-31 | `82823ff`, `7bd8c82` | g++-15 becomes the default. Its libstdc++ turns `_GLIBCXX_ASSERTIONS` on for unoptimised builds ([GCC bug 112808](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=112808)), so Debug builds start aborting here. |
| 2026-11-10 | | Builder's string_view detector flags the lines while researching abraidotti/xania#1 (the same mistake, made two days earlier in `35c8f3a`); Xania Sim's `lobby` trial confirms all five. Filed as abraidotti/xania#3. |

<details><summary>Why debug builds abort and release builds don't</summary>

The same reason as abraidotti/xania#1, checked the same way with g++ 15.2: at `-O0` libstdc++ checks `operator[]` and aborts; at `-O2` (and at `-O0` with `-D_GLIBCXX_NO_ASSERTIONS`) the read goes ahead silently, and AddressSanitizer doesn't report it, because the byte after the view is still inside the input buffer. So it is undefined behaviour in every build, and the assertion is only what makes it visible.

What release builds actually read: every caller passes a view of something NUL-terminated (the `std::string` `pop_incomm` returns, or the literal `""` on reconnect), and `ltrim` only moves the start of the view. So the byte just past an empty view is always a `'\0'`, which matches no `case` and lands in `default:`, the right answer by accident. (The issue said release builds "switch on whatever byte follows"; in practice that byte is always the terminator. The optimiser is still entitled to assume the read never happens, which is why it's worth fixing anyway.)

One contrast that explains why only these lines are affected: `Descriptor::pop_incomm` does `next_line[0]` on the same empty line, but `next_line` is a `std::string`, and `s[s.size()]` on a `std::string` is defined (it's the terminator). Only `std::string_view` has no terminator to read.

</details>

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

<details><summary>Alternatives considered</summary>

- **An `if (argument.empty())` block in each of the five states**, as `GetAnsi` has: five copies of a re-prompt that each `default:` already writes, and five more places for them to drift apart. Rejected.
- **`switch (argument.empty() ? '\0' : argument[0])` inline**: the same idea without a name, repeated five times. A named helper says why and can be tested.
- **Reject empty lines before `nanny`** (in `pop_incomm` or the game loop): would also change states where an empty line means something (`GetAnsi` treats it as "no"; the MOTD's "press return"), and wouldn't cover the reconnect path, which calls `nanny` directly. Rejected.
- **Refactor nanny** (444 lines; #279 proposes a `Lobby` class): the right long-term home for this, but not in a bug fix. `first_char` will move with the code.

</details>

## What players will notice

A player who presses Enter at one of the five prompts is asked again instead of crashing a debug MUD. Release builds already asked again (by accident, see above), so on the live game nothing visible changes. Nothing new for an abusive player: before the fix, pressing Enter at a prompt could take a debug MUD down for everyone, which was the real exploit. No balance numbers involved.

## Verification

Run by Xania Builder's gate, in the same configurations CI uses (Debug, which here means ASan + UBSan + libstdc++ assertions, and Release -O2):

| | Check | Expected | Result |
|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean |
| ✅ | Debug build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) |
| ✅ | Unit tests, Debug, the branch | every test passes | 1075 test cases and sections, all passed |
| ✅ | Release build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) |
| ✅ | Unit tests, Release, the branch | every test passes | 1075 test cases and sections, all passed |
| ➖ | Debug build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof |
| ➖ | Release build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof |
| ✅ | Debug build of the base as it is (for Sim's trials on it) | it compiles and installs | built in 7 s |
| ➖ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | the new tests pass on the branch; they can't build on the base (they test code the change adds), so the base side is Sim's |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 20 s |
| ✅ | Sim `lobby` on the base | it reproduces `nanny` (the bug is there) | reproduced: xania crashed (SIGABRT, failed assertion) in MudImpl::nanny (MudImpl.cpp) (ConfirmNewName crashed, GetNewSex crashed, GetAlignment crashed, DefaultChoice crashed, BreakConnect crashed) |
| ✅ | Sim `lobby` on the branch | it runs and finds no crash | no crash in 50 s (ConfirmNewName still up, GetNewSex still up, GetAlignment still up, DefaultChoice still up, BreakConnect still up) |
| ✅ | Proof the bug was there before the change | a new test fails on the base, or a Sim trial shows the bug on the base | Sim showed it on the base: Sim `lobby` on the base |
| ✅ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | 6 before, 1 after |

The new tests on the code **before** the change (the branch's tests applied to the base) and after it:

| Test | Before, Debug | Before, Release | After, Debug | After, Release |
|---|---|---|---|---|
| first_char | not run | not run | pass | pass |

<sub>g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake version 4.2.3; Ubuntu 26.04.1 LTS. Base `82171fa443`, branch `f7a0c3b52d` (this PR's `b6291472fe` has the same code, with its history squashed).</sub>

The same change went through the fork first, where this repo's own CI (format, Debug and Release build and test) passed: https://github.com/abraidotti/xania/pull/5.

## Not in this PR

- Xania Sim: a reconnect trial (restart xania under a live doorman with a character logged in twice) to confirm the second path.
- Builder: teach the detector about `empty()` guards (it flags line 762 and two other guarded places).

---

**More detail:** the [full write-up](https://abraidotti.github.io/xania-builder/dossiers/issue-3-nanny-reads-argument-0-of-an/) has the root-cause analysis, every question the research asked and its answer, and the gate's logs. Researched and gated with [Xania Builder](https://github.com/abraidotti/xania-builder); players simulated with [Xania Sim](https://github.com/abraidotti/xania-sim).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
