# Astronomy project

Analysis is done through the specialised subagents in the `astro` plugin — `project-scout`,
`lit-scout`, `archive-scout`, the photometry/spectroscopy/timeseries analysts,
`inference-modeler`, `theory-sim-analyst`, `figure-smith`, `paper-wright` and
`results-referee`. They are declared in `.claude/settings.json` and come from the
`astro-agents` repository, not from this one. Describe the task and the right one is
selected; name one when you want a particular perspective.

Anything project-specific goes in `.claude/agents/` here, which is scanned recursively and
merged with the plugin's. A name that collides silently overrides the plugin's version.

## Environment

Python is managed with `uv`. The pinned interpreter is in `.python-version`; dependencies are in
`pyproject.toml`.

```bash
uv sync                  # create/update .venv from pyproject.toml
uv run python script.py  # run inside the venv
uv add photutils         # add a dependency (edits pyproject.toml)
```

Never `pip install` into the system Python. Never run a script with bare `python3` — it will not
see the project's packages.

## Layout

```
data/raw/       archive downloads, immutable — never edited in place, each with a MANIFEST.md
data/interim/   reduced/calibrated products (regenerable from raw + scripts)
data/processed/ final measurement tables, ready for plotting or fitting
scripts/        rerunnable pipeline steps; fetch_*.py, reduce_*.py, fit_*.py
notebooks/      exploration only — anything that produces a result graduates to scripts/
results/        figures and tables that go into the write-up
paper/          the manuscript: ms.tex in Acta Astronomica style, see paper/STYLE.md
paper/figures/  publication figures, each produced by a script in scripts/
docs/lit/       literature notes and refs.bib
docs/NOTEBOOK.md  append-only record of decisions and dead ends
```

Raw data is read-only. Every file in `data/interim/` and `data/processed/` must be reproducible by
rerunning something in `scripts/`.

## Conventions that apply to every agent

- **Units are explicit.** Use `astropy.units` on anything physical. Never pass a bare float across a
  function boundary where the unit is not in the name.
- **Coordinates are explicit.** `astropy.coordinates.SkyCoord` with a stated frame and epoch.
- **Times are explicit.** `astropy.time.Time` with `format` and `scale` given. BJD_TDB is the default
  for anything time-critical.
- **Uncertainties travel with values.** A measurement without an error bar is not a result.
- **Provenance is recorded.** Every derived product notes the query, script, and input files that
  produced it.
- **Decisions go in the notebook.** Append to `docs/NOTEBOOK.md` when a question is set or narrowed,
  a dataset or method is chosen over an alternative, or something is tried and abandoned. Agents
  start cold and long conversations get summarised — what is not written there is lost. Record the
  reason, not the command log, and use absolute dates.
- **Tables are ECSV or FITS**, not bare CSV — the units and metadata survive the round trip.
- **Figures**: perceptually uniform colour maps (viridis, magma, cividis), labelled axes with units,
  error bars shown. No rainbow maps.

## Writing

The manuscript is `paper/ms.tex`, in Acta Astronomica's own class. Read `paper/STYLE.md` before
editing it — the class has rules that are not guessable, and `acta.cls` is the journal's file and is
never edited. `cd paper && make` builds; `make check` reports missing prerequisites.

Acta does not use BibTeX. The reference list is generated from `docs/lit/refs.bib` with
`uv run python scripts/bib2acta.py docs/lit/refs.bib -o paper/references.tex`.

No number is typed into the text by hand. Every value in the manuscript comes from a file in
`data/processed/` or `results/`, and gets checked against it before the draft is called done.

## Reporting

State what limits a result, not just the result. When data cannot support the question asked, say so
rather than returning a number with an optimistic error bar. Flag preprints as preprints, upper
limits as upper limits, and marginal detections as marginal.
