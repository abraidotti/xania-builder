# Gate: compare-counts-only-weapon-dice-and

Branch `feature/144-compare-stats` at `937fd66f2b` against base `eec205e5fd`: **passed** in 2 min, 2026-11-20 23:14.

Environment: gcc g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake cmake version 4.2.3; os Ubuntu 26.04.1 LTS; distro Ubuntu-26.04

Changes: 5 files changed, 346 insertions(+), 39 deletions(-)

- `937fd66 compare: British spelling, armour (and armour_score), as the rest of Xania's prose`
- `2702f04 compare: count damroll and AC affects, and say how the other stats differ`

| | Step | Expected | Result | Time |
|---|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean | 2 s |
| ✅ | Debug build of the branch | it compiles (-Werror) | built in 14 s | 14 s |
| ✅ | Unit tests, Debug, the branch | every test passes | 1107 test cases and sections, all passed | 3 s |
| ✅ | Release build of the branch | it compiles (-Werror) | built in 11 s | 11 s |
| ✅ | Unit tests, Release, the branch | every test passes | 1107 test cases and sections, all passed | 0 s |
| ➖ | Debug build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof | 2 s |
| ➖ | Release build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof | 0 s |
| ✅ | Debug build of the base as it is (for Sim's trials on it) | it compiles and installs | built in 2 s | 2 s |
| ➖ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | the new tests pass on the branch; they can't build on the base (they test code the change adds), so the base side is Sim's | 0 s |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 21 s | 22 s |
| ✅ | Sim `pytest scenarios/test_live_compare.py` on the base | compare says the pin looks worse than the dagger, and can't compare the two rings | pytest exit 1: 1 failed in 32.43s | 33 s |
| ✅ | Sim `pytest scenarios/test_live_compare.py` on the branch | the pin looks better (its damroll counts), with the strength and hp lines; the rings get their four stat lines | pytest exit 0: 1 passed in 32.24s | 33 s |
| ✅ | Proof the bug was there before the change | a new test fails on the base, or a Sim trial shows the bug on the base | Sim showed it on the base: Sim `pytest scenarios/test_live_compare.py` on the base | 0 s |
| ➖ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | doesn't apply: the focus has no string_view indexing, before or after | 0 s |

## The new tests, before and after

| Test | Base, Debug | Base, Release | Branch, Debug | Branch, Release | |
|---|---|---|---|---|---|
| compare weapons | not run | not run | pass | pass | can't build before the change |
| compare armour | not run | not run | pass | pass | can't build before the change |
| compare things worn in the same place | not run | not run | pass | pass | can't build before the change |
| a weapon and something else can't be compared | not run | not run | pass | pass | can't build before the change |

## Detectors, base against branch

| Function | Base | Branch |
|---|---|---|
| `do_compare` | none | none |
| `find_comparable` | none | none |

## Logs

<details><summary>✅ Sim `smoke` on the branch</summary>

```
smoke: Smoke: create a bot, look, quit (21 s, Xania 937fd66f2b)
  transcript: runs\20261120-231512\Smokea.log
  result: clean
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_compare.py` on the base</summary>

```
E         
E         
E         Directrix gives you a pink ice ring.
E         
E         
E         
E         Directrix has created something!
E         
E         
E         
E         Concordius peers at you intently.
E         
E         
E         
E         Directrix gives you a very sharp pin.
E         
E         
E         A very sharp pin looks worse than a long elven dagger.
E         
E         
E       assert 'A very sharp pin looks better than a long elven dagger.' in 'school)\n\n[Exits: north south up]\nDirectrix the Apprentice of Magic is here.\nA tamed eagle perches on a wall.\n(Wh...intently.\n\n\n\nDirectrix gives you a very sharp pin.\n\n\nA very sharp pin looks worse than a long elven dagger.\n\n'
scenarios\test_live_compare.py:42: AssertionError
=========================== short test summary info ===========================
FAILED scenarios/test_live_compare.py::test_compare_counts_bonuses_and_names_the_stats_that_differ
1 failed in 32.43s
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_compare.py` on the branch</summary>

```
.                                                                        [100%]
1 passed in 32.24s
```

</details>
