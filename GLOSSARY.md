# Glossary — and how to talk to me

I am learning software engineering vocabulary as I go. This file is how you know
which words to explain and, just as importantly, which to leave alone.

There are two of these files:

- **`GLOSSARY.md`** (this one) comes from the template and holds settled
  vocabulary. **Do not edit it inside a project** — it is replaced wholesale by
  `copier update`, so edits here are lost.
- **`GLOSSARY.project.md`** is where words met during *this* project go. It does
  not exist until the first word is added; create it then, with the same two
  section headings as below. It is never overwritten by a template update.

Read both. The union of the two is "what the owner knows". Periodically I will
ask you to fold the project file's words into the template's copy; when that
happens, **remove them from the project file** so the same word never lives in
two places.

---

## How to talk to me

1. **While working, talk normally.** Commentary between tool calls can be as
   dense and jargon-heavy as you like. Do not stop to explain mid-flow.
2. **Final summaries are high level.** Lead with what changed and why it
   matters. Where a detail genuinely matters, explain it properly — but only far
   enough to land, never to exhaustiveness. Length is not thoroughness.
3. **A word in neither list is unknown.** Use it, gloss it in passing, then
   **ask which list it belongs in** — I may already know it, or may have met it
   and want the repetition. If I don't answer, put it in *learning*:
   over-explaining once is cheaper than silently assuming.
4. **Never re-explain a word from "learned".** That list exists to be obeyed.
   Use the word plainly, as you would with any colleague.
5. **Only I promote words.** You may suggest — "you've seen `pathspec` a few
   times now, promote it?" — but never move one yourself. A silent promotion
   means you go quiet on something I never absorbed, and I'd have no way to
   tell why.
6. **This governs conversation with me only.** Not the CI review agent, which
   writes for a script that parses one line. Not commit messages, code comments,
   or pull request bodies — those are written for a technical reader and should
   stay in normal engineering register.

### How to write an entry

An entry **frames** the word — one or two sentences that use it in a context
where the meaning becomes obvious. It is not a dictionary definition.

- Dictionary style, **avoid**:
  *fail closed — to deny by default when an error occurs.*
- Framing style, **use**:
  *fail closed — when the review gate can't reach the model, it blocks the merge
  rather than waving the change through; it **fails closed**, because the safe
  direction on error is "no".*

Reuse an entry's wording verbatim when the word comes up. Hearing the same
framing repeatedly is what moves a word into someone's vocabulary; inventing a
fresh explanation each time is what stops it sticking.

---

## Words I'm learning

> Seeded from real working sessions, so some of these I may already know —
> promote them freely on a first read-through.

### Git and version control

- **diff** — the list of exactly which lines a change adds and removes. Almost
  every gate in this project is really "something reading the **diff**".
- **base / head** — in a pull request, **base** is the branch you want to merge
  into and **head** is the branch carrying your changes. Most checks compare the
  two.
- **merge base** — before comparing your branch to `main`, git finds the last
  commit they both share; that common ancestor is the **merge base**, and
  everything after it is "your changes".
- **ref** — a name that points at a commit: `main`, `origin/main`, a tag. Turning
  a **ref** into the raw commit id is what `git rev-parse` does.
- **HEAD** — whichever commit you currently have checked out. "Detached HEAD"
  just means you're sitting on a commit directly instead of on a branch.
- **staged / the index** — `git add` doesn't commit anything; it moves changes
  into a holding area, **the index**, and the next commit captures whatever is
  **staged** there.
- **pathspec** — the `-- src/ tests/` part of a git command, narrowing it to
  certain paths. Git also reads special forms like `:(exclude)` in a
  **pathspec**, which is why paths from untrusted files get `--literal-pathspecs`.
- **trailer** — the `Co-Authored-By: ...` line at the foot of a commit message.
  A **trailer** is a structured `Key: value` footer that tooling can read back
  out later — which is how the blind-test check finds its commits.
- **worktree** — one clone normally gives you one checked-out copy. `git
  worktree` gives you a second folder on a different branch sharing the same
  history, so parallel agents each get their own **worktree** and never trip
  over each other's files.
- **rebase** — instead of merging `main` into your branch, a **rebase** replays
  your commits on top of the current `main`, producing a straight line of
  history rather than a fork-and-join.
- **force-push** — a normal push adds commits; a **force-push** overwrites the
  branch's history on the remote. Banned here on anything already pushed,
  because it destroys work someone else may have pulled.
- **revert vs. reset** — `git revert` writes a *new* commit that undoes an old
  one, leaving history intact. `git reset` rewinds history as though it never
  happened. On a shared branch you always **revert**.
- **merge conflict** — when two changes touch the same lines and git can't
  decide which wins, you get a **merge conflict** and have to choose by hand.
- **conflict markers** — what git (and copier) leave *in the file* when they
  can't resolve a conflict: your version and theirs, fenced by `<<<<<<<`,
  `=======` and `>>>>>>>`. The file is not valid code until you keep one side
  and delete the **conflict markers** — which is also why nothing should ever
  commit while they are present.
- **`git switch` / `git restore`** — `git switch` moves between branches
  (`-c` creates one first); `git restore` throws away changes to files. They
  were split out of `git checkout` in 2019 because one command doing both was
  genuinely dangerous: `git checkout somefile.py` silently discards your edits
  to that file and looks almost identical to the branch command. `checkout`
  still works; **`switch`** is the half that cannot surprise you.

### CI and automation

- **CI** — the robot that checks out your branch on a fresh machine and runs
  everything on every push. **CI** is what makes "works on my machine" stop
  being an argument.
- **runner** — the throwaway virtual machine that executes a CI job. macOS
  **runners** bill at roughly ten times the rate of Linux ones, which is why the
  swift jobs get watched so carefully.
- **job / step** — a workflow is made of **jobs** (each on its own runner, run in
  parallel by default), and each job is a list of **steps** run in order.
- **matrix** — running the same job once per variant — per language, per Python
  version — from a single definition. The template's own CI uses a **matrix** to
  render both python and swift-ios.
- **gate** — any check that can stop a change from landing. This project has
  four **gates**, and most of its design is about making sure none of them can
  be quietly disarmed.
- **hard vs. soft gate** — the **hard gate** is mechanical and authoritative:
  tests either pass or they don't. The **soft gate** is a judgement layered on
  top, and it never replaces the hard one.
- **fail closed / fail open** — when a check breaks for its own reasons, failing
  **closed** means it blocks the merge anyway; failing **open** means it waves
  the change through. Gates must **fail closed**, because an error that looks
  like a pass is worse than no gate at all.
- **required status check** — GitHub refuses to merge until the checks you
  marked **required** report green. A check that isn't marked required is just
  advice nobody has to take.
- **branch protection** — the settings on `main` that stop direct pushes and
  demand checks first. The template can't switch **branch protection** on from
  inside the repo, which is why the README walks you through it by hand.
- **CODEOWNERS** — a file listing which paths need whose approval. If a pull
  request touches a path in **CODEOWNERS**, GitHub demands a review from that
  owner before it can merge.
- **concurrency group** — push twice quickly and you get two CI runs, the first
  now testing a commit nobody will merge. A **concurrency group** cancels the
  superseded run instead of paying for it.
- **PAT (personal access token)** — a password-substitute you generate for
  automation, scoped to exactly what it may touch. A project's CI gets a token
  automatically, but only for its own repository — reading a *different* private
  repo needs a **PAT** you create and store as a secret. Fine-grained ones expire
  (a year at most), and everything depending on them fails at once when they do.
- **secret** — a value stored in a repository's settings rather than in its
  files, exposed to CI as an environment variable and masked in the logs. Where
  a token belongs; committing one instead is what `gitleaks` exists to catch.
- **exit code** — every command finishes with a number: `0` means success,
  anything else means failure. CI decides whether a step passed by reading its
  **exit code**, nothing more.
- **rate limit** — a cap on how much you can ask of a service inside a given
  window of time. Sixteen agents working at once share one subscription's
  **rate limit**, which is how a wide fan-out ends up starving the review gate
  of the capacity it needs to run.
- **throughput vs. latency** — **throughput** is how much work finishes per unit
  of time; **latency** is how long any one piece takes. Doubling the workers
  improves throughput and does nothing whatsoever for the latency of a single
  slice.
- **saturate** — to use up all of something's available capacity, leaving none
  for anything else. Workers can **saturate** the budget their own review gate
  needs.
- **polling** — repeatedly asking "is it finished yet?" instead of being told
  when it is. **Polling** a CI run every ten seconds spends real budget on an
  answer that has not changed since the last time you asked.

### Testing

- **fixture** — setup that pytest hands to a test: a temp folder, a fake clock, a
  patched socket. A **fixture** keeps the test body about the behaviour instead
  of the scaffolding.
- **autouse** — a normal fixture runs only for tests that ask for it; an
  **autouse** fixture applies to every test automatically. That's how the
  offline rule gets enforced without anyone remembering to opt in.
- **mocking** — replacing a real dependency with a stand-in that returns
  whatever you tell it. You **mock** at real boundaries — the network, the
  clock, the filesystem — and never the thing you're actually testing.
- **loopback** — `127.0.0.1` and `localhost`: the machine talking to itself.
  **Loopback** traffic never leaves the box, which is why the offline test rule
  allows it.
- **regression test** — a test written so that a bug which already happened once
  cannot come back. Most tests added after a fix are **regression tests**.
- **mutation testing** — deliberately breaking your own code to check the tests
  notice. `test-the-tests` is a crude one-shot version of **mutation testing**:
  it removes the implementation and fails if the suite stays green.
- **flaky** — a test that passes sometimes and fails sometimes with no code
  change. A **flaky** test is worse than a failing one, because it teaches
  everyone to ignore red.
- **fixture data / golden file** — a saved expected output that a test compares
  against, instead of recomputing what the answer should be.

### Working with agents

- **orchestrator / worker** — the session that splits a job up and hands out the
  pieces is the **orchestrator** (the owner calls these **orcs**, and you should
  read it that way when they do); each agent doing one piece is a **worker**.
  This project permits exactly one level of that.
- **headless** — an agent run with no interactive session: handed a prompt, left
  to finish alone, output captured to a log. Workers run **headless**.
- **context window** — everything a model can see at once — files, conversation,
  the diff — has a size limit, the **context window**. Overflowing it is why the
  review gate now caps how much diff it sends.
- **prompt injection** — text inside data the model is reading — a diff, a
  comment, a web page — that tries to issue it instructions. The defence is
  telling the model which parts are data and marking the boundary so it can't be
  forged.
- **sandbox** — running an agent fenced into a small area, unable to reach the
  rest of your disk or the network. Keeping the **sandbox** on is what makes it
  safe to let a worker execute code nobody has read yet.
- **blast radius** — how much can go wrong if one thing fails or leaks. Handing
  one broad API key to five parallel unattended agents is a large **blast
  radius** for very little benefit.
- **unattended** — running with nobody watching, so the agent has to decide for
  itself when to stop. Most of the rules in `AGENTS.md` exist for **unattended**
  work specifically — they are what a session follows when you are asleep.
- **fan-out** — spawning many parallel workers from a single point. A wide
  **fan-out** gets the work done sooner and makes everything downstream harder:
  more diffs to assemble, more reconciliations, more chances two workers
  collided.

### The template's own tooling

- **Copier** — the tool this template runs on. It reads the `template/` folder,
  asks its questions, and produces a new project. `copier update` later pulls
  template improvements into an already-generated project.
- **render** — turning a template file full of placeholders into a real file
  with your answers filled in. The template is **rendered** once per project.
- **Jinja** — the placeholder language inside template files. A name wrapped in
  double curly braces — `project_name` written that way — is a **Jinja**
  expression, swapped for your actual answer at render time. Anything it doesn't
  recognise passes through untouched, which is how a leaked placeholder ends up
  visible in a generated project.
- **scaffold** — the empty-but-working skeleton of a project, generated before
  any real code exists. What you get from `copier copy` is a **scaffold**.
- **lockfile** — `pyproject.toml` says roughly which versions you want; a
  **lockfile** (`uv.lock`) records exactly which ones were resolved, so every
  machine installs an identical set.
- **linter vs. formatter** — a **formatter** rewrites layout to one style with no
  judgement involved; a **linter** hunts for likely mistakes and questionable
  patterns. Ruff happens to do both.
- **shellcheck** — a linter for shell scripts. It catches the specific ways bash
  quietly does the wrong thing: unquoted variables, ignored exit codes,
  conditions that are always true.

### General engineering

- **dogfooding** — running your own product on yourself before shipping it. The
  template now runs its own gates over its own code, which is **dogfooding** it.
  From "eating your own dog food".
- **ratchet** — a mechanism that only turns one way. Here: every bug that
  escapes must also buy a permanent check, so the floor rises and never drops
  back down.
- **escape hatch** — a deliberate way around a rule for the rare case that needs
  it, like the `chore/` prefix skipping the plan check. A good **escape hatch**
  is visible and hard to abuse; a bad one is a hole.
- **idempotent** — safe to run twice: the second run leaves you where the first
  one did. Making `/orchestrate`'s branch setup **idempotent** is what let it be
  re-run to dispatch a fix.
- **stdin / stdout / stderr** — every command has three streams: input arriving
  (**stdin**), normal output leaving (**stdout**), and error messages kept
  separate (**stderr**) so you can capture results without diagnostics mixed in.
- **pipe** — the `|` in `a | b`, feeding a's stdout straight into b's stdin.
- **heredoc** — the `<<EOF ... EOF` block in a shell script: several lines of
  literal text written inline and handed to a command as input.
- **verbatim** — copied exactly, character for character, with nothing
  substituted or interpreted.
- **regex** — a compact pattern language for matching text. The
  `^[a-z][a-z0-9-]*$` in the slug validator is a **regex** reading "a lowercase
  letter, then any number of lowercase letters, digits or dashes, then the end".
- **provenance** — where something came from and who produced it. A fork's pull
  request has different **provenance** from a branch in your own repository,
  which is why auto-merge checks before arming.
- **wholesale** — replaced entirely rather than merged piece by piece.
- **waterfall** — the old way of building software: every decision made up front,
  in order, before any code exists, with no route for what you learn while
  building to get back into the plan. Vertical slices exist to avoid
  **waterfall** — they create points where re-steering is still cheap.
- **CRUD** — Create, Read, Update, Delete: the four basic operations on stored
  data. A "**CRUD** app" is one whose behaviour is mostly those four over some
  records, which is shorthand for well-understood, low-surprise work.
- **port** (as a verb) — moving working software to a new language, platform or
  framework without changing what it does. A **port** is predictable work
  precisely because the target behaviour already exists to compare against.
- **recall** — a filter's **recall** is how much of the real signal it keeps. If
  fifty items genuinely match and the filter finds forty, its recall is 80% —
  and the ten it dropped are invisible, because nothing in the output says they
  existed. That is why **recall** is usually the risk worth watching: a filter
  that returns only correct results can still be badly wrong by omission.

---

## Words I've learned

> Do not explain these. Use them plainly.

load-bearing
