# astro-template

The scaffold for an observational astronomy project: directory layout, working
conventions, and a manuscript toolchain for *Acta Astronomica*. The research
agents are not here — they live in
[`astro-agents`](../astro-agents) and install as a plugin, so one copy serves
every project.

## Start a project

```bash
bin/astro-new my-paper ~/projects
cd ~/projects/my-paper
uv sync
```

`astro-new` copies the scaffold, renames the package, writes a README and a
first notebook entry, and makes the initial commit. The new project has its own
history and no link back to this one.

**One repository per project, not a branch.** `data/raw/` and `data/interim/`
are gitignored, so a branch does not carry them: switching branches would leave
the previous project's files sitting in `data/`, untracked and invisible to
git, where a script written for other data would read them without complaint.
Branches are still right *within* a project — a risky reanalysis, a different
detrending — and a worktree lets you diff the two sets of outputs side by side.

## What the project gets

```
data/raw/       archive downloads, immutable, each with a MANIFEST.md
data/interim/   reduced and calibrated products
data/processed/ final measurement tables
scripts/        rerunnable pipeline steps: fetch_*.py, reduce_*.py, fit_*.py
notebooks/      exploration only
results/        figures and tables for the write-up
paper/          ms.tex in Acta Astronomica style, its class file, and figures/
docs/lit/       literature notes and refs.bib
docs/NOTEBOOK.md  decisions and dead ends, append-only
```

- [`CLAUDE.md`](CLAUDE.md) — units, frames, time systems, provenance. The rules
  every agent follows.
- [`paper/STYLE.md`](paper/STYLE.md) — the Acta class and its non-obvious rules.
  The class is from 2008 and needs two stand-ins that no current TeX Live
  provides; `paper/compat/` supplies them.
- [`scripts/bib2acta.py`](scripts/bib2acta.py) — Acta does not use BibTeX, so
  this turns `docs/lit/refs.bib` into the journal's `\refitem` list.
- [`scripts/ogle.py`](scripts/ogle.py) — OGLE microlensing events and
  variable-star light curves.

## Connecting the agents

`.claude/settings.json` declares where the agents come from, and is committed,
so each project records which agents it used:

```json
{
  "extraKnownMarketplaces": {
    "astro-agents": {
      "source": { "source": "github", "repo": "kkolsut/astro-agents" }
    }
  },
  "enabledPlugins": { "astro@astro-agents": true }
}
```

A new project needs one command to actually install it:

```bash
claude plugin install astro@astro-agents --scope project
```

This tracks the default branch, which is what you want while the agents are
still being edited. **When a paper is submitted, pin it**, so the published
result can say which version of `results-referee` checked its numbers:

```json
"source": { "source": "github", "repo": "kkolsut/astro-agents", "ref": "v1.2.0" }
```

`ref` takes a tag, a branch, or a commit SHA. On a self-hosted git host use
`{ "source": "git", "url": "..." }` instead, with a URL that **ends in
`.git`** — without the suffix Claude Code treats it as a link to a JSON file
and never clones.

## Keeping the template current

A project is a copy, so improvements made while writing one paper do not flow
back. When something in `paper/`, `scripts/bib2acta.py` or `CLAUDE.md` turns
out to be wrong or missing, fix it **here** as well, or the next project starts
from the old version. The agents do not have this problem — they update
centrally, which is why they are a plugin and this is not.
