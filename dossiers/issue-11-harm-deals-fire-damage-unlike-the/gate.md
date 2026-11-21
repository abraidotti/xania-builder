# Gate: issue-11-harm-deals-fire-damage-unlike-the

Branch `fix/11-harm-damage-type` at `58ba177c28` against base `eec205e5fd`: **passed** in 4 min, 2026-11-20 22:18.

Environment: gcc g++-15 (Ubuntu 15.2.0-16ubuntu1) 15.2.0; cmake cmake version 4.2.3; os Ubuntu 26.04.1 LTS; distro Ubuntu-26.04

Changes: 1 file changed, 1 insertion(+), 1 deletion(-)

- `58ba177 spell_harm: deal Harm damage again, like the rest of the Harmful group`

| | Step | Expected | Result | Time |
|---|---|---|---|---|
| ✅ | clang-format (make check-format, as CI) | no formatting differences | clean | 2 s |
| ✅ | Debug build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) | 0 s |
| ✅ | Unit tests, Debug, the branch | every test passes | 1090 test cases and sections, all passed | 4 s |
| ✅ | Release build of the branch | it compiles (-Werror) | up to date (nothing to rebuild) | 0 s |
| ✅ | Unit tests, Release, the branch | every test passes | 1090 test cases and sections, all passed | 0 s |
| ✅ | Debug build of the base with the branch's tests | it compiles (-Werror) | up to date (nothing to rebuild) | 0 s |
| ➖ | Unit tests, Debug, the base with the branch's tests | the new tests fail here (they pin the bug) | 0 of 1090 failed | 2 s |
| ✅ | Release build of the base with the branch's tests | it compiles (-Werror) | up to date (nothing to rebuild) | 2 s |
| ➖ | Unit tests, Release, the base with the branch's tests | the new tests fail here (they pin the bug) | 0 of 1090 failed | 0 s |
| ✅ | Sim `smoke` on the branch | it runs and finds no crash | no crash in 22 s | 22 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k harm_deals_fire` on the base | harm hurts the Magic-immune snotling with a fire verb and can't touch the Fire-immune bat: the opposite of cause critical | pytest exit 0: 1 passed, 6 deselected in 41.59s | 42 s |
| ✅ | Sim `pytest scenarios/test_live_bugs.py -k harm_deals_fire` on the branch | harm behaves like cause critical: the snotling is unaffected (Magic immunity), so the known-bug check reports the bug gone | pytest exit 1: 1 failed, 6 deselected in 42.03s | 43 s |
| ✅ | Sim `skill harm --classes cleric --fights 2` on the branch | it runs and finds no crash | no crash in 126 s (skill harm, kind spell, learned by cleric 23) | 127 s |
| ✅ | Proof the bug was there before the change | a new test fails on the base, or a Sim trial shows the bug on the base | Sim showed it on the base: Sim `pytest scenarios/test_live_bugs.py -k harm_deals_fire` on the base | 0 s |
| ➖ | Builder's detectors on the focus, base against branch | no string_view indexed like a C string is left in the focus | doesn't apply: the focus has no string_view indexing, before or after | 0 s |

## Detectors, base against branch

| Function | Base | Branch |
|---|---|---|
| `spell_harm` | none | none |
| `check_damage_tolerance` | none | none |
| `damage` | none | none |
| `spell_cause_light` | none | none |
| `MobIndexData::MobIndexData` | none | none |
| `spell_fireball` | none | none |
| `spec_cast_cleric` | none | none |
| `is_safe` | none | none |

## Logs

<details><summary>✅ Sim `smoke` on the branch</summary>

```
smoke: Smoke: create a bot, look, quit (22 s, Xania 58ba177c28)
  transcript: runs\20261120-221855\Smokea.log
  result: clean
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_bugs.py -k harm_deals_fire` on the base</summary>

```
.                                                                        [100%]
1 passed, 6 deselected in 41.59s
```

</details>

<details><summary>✅ Sim `pytest scenarios/test_live_bugs.py -k harm_deals_fire` on the branch</summary>

```
                    seen[mob, spell] = await _cast(bot, spell, mob)
                    await d.peace()
                    await d.do(f"purge {mob}", expect=None)
        finally:
            try:
                await d.peace()
                await d.restore(bot.name)
            finally:
                await d.close()
        await bot.close()
        assert not any(v.startswith("??") for v in seen.values()), f"a cast neither hit nor was shrugged off, so the " \
                                                                   f"check didn't run: {seen}"
        # the control: Harm damage checks Magic
        assert seen["snotling", "cause critical"] == "unaffected", seen
        assert seen["bat", "cause critical"] != "unaffected", seen
        # harm: Fire damage checks Fire
>       assert seen["snotling", "harm"] != "unaffected", (
            f"harm can't hurt a Magic-immune mob any more: it deals Harm damage again (abraidotti/xania#11 option A), "
            f"retire this test. {seen}")
E       AssertionError: harm can't hurt a Magic-immune mob any more: it deals Harm damage again (abraidotti/xania#11 option A), retire this test. {('snotling', 'harm'): 'unaffected', ('snotling', 'cause critical'): 'unaffected', ('bat', 'harm'): 'UNSPEAKABLE', ('bat', 'cause critical'): 'MASSACRES'}
E       assert 'unaffected' != 'unaffected'
scenarios\test_live_bugs.py:273: AssertionError
=========================== short test summary info ===========================
FAILED scenarios/test_live_bugs.py::test_harm_deals_fire_damage_not_harm - As...
1 failed, 6 deselected in 42.03s
```

</details>

<details><summary>✅ Sim `skill harm --classes cleric --fights 2` on the branch</summary>

```
[00:00] skill trial: planned (skill=harm kind=spell classes=cleric 23)
[01:28] skill cleric 23: staged (ok=True)
[01:28] skill cleric 23: practising
[01:40] skill cleric 23: using (practice=1->75)
[02:03] skill cleric 23: done (uses=4 worked=4 fights=the escaped prisoner: fled, the escaped prisoner: fled)
skill: Skill: harm (126 s, Xania 58ba177c28)
  skill harm, kind spell, learned by cleric 23
  xania_log: runs\skill-20261120-222028\xania.log
  transcripts: runs\skill-20261120-222028
  result: clean
```

</details>
