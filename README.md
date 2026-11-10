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
| 4. Technical debt | `string_view`s indexed like C strings, long functions, legacy idioms, TODO/FIXME marks |
| 5. Gameplay | How players reach it, what runs it automatically, the messages it can show, whether Explorer's balance numbers depend on it |
| 6. Documentation | Help entries for the commands and ones that mention the functions; docs in the checkout |
| 7. Test coverage | Unit test files for the touched files (by name, include or mention), functions no test calls, Sim scenarios that send the commands, Sim findings about the functions |

The dossier ends with a **gate plan**: the builds, unit tests and Sim trials (`smoke` always; `hunt` when fights
reach the code; `churn` for logins, quits and lifetimes; `skill` for a spell; scenarios that send the commands)
that `prototype` will run, and the Sim findings that should stop reproducing.

The source index is lexical: there's no compiler involved, so calls are matched by name (an overloaded name
counts as a call to every definition with it). Each section is gathered on its own, so one that can't run (no
Explorer, no Sim database) says why and the rest carry on.

## Exit codes and --json

Like Sim: **0** done and nothing needs attention, **1** done but something does (research: nothing in the idea
pointed at the code; doctor: an optional part is missing), **2** couldn't run. `--json` prints the result on stdout;
the summary goes to stderr.

## Roadmap

- **B0-B1 (done)**: config, `doctor`, `research` and the dossier.
- **B2**: `prototype`, the gate: debug and ASan builds, unit tests, the dossier's Sim trials, Explorer's comparison
  of the base against the branch. It needs Sim's A/B commit comparison.
- **B3**: first pilot, [abraidotti/xania#1](https://github.com/abraidotti/xania/issues/1) (`do_get` reads past the
  end of `"all"`), end to end: research, fix on a fork branch, gate, pull request on the fork.
- **B4**: [abraidotti/xania#2](https://github.com/abraidotti/xania/issues/2), the use-after-free on quit.
- **B5**: a feature, from an Explorer recommendation or an open upstream request.
- **Later**: Builder's own code-level testing (unit tests, fuzzing functions directly, checking area and player
  files) and Sim's careless and abusive players against the commands a change touches.

The one hard rule: every change is gated on the fork first. Nothing goes upstream from Builder.

## Licence

MIT.
