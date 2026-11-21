# Gate: issue-9-vampiric-weapons-drain-nothing-from-hits

Branch `fix/9-vampiric-drain` at `7901035a37` against base `eec205e5fd`: **passed** in 30 min, 2026-11-20 21:41.

Environment: gcc g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake cmake version 4.2.3; os Ubuntu 26.04.1 LTS; distro Ubuntu-26.04

Changes: 4 files changed, 181 insertions(+), 7 deletions(-)

- `7901035 Vampiric weapons drain 5% of each weapon hit, with a message`

| | Step | Expected | Result | Time |
|---|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean | 3 s |
| ✅ | Debug build of the branch | it compiles (-Werror) | built in 141 s | 141 s |
| ✅ | Unit tests, Debug, the branch | every test passes | 1101 test cases and sections, all passed | 4 s |
| ✅ | Release build of the branch | it compiles (-Werror) | built in 145 s | 145 s |
| ✅ | Unit tests, Release, the branch | every test passes | 1101 test cases and sections, all passed | 0 s |
| ➖ | Debug build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof | 3 s |
| ➖ | Release build of the base with the branch's tests | it compiles (-Werror) | the new tests use code the change adds, so they can't compile without it; Sim's trials on the base are the before/after proof | 2 s |
| ✅ | Debug build of the base as it is (for Sim's trials on it) | it compiles and installs | built in 2 s | 2 s |
| ➖ | The new tests, before and after the change | each new test fails or aborts on the base in at least one build, and passes on the branch | the new tests pass on the branch; they can't build on the base (they test code the change adds), so the base side is Sim's | 0 s |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 22 s | 23 s |
| ✅ | Sim `weapon --rounds 40 --expect code today` on the base | the old (damage / 100) * 10 explains the rounds best for every weapon: nothing below 100 damage | no crash in 476 s | 477 s |
| ✅ | Sim `weapon --rounds 40 --expect #9` on the branch | 5% of each hit, rounded, explains the rounds best for every weapon, with a drain message on each draining hit | no crash in 477 s | 478 s |
| ✅ | Sim `skill bash --classes knight --fights 2` on the branch | it runs and finds no crash | no crash in 185 s (skill bash, kind combat skill, learned by knight 5) | 186 s |
| ✅ | Sim `hunt --minutes 5` on the branch | it runs and finds no crash | no crash in 306 s (fights 12, bot errors 0, crashed False) | 307 s |
| ✅ | Proof the bug was there before the change | a new test fails on the base, or a Sim trial shows the bug on the base | Sim showed it on the base: Sim `weapon --rounds 40 --expect code today` on the base | 0 s |
| ➖ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | doesn't apply: the focus has no string_view indexing, before or after | 0 s |

## The new tests, before and after

| Test | Base, Debug | Base, Release | Branch, Debug | Branch, Release | |
|---|---|---|---|---|---|
| vampiric drain amount | not run | not run | pass | pass | can't build before the change |
| vampiric drain | not run | not run | pass | pass | can't build before the change |

## Detectors, base against branch

| Function | Base | Branch |
|---|---|---|
| `damage` | none | none |
| `one_hit` | none | none |
| `char_update` | none | none |
| `spell_vampire` | none | none |
| `update_pos` | none | none |
| `check_damage_tolerance` | none | none |

## Logs

<details><summary>✅ Sim `smoke` on the branch</summary>

```
smoke: Smoke: create a bot, look, quit (22 s, Xania 7901035a37)
  transcript: runs\20261120-214635\Smokea.log
  result: clean
```

</details>

<details><summary>✅ Sim `weapon --rounds 40 --expect code today` on the base</summary>

```
[00:22] weapon 4100@20: setting up
[02:57] weapon 4100@20: done (weapon=a black demon blade (#4100) level=20 rounds=40 hits=73 mean_hit=13.9 max_hit=24 hits_100_plus=0 drained_seen=0 rounds_unexplained=4 drink_messages=0 error=)
[02:57] weapon 10066@65: setting up
[05:24] weapon 10066@65: done (weapon=Executioner's Axe (#10066) level=65 rounds=40 hits=68 mean_hit=62.8 max_hit=100 hits_100_plus=1 drained_seen=10 rounds_unexplained=4 drink_messages=0 error=)
[05:24] weapon 28021@91: setting up
[07:51] weapon 28021@91: done (weapon=Sword of Ashen-Shugar (#28021) level=91 rounds=40 hits=64 mean_hit=82.2 max_hit=175 hits_100_plus=11 drained_seen=100 rounds_unexplained=4 drink_messages=0 error=)
weapon: Weapon: a weapon flag in a real fight, hit by hit (476 s, Xania eec205e5fd)
  result: clean
```

</details>

<details><summary>✅ Sim `weapon --rounds 40 --expect #9` on the branch</summary>

```
[00:22] weapon 4100@20: setting up
[02:54] weapon 4100@20: done (weapon=a black demon blade (#4100) level=20 rounds=40 hits=70 mean_hit=13.1 max_hit=25 hits_100_plus=0 drained_seen=56 rounds_unexplained=4 drink_messages=63 error=)
[02:54] weapon 10066@65: setting up
[05:24] weapon 10066@65: done (weapon=Executioner's Axe (#10066) level=65 rounds=40 hits=60 mean_hit=64.8 max_hit=107 hits_100_plus=2 drained_seen=172 rounds_unexplained=4 drink_messages=60 error=)
[05:24] weapon 28021@91: setting up
[07:54] weapon 28021@91: done (weapon=Sword of Ashen-Shugar (#28021) level=91 rounds=40 hits=65 mean_hit=79.5 max_hit=125 hits_100_plus=10 drained_seen=232 rounds_unexplained=4 drink_messages=65 error=)
weapon: Weapon: a weapon flag in a real fight, hit by hit (477 s, Xania 7901035a37)
  result: clean
```

</details>

<details><summary>✅ Sim `skill bash --classes knight --fights 2` on the branch</summary>

```
[00:00] skill trial: planned (skill=bash kind=combat skill classes=knight 5)
[01:14] skill knight 5: staged (ok=True)
[01:14] skill knight 5: practising
[01:27] skill knight 5: using (practice=1->28)
[03:02] skill knight 5: done (uses=2 worked=2 fights=the small troll: fled, the small troll: won)
skill: Skill: bash (185 s, Xania 7901035a37)
  skill bash, kind combat skill, learned by knight 5
  xania_log: runs\skill-20261120-220238\xania.log
  transcripts: runs\skill-20261120-220238
  result: clean
```

</details>

<details><summary>✅ Sim `hunt --minutes 5` on the branch</summary>

```
hunt: Hunt: angry cave beast, 4 bots (306 s, Xania 7901035a37)
  fights 12, bot errors 0, crashed False
  result: clean
```

</details>
