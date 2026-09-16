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

`.claude/settings.json` declares where the agents come from. It ships pointing
at a local checkout:

```json
{
  "extraKnownMarketplaces": {
    "astro-agents": {
      "source": { "source": "directory", "path": "/home/sisio/projects/astro-agents" }
    }
  },
  "enabledPlugins": { "astro@astro-agents": true }
}
```

Once `astro-agents` is pushed to a git host, change that to the remote so a
fresh clone on any machine resolves it — and so the project records which
version it used:

```json
"source": { "source": "git", "url": "https://git.example.internal/you/astro-agents.git", "ref": "v1.0.0" }
```

On a self-hosted host the URL **must end in `.git`**, or Claude Code treats it
as a link to a JSON file and never clones. Pinning `ref` to a tag is what lets
a finished paper say which version of `results-referee` checked its numbers.

## Keeping the template current

A project is a copy, so improvements made while writing one paper do not flow
back. When something in `paper/`, `scripts/bib2acta.py` or `CLAUDE.md` turns
out to be wrong or missing, fix it **here** as well, or the next project starts
from the old version. The agents do not have this problem — they update
centrally, which is why they are a plugin and this is not.
