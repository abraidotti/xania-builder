# Gate: issue-2-quitting-on-a-tick-pulse-char

Branch `fix/2-extract-char-desc` at `c6aac511ea` against base `82171fa443`: **passed** in 18 min, 2026-11-11 11:03.

Environment: gcc g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake cmake version 4.2.3; os Ubuntu 26.04.1 LTS; distro Ubuntu-26.04

Changes: 2 files changed, 76 insertions(+), 1 deletion(-)

- `c6aac51 ExtractCharTest: build the Area with Area::parse (its constructor is private)`
- `9947e43 extract_char: clear ch->desc as well as the descriptor's character (#2)`

| | Step | Expected | Result | Time |
|---|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean | 2 s |
| ✅ | Debug build of the branch | it compiles (-Werror) | built in 23 s | 23 s |
| ✅ | Unit tests, Debug, the branch | every test passes | 1074 test cases and sections, all passed | 3 s |
| ✅ | Release build of the branch | it compiles (-Werror) | built in 21 s | 21 s |
| ✅ | Unit tests, Release, the branch | every test passes | 1074 test cases and sections, all passed | 0 s |
| ✅ | Debug build of the base with the branch's tests | it compiles (-Werror) | built in 20 s | 20 s |
| ➖ | Unit tests, Debug, the base with the branch's tests | the new tests fail here (they pin the bug) | 1 of 1074 failed: extract_char detaches the character from its descriptor both ways/leaving the world (quit, purge) | 2 s |
| ✅ | Release build of the base with the branch's tests | it compiles (-Werror) | built in 21 s | 21 s |
| ➖ | Unit tests, Release, the base with the branch's tests | the new tests fail here (they pin the bug) | 1 of 1074 failed: extract_char detaches the character from its descriptor both ways/leaving the world (quit, purge) | 0 s |
| ✅ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | 1 of 1 new tests pin the fix | 0 s |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 21 s | 22 s |
| ✅ | Sim `churn --bots 6 --minutes 15` on the base | it reproduces `heap-use-after-free` (the bug is there) | reproduced: xania crashed (AddressSanitizer: heap-use-after-free) in Descriptor::is_switched (Descriptor.hpp) | 68 s |
| ✅ | Sim `churn --bots 6 --minutes 15` on the branch | it runs and finds no crash | no crash in 912 s (quits 1260, bot errors 0, crashed False) | 913 s |
| ✅ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | 0 before, 0 after | 0 s |

## The new tests, before and after

| Test | Base, Debug | Base, Release | Branch, Debug | Branch, Release | |
|---|---|---|---|---|---|
| extract_char detaches the character from its descriptor both ways | fail | fail | pass | pass | pins the fix |

## Detectors, base against branch

| Function | Base | Branch |
|---|---|---|
| `do_quit` | none | none |
| `extract_char` | none | none |
| `MudImpl::game_loop` | none | none |
| `update_handler` | none | none |
| `char_update` | none | none |
| `Char::is_immortal` | none | none |
| `collect_all_garbage` | none | none |
| `Char::get_trust` | none | none |
| `is_switched` | none | none |

## Logs

<details><summary>✅ Sim `smoke` on the branch</summary>

```
smoke: Smoke: create a bot, look, quit (21 s, Xania c6aac511ea)
  transcript: runs\20261111-110532\Smokea.log
  result: clean
```

</details>

<details><summary>✅ Sim `churn --bots 6 --minutes 15` on the base</summary>

```
churn: Churn: 6 bots creating and quitting (68 s, Xania 82171fa443)
  quits 42, bot errors 0, crashed True
  [known] high xania crashed (AddressSanitizer: heap-use-after-free) in Descriptor::is_switched (Descriptor.hpp)
  crash_report: runs\churn-20261111-110538\xania-crash.txt
  result: clean
```

</details>

<details><summary>✅ Sim `churn --bots 6 --minutes 15` on the branch</summary>

```
churn: Churn: 6 bots creating and quitting (912 s, Xania c6aac511ea)
  quits 1260, bot errors 0, crashed False
  result: clean
```

</details>
