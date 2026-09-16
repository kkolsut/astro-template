"""Access to OGLE public data releases (Warsaw University Observatory).

OGLE has no VO service and no astroquery module for its light-curve databases --
``astroquery.ogle`` only wraps the OGLE-III interstellar extinction calculator. This module
provides the missing access layer over the public HTTP/FTP tree.

Two collections are covered:

* **EWS** -- the Early Warning System of ongoing microlensing events, one directory per event
  per season, with model parameters and I-band photometry.
* **OCVS** -- the OGLE Collection of Variable Stars: catalogs and light curves for RR Lyrae,
  Cepheids, eclipsing binaries, long-period variables and more, across the Galactic bulge and
  disk, the LMC and the SMC.

Gotchas encoded here, all of which have bitten people before:

* The **HTML pages and the data files are on different hosts.** Pages are served from
  ``ogle.astrouw.edu.pl``; the actual ``phot.dat`` and catalog files live under
  ``www.astrouw.edu.pl/ogle/``. Requesting a data file from the page host returns a 404 HTML
  document, which silently parses as garbage rather than raising.
* **Time conventions differ between the two collections.** EWS ``phot.dat`` carries full
  geocentric HJD (UTC-based); OCVS light curves carry HJD - 2450000. Neither is BJD_TDB.
  ``as_bjd_tdb()`` converts, and nothing here does it implicitly.
* **Magnitudes are OGLE I and V**, standard Cousins/Johnson-like, not SDSS i/g.
* ``ident.dat`` is **fixed-width**, not whitespace-delimited -- the trailing cross-identification
  column contains spaces.

Usage::

    from scripts.ogle import ews_events, ews_photometry, ocvs_catalog, ocvs_photometry

    ev = ews_events(2019)                       # all events of the 2019 season
    lc = ews_photometry("2019-BLG-0001")        # its photometry
    cat = ocvs_catalog("blg", "rrlyr")          # bulge RR Lyrae, with coordinates
    lc = ocvs_photometry("OGLE-BLG-RRLYR-00001")

All downloads are cached under ``data/raw/ogle/``; re-running is cheap and offline-safe.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.time import Time

# Data files. NOT ogle.astrouw.edu.pl -- that host serves the HTML pages only.
DATA_ROOT = "https://www.astrouw.edu.pl/ogle"
# Human-readable event pages, for provenance links.
PAGE_ROOT = "https://ogle.astrouw.edu.pl"

CACHE = Path(__file__).resolve().parent.parent / "data" / "raw" / "ogle"

#: OCVS sky fields.
FIELDS = ("blg", "gd", "gal", "lmc", "smc")

#: OCVS variability classes. Availability differs by field -- see ``ocvs_available()``.
VAR_TYPES = (
    "rrlyr", "cep", "t2cep", "acep", "ecl", "lpv", "dsct",
    "hb", "dpv", "rot", "transits", "short_period_ecl",
)

ACKNOWLEDGEMENT = (
    "This work uses data from the OGLE survey, conducted by the Astronomical Observatory "
    "of the University of Warsaw. Cite the paper describing the relevant OGLE catalog "
    "(see the README in the corresponding data directory) and Udalski, Szymanski & "
    "Szymanski (2015), Acta Astron. 65, 1, describing OGLE-IV."
)


def _fetch(relpath: str, *, refresh: bool = False) -> Path:
    """Download ``relpath`` under DATA_ROOT into the cache, returning the local path."""
    local = CACHE / relpath
    if local.exists() and not refresh:
        return local
    local.parent.mkdir(parents=True, exist_ok=True)
    url = f"{DATA_ROOT}/{relpath}"
    with urllib.request.urlopen(url, timeout=120) as r:
        if r.status != 200:
            raise RuntimeError(f"{url} returned HTTP {r.status}")
        body = r.read()
    # A missing OGLE file returns a 200-with-HTML or a 404 page rather than an error; both
    # would parse as an empty table further down, so reject them here.
    if body.lstrip()[:9].lower().startswith(b"<!doctype") or body.lstrip()[:5].lower() == b"<html":
        raise FileNotFoundError(f"{url} does not exist (server returned an HTML page)")
    local.write_bytes(body)
    return local


# --------------------------------------------------------------------------------------
# EWS -- microlensing events
# --------------------------------------------------------------------------------------

def ews_events(year: int, *, refresh: bool = False) -> Table:
    """Return all microlensing events announced by the EWS in a given season.

    Columns include the event name, field, star number, sky position as a ``SkyCoord``, and
    the point-lens model parameters: ``tmax`` (HJD), ``tau`` (Einstein timescale, days),
    ``umin`` (impact parameter), ``amax``, ``fbl`` (blending fraction), ``i_bl`` and ``i0``.

    A large ``tau`` with small ``fbl`` is the classic signature of a blended, poorly
    constrained fit rather than a long-timescale (massive) lens -- treat the two parameters
    together, not separately.
    """
    path = _fetch(f"ogle4/ews/{year}/lenses.par", refresh=refresh)
    names = ["event", "field", "starno", "ra_str", "dec_str", "tmax", "tmax_ut",
             "tau", "umin", "amax", "dmag", "fbl", "i_bl", "i0"]
    t = Table.read(path, format="ascii.no_header", names=names, data_start=1,
                   guess=False, delimiter=" ")
    t["coord"] = SkyCoord(t["ra_str"], t["dec_str"], unit=(u.hourangle, u.deg), frame="icrs")
    t["tau"].unit = u.day
    for c in ("i_bl", "i0", "dmag", "amax"):
        t[c].unit = u.mag
    t.meta["season"] = year
    t.meta["time_scale"] = "HJD (geocentric, UTC-based) -- not BJD_TDB"
    t.meta["source"] = f"{DATA_ROOT}/ogle4/ews/{year}/lenses.par"
    return t


def ews_photometry(event: str, *, refresh: bool = False) -> Table:
    """Return the I-band light curve of one EWS event, e.g. ``"2019-BLG-0001"``.

    Columns: ``hjd`` (full geocentric HJD), ``mag``, ``mag_err``, ``seeing`` (pixels) and
    ``sky`` (background, ADU). The seeing and sky columns are the cheapest quality cut
    available -- points taken in poor seeing in these crowded bulge fields are systematically
    biased by blending, not merely noisier.
    """
    year, _, rest = event.partition("-")
    slug = rest.lower().replace("-", "-", 1)  # "BLG-0001" -> "blg-0001"
    slug = slug.lower()
    rel = f"ogle4/ews/{year}/{slug}/phot.dat"
    path = _fetch(rel, refresh=refresh)
    t = Table.read(path, format="ascii.no_header",
                   names=["hjd", "mag", "mag_err", "seeing", "sky"])
    t["mag"].unit = u.mag
    t["mag_err"].unit = u.mag
    t.meta["event"] = event
    t.meta["band"] = "I (OGLE)"
    t.meta["time_scale"] = "HJD (geocentric, UTC-based) -- not BJD_TDB"
    t.meta["source"] = f"{DATA_ROOT}/{rel}"
    t.meta["page"] = f"{PAGE_ROOT}/ogle4/ews/{year}/{slug}.html"
    return t


# --------------------------------------------------------------------------------------
# OCVS -- variable star collections
# --------------------------------------------------------------------------------------

# Byte ranges from the OCVS ident.dat README (1-indexed, inclusive), converted to slices.
_IDENT_COLS = {
    "id": (0, 20),
    "subtype": (22, 26),
    "ra_str": (28, 39),
    "dec_str": (40, 51),
    "ogle4_id": (53, 69),
    "ogle3_id": (70, 85),
    "ogle2_id": (86, 101),
    "other_id": (102, None),
}


def ocvs_catalog(field: str, vartype: str, *, refresh: bool = False) -> Table:
    """Return the identification catalog for one OCVS field and variability class.

    ``field`` is one of :data:`FIELDS`, ``vartype`` one of :data:`VAR_TYPES`. Returns the
    star IDs, subtype, an ICRS ``SkyCoord`` column, and cross-identifications to earlier
    OGLE phases and to VSX where they exist.

    Positions are catalog positions at the survey epoch with no proper motion applied; for
    cross-matching against Gaia, propagate rather than matching epoch-blind.
    """
    _check(field, vartype)
    rel = f"ogle4/OCVS/{field}/{vartype}/ident.dat"
    path = _fetch(rel, refresh=refresh)
    rows = {k: [] for k in _IDENT_COLS}
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        for k, (a, b) in _IDENT_COLS.items():
            rows[k].append(line[a:b].strip() if b else line[a:].strip())
    t = Table(rows)
    t["coord"] = SkyCoord(t["ra_str"], t["dec_str"], unit=(u.hourangle, u.deg), frame="icrs")
    t.meta["field"] = field
    t.meta["vartype"] = vartype
    t.meta["source"] = f"{DATA_ROOT}/{rel}"
    t.meta["readme"] = f"{DATA_ROOT}/ogle4/OCVS/{field}/{vartype}/README"
    return t


def ocvs_params(field: str, vartype: str, subtype: str, *, refresh: bool = False) -> Table:
    """Return the parameter file for one subtype, e.g. ``ocvs_params("blg", "rrlyr", "RRab")``.

    Column layout varies by variability class -- read the class README (linked in
    ``table.meta["readme"]``) rather than assuming. The common leading columns are the star
    ID, mean I and V magnitudes, period in days, period uncertainty, and epoch of maximum
    (HJD - 2450000).
    """
    _check(field, vartype)
    rel = f"ogle4/OCVS/{field}/{vartype}/{subtype}.dat"
    path = _fetch(rel, refresh=refresh)
    t = Table.read(path, format="ascii.no_header")
    t.rename_column(t.colnames[0], "id")
    t.meta["readme"] = f"{DATA_ROOT}/ogle4/OCVS/{field}/{vartype}/README"
    t.meta["source"] = f"{DATA_ROOT}/{rel}"
    t.meta["note"] = "Column meanings are class-specific; consult the README before use."
    return t


def ocvs_photometry(star_id: str, band: str = "I", *, refresh: bool = False) -> Table:
    """Return the light curve of one OCVS star, e.g. ``"OGLE-BLG-RRLYR-00001"``.

    ``band`` is ``"I"`` or ``"V"``; V-band coverage is far sparser and many stars have none.
    Columns: ``hjd`` (converted here to full HJD from the stored HJD - 2450000), ``mag``,
    ``mag_err``.
    """
    field, vartype = _parse_id(star_id)
    rel = f"ogle4/OCVS/{field}/{vartype}/phot/{band}/{star_id}.dat"
    path = _fetch(rel, refresh=refresh)
    t = Table.read(path, format="ascii.no_header", names=["hjd", "mag", "mag_err"])
    # Stored as HJD - 2450000; normalise so callers never have to remember the offset.
    t["hjd"] += 2450000.0
    t["mag"].unit = u.mag
    t["mag_err"].unit = u.mag
    t.meta["id"] = star_id
    t.meta["band"] = f"{band} (OGLE)"
    t.meta["time_scale"] = "HJD (geocentric, UTC-based) -- not BJD_TDB"
    t.meta["source"] = f"{DATA_ROOT}/{rel}"
    return t


def ocvs_cone_search(field: str, vartype: str, coord: SkyCoord,
                     radius: u.Quantity = 1 * u.arcmin, *, refresh: bool = False) -> Table:
    """Return OCVS entries within ``radius`` of ``coord``, sorted by separation.

    OGLE fields are extremely crowded; a match within a few arcsec is not by itself an
    identification. Check the separation column against the astrometric precision of
    whatever catalog you are matching to.
    """
    cat = ocvs_catalog(field, vartype, refresh=refresh)
    sep = cat["coord"].separation(coord)
    out = cat[sep <= radius]
    out["separation"] = sep[sep <= radius].to(u.arcsec)
    out.sort("separation")
    return out


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def as_bjd_tdb(table: Table, coord: SkyCoord, site: str = "lco") -> Time:
    """Convert an OGLE HJD column to BJD_TDB at ``coord``.

    OGLE reports geocentric HJD on a UTC-based scale. Combining it with BJD_TDB from TESS,
    Kepler or Gaia without converting introduces an offset of order seconds to a minute --
    negligible for a 100-day microlensing event, fatal for an eclipse ephemeris propagated
    over a decade. Nothing in this module converts implicitly; call this when you need it.

    OGLE observes from Las Campanas, so ``site="lco"`` is the correct default.
    """
    from astropy.coordinates import EarthLocation

    t = Time(np.asarray(table["hjd"]), format="jd", scale="utc",
             location=EarthLocation.of_site(site))
    # Undo the heliocentric light-time correction, then apply the barycentric one.
    ltt_helio = t.light_travel_time(coord, kind="heliocentric")
    ltt_bary = t.light_travel_time(coord, kind="barycentric")
    return (t - ltt_helio + ltt_bary).tdb


def ocvs_available(field: str, *, refresh: bool = False) -> list[str]:
    """List the variability classes actually present for a field."""
    import re
    url = f"{DATA_ROOT}/ogle4/OCVS/{field}/"
    with urllib.request.urlopen(url, timeout=60) as r:
        html = r.read().decode(errors="replace")
    return sorted({m for m in re.findall(r'href="([a-z_0-9]+)/"', html)})


def _check(field: str, vartype: str) -> None:
    if field not in FIELDS:
        raise ValueError(f"unknown field {field!r}; expected one of {FIELDS}")
    if vartype not in VAR_TYPES:
        raise ValueError(f"unknown variability class {vartype!r}; expected one of {VAR_TYPES}")


def _parse_id(star_id: str) -> tuple[str, str]:
    """Map ``OGLE-BLG-RRLYR-00001`` to its ``(field, vartype)`` directory pair."""
    parts = star_id.split("-")
    if len(parts) < 4 or parts[0] != "OGLE":
        raise ValueError(f"unrecognised OCVS identifier: {star_id!r}")
    field = parts[1].lower()
    vartype = parts[2].lower()
    aliases = {"rrlyr": "rrlyr", "cep": "cep", "t2cep": "t2cep", "acep": "acep",
               "ecl": "ecl", "lpv": "lpv", "dsct": "dsct", "dpv": "dpv"}
    return field, aliases.get(vartype, vartype)


def write_manifest(directory: Path, *, query: str, source: str, nfiles: int,
                   notes: str = "") -> Path:
    """Write the MANIFEST.md this project requires beside every raw download."""
    from datetime import date

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "MANIFEST.md"
    path.write_text(
        f"# OGLE retrieval\n\n"
        f"| | |\n|---|---|\n"
        f"| Archive | OGLE, Warsaw University Observatory |\n"
        f"| Source | {source} |\n"
        f"| Query | `{query}` |\n"
        f"| Retrieved | {date.today().isoformat()} |\n"
        f"| Files | {nfiles} |\n"
        f"| Data rights | Public |\n\n"
        f"Times are HJD (geocentric, UTC-based), **not** BJD_TDB. Magnitudes are OGLE I/V.\n\n"
        f"{notes}\n\n**Acknowledgement:** {ACKNOWLEDGEMENT}\n"
    )
    return path
