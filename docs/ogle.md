# OGLE data access

OGLE (Optical Gravitational Lensing Experiment, Warsaw University Observatory) publishes its data
over plain HTTP/FTP with no VO service. `astroquery.ogle` exists but wraps only the OGLE-III
interstellar extinction calculator — it cannot retrieve a light curve. `scripts/ogle.py` is this
project's access layer for the parts that matter.

```python
import sys; sys.path.insert(0, "scripts")
from ogle import ews_events, ews_photometry, ocvs_catalog, ocvs_params, ocvs_photometry, \
                 ocvs_cone_search, ocvs_available, as_bjd_tdb, write_manifest
```

Everything is cached under `data/raw/ogle/`, so repeat calls are free and work offline.

## Microlensing — the Early Warning System

```python
ev = ews_events(2019)                     # 1526 events in the 2019 season
lc = ews_photometry("2019-BLG-0001")      # 3335 I-band points
```

`ews_events` returns the season's event list with point-lens model parameters: `tmax` (HJD), `tau`
(Einstein timescale, days), `umin`, `amax`, `dmag`, `fbl` (blended flux fraction), `i_bl`, `i0`, plus
a `coord` column. `ews_photometry` returns `hjd`, `mag`, `mag_err`, `seeing`, `sky`.

Seasons run from 2002 (OGLE-III) to the present. The `seeing` and `sky` columns are the cheapest
quality cut you have — in these crowded fields, poor-seeing points are systematically biased by
blending, not just noisier.

**Read `tau` and `fbl` together.** A long timescale with a small blending fraction is the standard
signature of a degenerate fit, not of a massive lens. The EWS parameters are real-time alerts, not
publication-grade fits; refit the photometry yourself for anything quantitative.

## Variable stars — the OGLE Collection of Variable Stars

```python
ocvs_available("blg")
# ['cep','dpv','dsct','ecl','hb','lpv','rot','rrlyr','short_period_ecl','t2cep','transits']

cat  = ocvs_catalog("blg", "rrlyr")             # 68509 stars, with coordinates and cross-IDs
pars = ocvs_params("blg", "rrlyr", "RRab")      # 48859 rows: periods, epochs, amplitudes
lc   = ocvs_photometry("OGLE-BLG-RRLYR-00001")  # 121 I-band points
```

Fields: `blg` (Galactic bulge), `gd` (Galactic disk), `gal`, `lmc`, `smc`. Available variability
classes differ by field — call `ocvs_available()` rather than assuming; the LMC has `acep`, the bulge
does not.

Cone search against a catalog:

```python
from astropy.coordinates import SkyCoord
import astropy.units as u
near = ocvs_cone_search("blg", "rrlyr", SkyCoord("17:05:07.49", "-32:37:57.2",
                                                 unit=(u.hourangle, u.deg)), 2*u.arcmin)
```

`ocvs_params` column layouts are **class-specific**. The function attaches a `readme` link in
`table.meta` — read it before interpreting columns. Do not assume the RR Lyrae layout applies to
Cepheids.

V-band light curves exist (`ocvs_photometry(..., band="V")`) but coverage is much sparser than I, and
many stars have none.

## Gotchas

These are encoded in `scripts/ogle.py` and in `archive-scout`'s prompt. They are listed here because
anyone extending the module needs to preserve them.

**The pages and the data are on different hosts.** HTML lives on `ogle.astrouw.edu.pl`; the files
live under `www.astrouw.edu.pl/ogle/`. Requesting a data file from the page host returns a 404 HTML
document — which `Table.read` will happily turn into an empty or garbage table rather than raising.
`_fetch()` rejects HTML bodies explicitly for this reason.

**Times are geocentric HJD on a UTC-based scale — never BJD_TDB.** The two collections even differ
from each other: EWS stores full HJD, OCVS stores HJD − 2450000 (the module normalises OCVS to full
HJD on read, so both return the same convention). Convert before combining with any space-mission
time base:

```python
t = as_bjd_tdb(lc, coord)     # OGLE observes from Las Campanas; site="lco" is the default
```

Measured shift for a bulge target: **66–68 seconds**. Irrelevant for a 100-day microlensing event;
fatal for an eclipse ephemeris propagated across a decade, or for combining OGLE with TESS.

**Magnitudes are OGLE I and V**, Cousins/Johnson-like, not SDSS i/g.

**Crowding.** These are among the densest fields on the sky. A 1″ positional match is not an
identification, and blending affects the photometry itself, not merely the astrometry.

**No proper motions.** Catalog positions are at the survey epoch; propagate before matching to Gaia.

**`ident.dat` is fixed-width**, not whitespace-delimited — the trailing cross-identification column
contains spaces. The module parses by byte range per the OCVS README.

## Citing

Each OCVS directory has a README naming the catalog paper — cite that, not only the survey. The
survey-level reference is Udalski, Szymański & Szymański (2015), *Acta Astron.* 65, 1. `write_manifest()`
emits the acknowledgement text alongside any download.

## Upstreaming to astroquery (deferred)

Worth doing eventually — the light-curve databases are a real gap, and the gotchas encoded here are
exactly what a shared module should carry. Notes for whoever picks it up:

- **It is an extension, not a new module.** `astroquery/ogle/` already exists, and its `Ogle` class
  already owns `query_region` for the extinction calculator. New entry points need different names
  (`query_events`, `query_photometry`, …) or a submodule; do not overload the existing one.
- **Open an issue before a PR.** astroquery is conservative about modules that read a directory tree
  rather than a documented service, and OGLE offers no API. Precedent exists, but get maintainer
  agreement on the approach first — a large unsolicited PR is the slow path.
- **The plumbing here would be replaced wholesale.** `_fetch()` uses `urllib` and a hand-rolled cache;
  astroquery wants a `BaseQuery` subclass, `self._request()`, its own cache, and the
  `async_to_sync` / `*_async` pattern. What survives the rewrite is the domain knowledge: the split
  hosts, the two time conventions, the fixed-width `ident.dat` layout, the per-class parameter files.
- **Tests are the bulk of the work.** Mocked-response tests with committed fixtures, plus
  `@pytest.mark.remote_data` for live checks. Trim fixtures aggressively — `ident.dat` is 7 MB.
- Also needs `docs/ogle/ogle.rst` and a `CHANGES.rst` entry.

Until then, treat `scripts/ogle.py` as the local answer and keep the gotcha comments intact — they
are the part worth contributing.

## What is not covered

The OGLE photometric maps, the Transient Detection System, and the OGLE-II/III archival releases have
different directory layouts and are not wrapped. They are reachable under the same `DATA_ROOT`; add
functions to `scripts/ogle.py` rather than writing a separate scraper.
