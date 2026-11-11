# Gate: issue-3-nanny-reads-argument-0-of-an

Branch `fix/3-lobby-empty-reply` at `f7a0c3b52d` against base `82171fa443`: **passed** in 3 min, 2026-11-11 11:22.

Environment: gcc g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake cmake version 4.2.3; os Ubuntu 26.04.1 LTS; distro Ubuntu-26.04

Changes: 3 files changed, 23 insertions(+), 5 deletions(-)

- `f7a0c3b nanny: an empty reply at a Y/N-style lobby prompt asks again instead of reading past the end (#3)`

| | Step | Expected | Result | Time |
|---|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean | 2 s |
| ✅ | Debug build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) | 0 s |
| ✅ | Unit tests, Debug, the branch | every test passes | 1075 test cases and sections, all passed | 4 s |
| ✅ | Release build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) | 0 s |
| ✅ | Unit tests, Release, the branch | every test passes | 1075 test cases and sections, all passed | 0 s |
| ➖ | Debug build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof | 2 s |
| ➖ | Release build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof | 2 s |
| ✅ | Debug build of the base as it is (for Sim's trials on it) | it compiles and installs | built in 7 s | 7 s |
| ➖ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | the new tests pass on the branch; they can't build on the base (they test code the change adds), so the base side is Sim's | 0 s |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 20 s | 21 s |
| ✅ | Sim `lobby` on the base | it reproduces `nanny` (the bug is there) | reproduced: xania crashed (SIGABRT, failed assertion) in MudImpl::nanny (MudImpl.cpp) (ConfirmNewName crashed, GetNewSex crashed, GetAlignment crashed, DefaultChoice crashed, BreakConnect crashed) | 112 s |
| ✅ | Sim `lobby` on the branch | it runs and finds no crash | no crash in 50 s (ConfirmNewName still up, GetNewSex still up, GetAlignment still up, DefaultChoice still up, BreakConnect still up) | 50 s |
| ✅ | Proof the bug was there before the change | a new test fails on the base, or a Sim trial shows the bug on the base | Sim showed it on the base: Sim `lobby` on the base | 0 s |
| ✅ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | 6 before, 1 after | 0 s |

## The new tests, before and after

| Test | Base, Debug | Base, Release | Branch, Debug | Branch, Release | |
|---|---|---|---|---|---|
| first_char | not run | not run | pass | pass | can't build before the change |

## Detectors, base against branch

| Function | Base | Branch |
|---|---|---|
| `MudImpl::nanny` | `argument[0]` at src/MudImpl.cpp:711, `argument[0]` at src/MudImpl.cpp:740, `argument[0]` at src/MudImpl.cpp:762, `argument[0]` at src/MudImpl.cpp:854, `argument[0]` at src/MudImpl.cpp:890, `argument[0]` at src/MudImpl.cpp:915 | `argument[0]` at src/MudImpl.cpp:762 |
| `Descriptor::pop_incomm` | none | none |

## Logs

<details><summary>✅ Sim `smoke` on the branch</summary>

```
smoke: Smoke: create a bot, look, quit (20 s, Xania f7a0c3b52d)
  transcript: runs\20261111-112305\Smokea.log
  result: clean
```

</details>

<details><summary>✅ Sim `lobby` on the base</summary>

```
[00:37] lobby GetNewSex: xania died (prompt=Are you male, female or other (M/F/O)? reply=)
[00:50] lobby GetAlignment: walking to the prompt
[00:56] lobby GetAlignment: xania died (prompt=Which alignment (G/N/E)? reply=)
[01:09] lobby DefaultChoice: walking to the prompt
[01:15] lobby DefaultChoice: xania died (prompt=Customize (Y/N)? reply=)
[01:28] lobby BreakConnect: walking to the prompt
[01:37] lobby BreakConnect: xania died (prompt=Do you wish to connect anyway (Y/N)? reply=)
lobby: Lobby: an empty reply at each login prompt (112 s, Xania 82171fa443)
  ConfirmNewName crashed, GetNewSex crashed, GetAlignment crashed, DefaultChoice crashed, BreakConnect crashed
  failed: lobby: ConfirmNewName: XANIA DIED after an empty reply to "Did I hear that right - 'Lobbya' (Y/N)?"
  failed: lobby: GetNewSex: XANIA DIED after an empty reply to 'Are you male, female or other (M/F/O)?'
  failed: lobby: GetAlignment: XANIA DIED after an empty reply to 'Which alignment (G/N/E)?'
  failed: lobby: DefaultChoice: XANIA DIED after an empty reply to 'Customize (Y/N)?'
  failed: lobby: BreakConnect: XANIA DIED after an empty reply to 'Do you wish to connect anyway (Y/N)?'
  [known] high xania crashed (SIGABRT, failed assertion) in MudImpl::nanny (MudImpl.cpp)
  [known] high xania crashed (SIGABRT, failed assertion) in MudImpl::nanny (MudImpl.cpp)
  [known] high xania crashed (SIGABRT, failed assertion) in MudImpl::nanny (MudImpl.cpp)
  [known] high xania crashed (SIGABRT, failed assertion) in MudImpl::nanny (MudImpl.cpp)
  [known] high xania crashed (SIGABRT, failed assertion) in MudImpl::nanny (MudImpl.cpp)
  crash_ConfirmNewName: runs\lobby-20261111-112312\xania-crash-ConfirmNewName.txt
  crash_GetNewSex: runs\lobby-20261111-112312\xania-crash-GetNewSex.txt
  crash_GetAlignment: runs\lobby-20261111-112312\xania-crash-GetAlignment.txt
  crash_DefaultChoice: runs\lobby-20261111-112312\xania-crash-DefaultChoice.txt
  crash_BreakConnect: runs\lobby-20261111-112312\xania-crash-BreakConnect.txt
  result: clean
```

</details>

<details><summary>✅ Sim `lobby` on the branch</summary>

```
[00:14] lobby ConfirmNewName: walking to the prompt
[00:19] lobby ConfirmNewName: survived (prompt=Did I hear that right - 'Lobbya' (Y/N)? reply=It's quite simple - type Yes or No:)
[00:19] lobby GetNewSex: walking to the prompt
[00:25] lobby GetNewSex: survived (prompt=Are you male, female or other (M/F/O)? reply=Please specify (M)ale, (F)emale or (O)ther.)
[00:25] lobby GetAlignment: walking to the prompt
[00:31] lobby GetAlignment: survived (prompt=Which alignment (G/N/E)? reply=That's not a valid alignment.
Which alignment (G/N/E)?)
[00:31] lobby DefaultChoice: walking to the prompt
[00:38] lobby DefaultChoice: survived (prompt=Customize (Y/N)? reply=Please answer (Y/N)?)
[00:38] lobby BreakConnect: walking to the prompt
[00:47] lobby BreakConnect: survived (prompt=Do you wish to connect anyway (Y/N)? reply=Please type Y or N?)
lobby: Lobby: an empty reply at each login prompt (50 s, Xania f7a0c3b52d)
  ConfirmNewName still up, GetNewSex still up, GetAlignment still up, DefaultChoice still up, BreakConnect still up
  result: clean
```

</details>
