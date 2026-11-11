# nanny reads argument[0] of an empty reply at five lobby prompts (debug builds abort) (#3)

[#3](https://github.com/abraidotti/xania/issues/3) · Xania 82171fa443 · 2026-11-11 14:10

<details><summary>The idea as given</summary>

## Summary

`MudImpl::nanny` (`src/MudImpl.cpp`) reads `argument[0]` at five lobby prompts without checking that the reply is
non-empty. Blank lines do reach `nanny` (`Descriptor::pop_incomm` passes them on, and `nanny` trims a line of spaces
to nothing), so an empty reply indexes an empty `std::string_view`.

- **Debug builds** (the default `BUILD_TYPE=Debug`) abort on the libstdc++ bounds assertion, taking the whole MUD
  down for everyone connected.
- **Release builds** don't abort but read past the end of the view, so the `switch` acts on whatever byte follows.

Present at `82171fa` (current `main` of this fork and of mattgodbolt/xania).

## How to reproduce

On a debug build, answer any of the five prompts below with an empty line (just press Enter). For example, connect,
type a new character name, and press Enter at "Did I hear that right - '<name>' (Y/N)?". Each ends in:

```
/usr/include/c++/15/string_view:260: ... operator[](size_type) const ...: Assertion '__pos < this->_M_len' failed.
Program received signal SIGABRT, Aborted.
```

with the first frame in our source at that prompt's line in the table below.

## Faulty lines

All in `src/MudImpl.cpp`, in `MudImpl::nanny`:

| Line | State | Prompt |
|---|---|---|
| 711 | `BreakConnect` | "Do you wish to connect anyway (Y/N)?" |
| 740 | `ConfirmNewName` | "Did I hear that right - '<name>' (Y/N)?" |
| 854 | `GetNewSex` | "Are you male, female or other (M/F/O)?" |
| 890 | `GetAlignment` | "Which alignment (G/N/E)?" |
| 915 | `DefaultChoice` | "Customize (Y/N)?" |

The `GetAnsi` case already guards it (`if (argument.empty())` at line 759), so the pattern is known.

## Suggested fix

Treat an empty reply like any other invalid answer and ask again, as `GetAnsi` does, e.g. for `ConfirmNewName`:

```cpp
case DescriptorState::ConfirmNewName:
    if (argument.empty()) {
        d->write(fmt::format("Did I hear that right - '{}' (Y/N)? ", ch->name));
        break;
    }
    switch (argument[0]) {
```

or switch on a value that can't be out of range: `switch (argument.empty() ? '\0' : argument[0])`, letting each
state's `default:` branch re-prompt.

## How this was found

xania-builder's check (a research tool, not yet published) for `string_view`s indexed like C strings
flagged these lines while researching #1 (the same family of bug). [xania-sim](https://github.com/abraidotti/xania-sim)'s
lobby trial (`python -m xania_sim lobby`) then confirmed all five on an isolated test MUD, answering each prompt
with an empty line. A check for it (`code.lobby-empty-reply`) is on its way to Xania Explorer's Bugs
page, where it will list any of the five lines still unfixed.

</details>

## Focus

- `MudImpl::nanny` (src/MudImpl.cpp:603, 444 lines): named in the idea
- `Descriptor::pop_incomm` (src/Descriptor.cpp:60, 21 lines): named in the idea

## 1. Explorer insights

- Bug check `code.lobby-empty-reply` (present, crash): An empty reply at a login prompt crashes debug builds. MudImpl.cpp:711, MudImpl.cpp:740, MudImpl.cpp:854, MudImpl.cpp:890, MudImpl.cpp:915

**To decide**

- [ ] The fix should turn the code check above to `fixed` (it matches the faulty pattern). Does it, and are there other occurrences to fix at the same time?

## 2. Architecture

- `MudImpl::nanny` is defined at src/MudImpl.cpp:603-1046 (444 lines): `void MudImpl::nanny(Descriptor *d, std::string_view argument)`
- Called from `MudImpl::game_loop` (src/MudImpl.cpp:180), `MudImpl::handle_doorman_packet` (src/MudImpl.cpp:483)
- `nanny` calls `ArgParser` (3 definitions), `act` (7 definitions), `all` (2 definitions), `announce`, `bug` (2 definitions), `by_name`, `channel`, `char_to_room`, `character` (3 definitions), `check_ban` (2 definitions), `check_enum_bit`, `check_playing` and 60 more
- `nanny` reaches persisted or shared state: inventory
- `Descriptor::pop_incomm` is defined at src/Descriptor.cpp:60-80 (21 lines): `std::optional<std::string> Descriptor::pop_incomm()`
- Called from `MudImpl::game_loop` (src/MudImpl.cpp:180)
- `pop_incomm` calls `pop_raw`, `sanitise_input`, `size` (2 definitions), `write_direct`
- `src/MudImpl.cpp`: 1114 lines, 44 functions
- `src/Descriptor.cpp`: 322 lines, 26 functions

**To decide**

- [ ] Is the change local to these functions, or does the fix belong in a shared helper their callers use too?
- [ ] Does every caller (including automatic ones) still get the behaviour it expects?

## 3. Design patterns

- In `nanny`: ArgParser x3 (modern), std::string_view x1 (modern), fmt::format x5 (modern), matches()/matches_start() x4 (modern), range-for over contents x1 (modern), act() x2 (either), '\0' terminator checks x1 (legacy)
- `nanny` mixes modern (ArgParser, std::string_view, fmt::format, matches()/matches_start(), range-for over contents) and legacy ('\0' terminator checks) idioms: the modern ones already in the function are the pattern to follow.
- Across src/: act() 779, std::string_view 625, ArgParser 402, matches()/matches_start() 291, range-for over contents 267, fmt::format 211, sprintf/strcpy/strcat 19, '\0' terminator checks 14, char buffers 10

**To decide**

- [ ] Which existing idiom does the change follow, and does it leave the function more consistent?
- [ ] Is there a helper already (in the same file or a header) that does what the change needs?

## 4. Technical debt

- `nanny` indexes string_views like C strings (reading past the end when the view is that long, and never seeing a terminator): `argument[0]` at src/MudImpl.cpp:711, `argument[0]` at src/MudImpl.cpp:740, `argument[0]` at src/MudImpl.cpp:762, `argument[0]` at src/MudImpl.cpp:854, `argument[0]` at src/MudImpl.cpp:890, `argument[0]` at src/MudImpl.cpp:915
- `nanny` is 444 lines long (src/ median 7).
- Legacy idioms in `nanny`: '\0' terminator checks
- TODO at src/MudImpl.cpp:28: remove this
- TODO at src/MudImpl.cpp:44: move these?
- TODO at src/MudImpl.cpp:57: Move into a Universe class
- TODO at src/MudImpl.cpp:96: do something rather than return here if there's a failure
- TODO at src/MudImpl.cpp:456: remove global
- TODO at src/MudImpl.cpp:668: crypt can return null if if fails (e.g. password is truncated).
- The same pattern elsewhere in src/ (10 places in 4 functions; each is the same kind of bug unless the view is known to be long enough): `do_who` `arg[0]` :1249; `do_get` `arg1[3]` :641, `&arg1[4]` :641, `arg1[3]` :648, `&arg1[4]` :651, `arg1[3]` :707; `do_permit` `player[0]` :95, `player[0]` :98; `skill_lookup` `name[0]` :39, `name[0]` :39

**To decide**

- [ ] Are the other places with the same pattern the same bug, and do they belong in this change?
- [ ] What debt does the change pay down while it's here, and what does it deliberately leave?
- [ ] Does the change add any (a special case, a duplicated check, a new legacy idiom)?

## 5. Gameplay

- Messages `nanny` can show: "Nanny: bad d->state() {}."; "Illegal name, try another.\n\rName: "; "Denying access to {}@{}."; "You are denied access.\n\r"; "The game is wizlocked.  Try again later - a reboot may be imminent.\n\r"; "Password: "; "The game is newlocked.  Try again later - a reboot may be imminent.\n\r"; "Your site has been banned.\n\r"; "Did I hear that right - '{}' (Y/N)? "; "Our survey said <Crude buzzer noise>.\n\rWrong password.\n\r" (+49)
- Messages `pop_incomm` can show: "Line too long.\n\r"
- Balance numbers Explorer models from these files: none (the change is behaviour, not balance; Explorer's predictions shouldn't move)

**To decide**

- [ ] What does a player notice before and after (messages, what they get, what's refused)?
- [ ] Can a careless or abusive player use the change (or the old behaviour) to their advantage?
- [ ] Does it change balance for any class, race or level range? If so, which Explorer numbers?

## 6. Documentation

- No help entries or docs mention the focus.

**To decide**

- [ ] Does any help entry describe the behaviour being changed, and does it need rewording?
- [ ] Does the change need a note anywhere else (README, release notes, an issue comment)?

## 7. Test coverage

- `src/apps/test/pfutest.cpp`: includes MudImpl.hpp
- `src/test/save_test.cpp`: includes MudImpl.hpp
- `src/test/DescriptorTest.cpp`: named after Descriptor.cpp, includes Descriptor.hpp
- No unit test calls `nanny`.
- No unit test calls `pop_incomm`.
- Sim finding `crash:SIGABRT:MudImpl.cpp:MudImpl::nanny` [known, seen 5x]: xania crashed (SIGABRT, failed assertion) in MudImpl::nanny (MudImpl.cpp) (https://github.com/abraidotti/xania/issues/3)

**To decide**

- [ ] Which unit test pins the fixed behaviour (a test that fails before the change)?
- [ ] Which Sim trial or scenario shows it from a player's side, and should a new one be added?

## 8. History

- `argument` is declared at src/MudImpl.cpp:603, a line last changed in `687f6ce` (2025-05-11, snellers): Step 2 of the next big refactoring project.
- `argument[0]` at src/MudImpl.cpp:711 was last changed in `03e4dc4` (2021-12-05, snellers): nanny() lobby func upgraded to use string_view....(#263)
- `argument[0]` at src/MudImpl.cpp:740 was last changed in `03e4dc4` (2021-12-05, snellers): nanny() lobby func upgraded to use string_view....(#263)
- `argument[0]` at src/MudImpl.cpp:762 was last changed in `03e4dc4` (2021-12-05, snellers): nanny() lobby func upgraded to use string_view....(#263)
- `argument[0]` at src/MudImpl.cpp:854 was last changed in `0fbb3f4` (2021-03-31, snellers): * New Sex wrapper class and enum:
- `argument[0]` at src/MudImpl.cpp:890 was last changed in `7a71102` (2020-07-22, Matt Godbolt): Reformat all the code with clang-format
- `argument[0]` at src/MudImpl.cpp:915 was last changed in `7a71102` (2020-07-22, Matt Godbolt): Reformat all the code with clang-format
- The conversion to string_view (or ArgParser): `03e4dc4` (2021-12-05, snellers): nanny() lobby func upgraded to use string_view....(#263). The indexing above has been on a view, with no terminator, since then
- `nanny` (444 lines) comes from 55 commits; the most: `33a9553` (2020-07-05, Matt Godbolt): Initial import of just code, areas, and html (178 lines); `03e4dc4` (2021-12-05, snellers): nanny() lobby func upgraded to use string_view....(#263) (44 lines); `e4a77fe` (2020-08-08, Matt Godbolt): Replace free function with call to d->write() throughout (28 lines); `f2c8558` (2022-04-03, snellers): Char creation lobby is colourized to improve usability (detect ansi early). (20 lines)
- `pop_incomm` (21 lines) comes from 2 commits; the most: `d5e56a6` (2020-08-07, Matt Godbolt): Descriptor refactor (#106) (20 lines); `f2ee4e1` (2020-08-08, Matt Godbolt): Remove outbuf and outsize (1 lines)
- Since 03e4dc4 (2021-12-05), 26 commits changed the compiler or its flags; the latest: `7bd8c82` (2026-10-31, snellers): github action upgrade to Ubuntu 26.04 and g++-15; `82823ff` (2026-10-31, snellers): General tooling upgrades, largely for Ubuntu 26.04.1 compatibility conda 26.9.4-0 conan 2.33.0 cmake >= 3.31 g++-15 default, g++-13 fallback Compiles on ubunt 26.04.1; `425fd97` (2025-04-07, snellers): Docker: ubuntu 24 is the default these days. Install clang 19. Stop trying to install awscli as it's not in the ubuntu apt sources now. The session doesn't start tmux by default. [skip ci]; `e5483b6` (2025-03-28, snellers): Update g++ versions in README. Retire the g++ 10/11 toolchains.; `55c9b1b` (2025-03-28, snellers): github: upgrade to ubuntu 24 and use g++-13
- Debug builds add `-fno-omit-frame-pointer -fsanitize=leak -fsanitize=address -fsanitize=undefined`
- Release builds add `-O2 -DNDEBUG -Wno-error=array-bounds`
- Upstream PR [#308](https://github.com/mattgodbolt/xania/pull/308) (open): nanny: an empty reply at a Y/N-style lobby prompt asks again instead of reading past the end (mentions `nanny`, `pop_incomm`)
- Upstream issue [#280](https://github.com/mattgodbolt/xania/issues/280) (closed): Duplicate characters during char creation (mentions `nanny`)
- Upstream issue [#279](https://github.com/mattgodbolt/xania/issues/279) (open): Breakup & refactor nanny() (mentions `nanny`)
- Upstream issue [#129](https://github.com/mattgodbolt/xania/issues/129) (closed): Splat in reconnect (mentions `nanny`)
- Upstream issue [#127](https://github.com/mattgodbolt/xania/issues/127) (closed): Heap use after free in xania (mentions `nanny`)

**To decide**

- [ ] When did the behaviour start, and why did nobody notice until now?
- [ ] Did a toolchain change (compiler, flags, sanitizers) make it show, or change how it shows?
- [ ] Has upstream seen or tried this before, and does the change fit what was decided then?

## Gate plan

What `prototype` runs on the fork before this can ship:

- Builds: Debug (ASan, UBSan, LSan, libstdc++ assertions), Release (-O2)
- Unit tests: `src/apps/test/pfutest.cpp`, `src/test/DescriptorTest.cpp`, `src/test/save_test.cpp`
- Sim: `smoke`: the game still boots and a player can log in
- Sim: `churn --minutes 5`: logins and quits reach it (lifetime bugs show here)
- Regression: Sim finding `crash:SIGABRT:MudImpl.cpp:MudImpl::nanny` should stop reproducing (https://github.com/abraidotti/xania/issues/3)
