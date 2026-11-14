# Xania Builder

Builder develops changes to [Xania](https://github.com/mattgodbolt/xania), the MUD: fixes and features, researched
before any code is written and gated on a fork before anything goes further. It's the third of three tools:

- [Xania Explorer](https://github.com/abraidotti/xania-explorer) **assesses** the game: balance across levels 1-91,
  bug checks on the code and area data, recommendations.
- [Xania Sim](https://github.com/abraidotti/xania-sim) **plays** it: bots that test it through the client, from
  careful players to abusive ones, with trials that report in JSON and exit codes.
- **Xania Builder** **builds** on both: it researches an idea, gates a change with builds, unit tests and Sim
  trials, and ships it to the fork.

Builder doesn't write the code. It gathers the facts and asks the questions; whoever writes the change (a person or
a coding assistant) works from the dossier, and the gate decides whether it's ready.

## Setup

Python 3.12+, standard library only. Builder reads a Xania checkout and uses Explorer and Sim, by default from
sibling checkouts:

```
xania/              # a checkout of your fork
xania-explorer/
xania-sim/
xania-builder/
```

```
cp builder.example.toml builder.toml      # adjust paths if yours differ
python -m xania_builder doctor            # checks the checkout, Explorer, Sim, Sim's findings and gh
python -m pytest                          # unit tests (a small fake checkout; no build needed)
```

`gh` (the GitHub CLI) is needed to read issues and, later, to open pull requests.

## Issue first: when a change needs decisions

Some changes aren't just bugs with one right fix. Fixing them means choosing a rate, a rule or a behaviour that
players will feel. For those, file an issue on the fork first and open a PR only once every question is answered:

1. **Evidence first.** Explorer's counts (what in the world is affected, at which levels) and a Sim trial showing
   what the game does today, with numbers.
2. **Options, with numbers.** Two or so ways to fix it, each with what it would mean in play, plus how comparable
   codebases do it, where that helps.
3. **Questions, each with a recommended answer.** Every open decision becomes a numbered question with a
   recommendation and the reason for it, so a reader can just agree or push back. People find this far easier to
   act on than bare questions.
4. **Wait for answers**, then research, gate and ship as usual, with the PR saying which answer each choice follows.

The issue uses the same five headings as a bug report (Summary, How to reproduce, Faulty lines, Suggested fix, How
this was found), with the options and questions under Suggested fix. Example:
[abraidotti/xania#9](https://github.com/abraidotti/xania/issues/9) (vampiric weapons).

## Research: the dossier

```
python -m xania_builder research '#1'                         # an issue on the fork
python -m xania_builder research bug:code.lose-level-asymmetry   # an Explorer bug check
python -m xania_builder research "Let players bank gold" --command deposit --file src/act_obj.cpp
```

Research writes `dossiers/<slug>/dossier.md` (to read) and `dossier.json` (for tools). It first works out the
**focus**: the functions, files and commands the idea is about. From the idea's prose it takes `file.cpp:123`
references (the function around that line), function names written alone in backticks, and commands. From a
backtrace it takes the innermost frame in Xania's source, and keeps the rest as the reported call path. Code
blocks such as suggested patches don't count. `--symbol`, `--file` and `--command` add to the focus.

Then it writes seven sections. Each one has **facts** it gathered and **questions** that need judgement:

| Section | What it gathers |
|---|---|
| 1. Explorer insights | Bug checks whose occurrences or text touch the focus; the assessments that read the same files, their main findings and code recommendations |
| 2. Architecture | Where each function is, the commands it handles (and from which position), its callers (including ones no player types, like autoloot), what it calls, any persisted state it reaches |
| 3. Design patterns | The idioms in each function against the codebase (`ArgParser`, `string_view`, `matches()`, `act()` vs `char` buffers, `sprintf`, `'\0'` checks), helpers it already has, functions of the same shape nearby |
| 4. Technical debt | `string_view`s indexed like C strings (a `[0]` with the same view's `empty()` tested in the 15 lines before it counts as guarded; comments don't count; a guard on something else, like `args.empty()` before `args.shift()[0]`, isn't seen), long functions, legacy idioms, TODO/FIXME marks, and the same pattern anywhere else in `src/` |
| 5. Gameplay | How players reach it, what runs it automatically, the messages it can show, whether Explorer's balance numbers depend on it |
| 6. Documentation | Help entries for the commands and ones that mention the functions; docs in the checkout |
| 7. Test coverage | Unit test files for the touched files (by name, include or mention), functions no test calls, Sim scenarios that send the commands, Sim findings about the functions |
| 8. History | When each variable the faulty lines index took its current form (`git blame` on its declaration), who last changed each faulty line, the commits each function comes from, compiler and flag changes since the bug began, what Debug and Release builds turn on, and upstream issues and PRs that mention the functions |

`--at REF` researches the code as it is at a commit (the base a fix will be compared with), from a cached worktree,
so a checkout that's already on the fix branch still gets a dossier of the bug. Section 4 also sweeps all of `src/`
for the same pattern, so a reviewer can see whether the fix leaves the same bug next door.

The dossier ends with a **gate plan**: the builds, unit tests and Sim trials (`smoke` always; `hunt` when fights
reach the code; `churn` for logins, quits and lifetimes; `skill` for a spell; scenarios that send the commands)
that `prototype` will run, and the Sim findings that should stop reproducing.

The source index is lexical: there's no compiler involved, so calls are matched by name (an overloaded name
counts as a call to every definition with it). Each section is gathered on its own, so one that can't run (no
Explorer, no Sim database) says why and the rest carry on.

## Analysis: the answers

Research asks; someone answers. Whoever writes the change adds `analysis.md` to the dossier folder: the root cause
(with the history), the fix and the alternatives it beat, what players will notice, an answer to every question the
dossier asked, and what's deliberately left out. It's the part a reviewer reads first, and `ship` builds the pull
request from it. [dossiers/issue-1-do-get-reads-past-the-end/analysis.md](dossiers/issue-1-do-get-reads-past-the-end/analysis.md)
is the first one.

## Prototype: the gate

```
python -m xania_builder prototype '#1' --branch fix/1-do-get-all
```

The gate proves the change against its base (the merge-base with the fork's main, or `base` in the dossier's
`gate.toml`), in WSL where Xania builds, in worktrees under `~/xania-gate/<dossier>/`:

| Step | What it checks |
|---|---|
| format | `make check-format`, as CI |
| builds | Debug (here: ASan, UBSan, LSan, and libstdc++'s assertions, which GCC 15 turns on at -O0) and Release (-O2), as CI; `-Werror` |
| unit tests | the whole suite on the branch in both builds (`ctest` as CI, plus Catch2's JUnit report for each case) |
| before/after | the branch's tests applied to the **base** and run in both builds: a test that pins a bug must fail or abort there and pass on the branch; one that passes on both doesn't test the fix |
| Sim | the trials in `gate.toml`, each with what it should find on the base (`reproduces` the finding, or a scenario that `pass`es while the bug is there) and on the branch (`clean`) |
| static | Builder's detectors on the focus functions, base against branch |

It writes `gate.json` and `gate.md` into the dossier folder. `--only` runs some steps (a quick `--only format
static` first is a good preflight). A `gate.toml` looks like:

```toml
base = "82171fa"
[[sim]]
args = ["hunt", "--minutes", "5"]
why = "autoloot runs 'get all corpse' after every kill"
finding = "do_get"       # the finding's signature contains this
base = "reproduces"
branch = "clean"
```

### Disk space

Each dossier's gate keeps two worktrees in WSL, each with a Debug and a Release build: about **13 GB a dossier**.
They stay so a rerun only rebuilds what changed. Before a gate starts, `prototype` checks the free space where WSL's
disk lives (on Windows, the host drive) and refuses with under 20 GB left after a new workspace, warning under 40.

```
python -m xania_builder clean              # list workspaces and their sizes
python -m xania_builder clean '#1' '#3'    # remove those dossiers' workspaces (the dossiers stay)
python -m xania_builder clean --keep 2     # keep only the two most recently used
```

On Windows, WSL's disk is one virtual file (`ext4.vhdx`) that grows as builds fill it and doesn't give space back
to Windows by itself. Make it sparse once (`wsl --shutdown`, then `wsl --manage <distro> --set-sparse true`) and
space freed in WSL returns to Windows automatically.

## Ship and the website

```
python -m xania_builder ship '#1'                  # push the branch, open or update the PR on the fork
python -m xania_builder ship '#1' --to upstream    # by hand, after review: the PR on mattgodbolt/xania
python -m xania_builder site                       # build/site: the website, locally
```

`ship` refuses unless the gate passed at the branch's current commit. The PR description comes from the analysis
and the gate (what was wrong, the fix, what players will notice, the verification tables) and links to the
dossier's page on [the website](https://abraidotti.github.io/xania-builder/), which has everything: the analysis,
the gate with its logs, and the research. GitHub Actions rebuilds the site when `dossiers/` changes on `main`.
Gate logs are published, so home directories in them are redacted to `~`.

## Exit codes and --json

Like Sim: **0** done and nothing needs attention, **1** done but something does (research: nothing in the idea
pointed at the code; doctor: an optional part is missing), **2** couldn't run. `--json` prints the result on stdout;
the summary goes to stderr.

## Roadmap

- **B0-B1 (done)**: config, `doctor`, `research` and the dossier.
- **B2 (done)**: `prototype`, the gate, with before/after runs of the new tests and Sim on both sides.
- **B3 (in progress)**: the first pilots end to end: [#1](https://github.com/abraidotti/xania/issues/1) (`do_get`
  reads past the end of `"all"`), [#3](https://github.com/abraidotti/xania/issues/3) (the lobby prompts) and
  [#2](https://github.com/abraidotti/xania/issues/2) (the use-after-free on quit), each with research, analysis,
  fix, gate, and a PR on the fork; then upstream, by hand.
- **Next for the gate**: Explorer's comparison of base and branch; the string_view detector learning about
  `empty()` guards.
- **B5**: a feature, from an Explorer recommendation or an open upstream request.
- **Later**: Builder's own code-level testing (unit tests, fuzzing functions directly, checking area and player
  files) and Sim's careless and abusive players against the commands a change touches.

The one hard rule: every change is gated on the fork first. Nothing goes upstream unless a person runs `ship --to upstream` after the fork PR has been reviewed.

## Licence

MIT.
