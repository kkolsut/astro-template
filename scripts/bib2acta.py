#!/usr/bin/env python3
"""Convert a BibTeX file into an Acta Astronomica ``references`` environment.

Acta does not use BibTeX. Its class defines

    \\refitem{Authors}{Year}{Journal}{Volume}{Page}

and a tilde in any of the last three fields means "this entry has no such
field" -- which is how books, theses and preprints are written. ``lit-scout``
produces BibTeX, so this is the glue between the two.

    uv run python scripts/bib2acta.py docs/lit/refs.bib -o paper/references.tex

Entries are sorted the way the journal wants them: alphabetically by first
author surname, then by year. Anything the converter cannot resolve is
reported on stderr and emitted with a ``% FIXME`` marker rather than silently
guessed at -- a reference list is checked by a human, and a wrong volume
number is worse than a visible gap.

Note on encoding: acta.cls loads ``inputenc`` with ``latin2``, so a UTF-8
source file will not compile. Non-ASCII characters are converted to LaTeX
accent commands on the way out.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

# Journal macros defined inside acta.cls's `references` environment. Keys are
# matched case-insensitively against the BibTeX `journal` field after
# punctuation and spaces are stripped.
JOURNAL_MACROS = {
    "aap": r"\AA",
    "astronomyandastrophysics": r"\AA",
    "aa": r"\AA",
    "aaps": r"\AAS",
    "aapssupplementseries": r"\AAS",
    "apj": r"\ApJ",
    "astrophysicaljournal": r"\ApJ",
    "apjl": r"\ApJ",
    "apjletters": r"\ApJ",
    "apjs": r"\ApJS",
    "astrophysicaljournalsupplementseries": r"\ApJS",
    "aj": r"\AJ",
    "astronomicaljournal": r"\AJ",
    "ibvs": r"\IBVS",
    "pasp": r"\PASP",
    "actaastron": r"\Acta",
    "actaastronomica": r"\Acta",
    "mnras": r"\MNRAS",
    "monthlynoticesoftheroyalastronomicalsociety": r"\MNRAS",
    "an": r"\AN",
    "astronnachr": r"\AN",
    "astronomischenachrichten": r"\AN",
    "physrev": r"\PR",
    "physicalreview": r"\PR",
}

# ADS exports journal names as its own macros (\aap, \actaa, ...) rather than
# as text. Map the common ones onto the class's macros, or onto plain text
# where acta.cls has no equivalent.
ADS_JOURNAL_MACROS = {
    r"\aap": r"\AA",
    r"\aaps": r"\AAS",
    r"\apj": r"\ApJ",
    r"\apjl": r"\ApJ",
    r"\apjs": r"\ApJS",
    r"\aj": r"\AJ",
    r"\actaa": r"\Acta",
    r"\mnras": r"\MNRAS",
    r"\pasp": r"\PASP",
    r"\an": r"\AN",
    r"\nat": "Nature",
    r"\science": "Science",
    r"\apss": "Astrophys.\\ Space Sci.",
    r"\araa": "ARA\\&A",
    r"\pasj": "PASJ",
    r"\jcap": "JCAP",
    r"\prd": "Phys.\\ Rev.\\ D",
    r"\prl": "Phys.\\ Rev.\\ Lett.",
}

# Author strings that are institutions, not people, and must not be turned
# into "Surname, I." ADS emits several of these.
CORPORATE_AUTHOR = re.compile(
    r"\b(collaboration|consortium|team|survey|observatory|project)\b", re.I
)

# Entry types that legitimately have no journal/volume/page triple.
NON_ARTICLE_TYPES = {"book", "inbook", "incollection", "phdthesis",
                     "mastersthesis", "techreport", "misc", "unpublished",
                     "proceedings", "inproceedings"}

# Non-ASCII characters to LaTeX, since the class is stuck on latin2.
ACCENT_COMMANDS = {
    "\u0301": "'",   # acute
    "\u0300": "`",   # grave
    "\u0302": "^",   # circumflex
    "\u0308": '"',   # diaeresis
    "\u0303": "~",   # tilde
    "\u0304": "=",   # macron
    "\u0306": "u",   # breve
    "\u0307": ".",   # dot above
    "\u030c": "v",   # caron
    "\u030a": "r",   # ring above
    "\u0327": "c",   # cedilla
    "\u0328": "k",   # ogonek
}
LITERAL_REPLACEMENTS = {
    "\u0142": r"\l{}",    # l with stroke -- no combining form
    "\u0141": r"\L{}",
    "\u00f8": r"\o{}",
    "\u00d8": r"\O{}",
    "\u00e5": r"\aa{}",
    "\u00c5": r"\AA{}",   # note: inside `references` \AA is the A&A macro
    "\u00df": r"\ss{}",
    "\u00e6": r"\ae{}",
    "\u00c6": r"\AE{}",
    "\u2013": "--",
    "\u2014": "---",
    "\u2018": "`",
    "\u2019": "'",
    "\u201c": "``",
    "\u201d": "''",
    "\u00a0": "~",
}


def to_latex_ascii(text: str) -> str:
    """Render a UTF-8 string as pure ASCII LaTeX."""
    out = []
    for char in text:
        if char in LITERAL_REPLACEMENTS:
            out.append(LITERAL_REPLACEMENTS[char])
            continue
        if ord(char) < 128:
            out.append(char)
            continue
        decomposed = unicodedata.normalize("NFD", char)
        if len(decomposed) == 2 and decomposed[1] in ACCENT_COMMANDS:
            base, accent = decomposed[0], ACCENT_COMMANDS[decomposed[1]]
            # \'n needs no braces; \v{c} and friends do.
            if accent.isalpha():
                out.append(f"\\{accent}{{{base}}}")
            else:
                out.append(f"\\{accent}{{{base}}}")
            continue
        out.append(unicodedata.normalize("NFKD", char).encode("ascii", "ignore").decode())
    return "".join(out)


def strip_braces(value: str) -> str:
    """Drop the braces BibTeX uses to protect capitalisation.

    Accent commands keep theirs: {\\'n} must stay braced or \\'nski
    changes meaning. Everything else ({VLT}, {Szyma...}) is unwrapped,
    repeatedly, since ADS nests them.
    """
    value = " ".join(value.split())
    out, i, n = [], 0, len(value)
    while i < n:
        if value[i] != "{":
            out.append(value[i])
            i += 1
            continue
        end = _match_brace(value, i)
        inner = value[i + 1:end - 1]
        if inner.lstrip().startswith("\\"):
            out.append(value[i:end])          # {\'n}, {\L} -- braces are load-bearing
        else:
            out.append(strip_braces(inner))   # {Szyma{\'n}ski} -- protective only
        i = end
    return "".join(out).strip()


def _match_brace(text: str, start: int) -> int:
    """Index just past the '}' matching the '{' at `start`."""
    depth, i = 0, start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def _split_fields(body: str) -> dict:
    """Scan `key = value` pairs, tracking brace depth by hand.

    A regex cannot do this: ADS nests braces arbitrarily deep
    ({Szyma{\\'n}ski}) and wraps author lists across lines.
    """
    fields, i, n = {}, 0, len(body)
    while i < n:
        match = re.compile(r"\s*(\w+)\s*=\s*").match(body, i)
        if not match:
            # Skip to the next comma that could start a field.
            nxt = body.find(",", i)
            if nxt == -1:
                break
            i = nxt + 1
            continue
        key, i = match.group(1).lower(), match.end()
        if i < n and body[i] == "{":
            end = _match_brace(body, i)
            raw, i = body[i + 1:end - 1], end
        elif i < n and body[i] == '"':
            end = body.find('"', i + 1)
            end = n if end == -1 else end
            raw, i = body[i + 1:end], end + 1
        else:
            end = body.find(",", i)
            end = n if end == -1 else end
            raw, i = body[i:end], end
        fields[key] = strip_braces(raw)
        nxt = body.find(",", i)
        i = n if nxt == -1 else nxt + 1
    return fields


def parse_bibtex(text: str) -> list[dict]:
    """A small BibTeX reader: enough for what ADS exports, no dependencies."""
    entries = []
    for match in re.finditer(r"@(\w+)\s*\{\s*([^,\s]*)\s*,", text):
        kind = match.group(1).lower()
        if kind in {"string", "comment", "preamble"}:
            continue
        opening = text.index("{", match.start())
        body = text[match.end():_match_brace(text, opening) - 1]
        fields = {"__type__": kind, "__key__": match.group(2)}
        fields.update(_split_fields(body))
        entries.append(fields)
    return entries


def split_authors(raw: str) -> list[str]:
    return [a.strip() for a in re.split(r"\s+and\s+", raw) if a.strip()]


PARTICLES = {"van", "von", "de", "der", "den", "del", "di", "da", "la", "le", "ten", "ter"}


def _initial_of(token: str) -> str:
    r"""First letter of a name token, as LaTeX.

    Polish and Scandinavian given names start with a letter that only exists
    as a command -- {\L}ukasz, {\O}ystein -- and dropping it loses the
    initial entirely, which is how Wyrzykowski, {\L}. becomes Wyrzykowski.
    """
    token = token.strip()
    special = re.match(r"\{?\\([a-zA-Z]+)\}?", token)
    if special:
        return f"\\{special.group(1)}{{}}"
    accented = re.match(r"\{?\\(.)\{?([a-zA-Z])\}?\}?", token)
    if accented:
        return f"\\{accented.group(1)}{{{accented.group(2).upper()}}}"
    cleaned = re.sub(r"[{}\\]", "", token)
    return cleaned[0].upper() if cleaned else ""


def format_one_author(name: str) -> tuple[str, str]:
    """Return (formatted 'Surname, I.I.', sort key) for one BibTeX name."""
    name = strip_braces(name)
    if CORPORATE_AUTHOR.search(name):
        # "Gaia Collaboration" is not a person; print it as it stands.
        return name, name.lower()
    if "," in name:
        surname, given = [p.strip() for p in name.split(",", 1)]
    else:
        # "R. P. van der Marel" -- the surname starts at the first particle,
        # otherwise it is the last token.
        parts = name.split()
        if len(parts) > 1:
            starts = [i for i, p in enumerate(parts) if p.lower() in PARTICLES]
            cut = starts[0] if starts else len(parts) - 1
            surname, given = " ".join(parts[cut:]), " ".join(parts[:cut])
        else:
            surname, given = name, ""
    # ADS ties initials with ~ ("M.~K."), so split on that too.
    initials = ""
    for token in re.split(r"[\s.~]+", given):
        if not token:
            continue
        if token.lower() in PARTICLES:
            surname = f"{token} {surname}"
            continue
        # Keep hyphenated given names as J.-M.
        initials += "-".join(
            f"{i}." for i in (_initial_of(p) for p in token.split("-")) if i
        )
    formatted = f"{surname}, {initials}" if initials else surname
    # Sort on the surname with accents and particles removed.
    key = re.sub(r"\\[a-zA-Z]+|[{}\\'`^\"~.]", "", surname).strip().lower()
    key = " ".join(w for w in key.split() if w not in PARTICLES) or key
    return formatted, key


def format_authors(raw: str) -> tuple[str, str]:
    """Acta style: 'Surname, I., Surname, I., and Surname, I.'"""
    names = [format_one_author(n) for n in split_authors(raw)]
    if not names:
        return "", ""
    sort_key = names[0][1]
    formatted = [n[0] for n in names]
    if len(formatted) == 1:
        return formatted[0], sort_key
    if len(formatted) == 2:
        return f"{formatted[0]}, and {formatted[1]}", sort_key
    return ", ".join(formatted[:-1]) + f", and {formatted[-1]}", sort_key


def journal_field(entry: dict, warn) -> str:
    raw = (entry.get("journal") or entry.get("journaltitle") or "").strip()
    if raw.startswith("\\"):
        macro = raw.split()[0].rstrip("{}")
        if macro in ADS_JOURNAL_MACROS:
            return ADS_JOURNAL_MACROS[macro]
        warn(entry, f"unrecognised ADS journal macro {macro}")
        return "~"
    if raw:
        key = re.sub(r"[^a-z]", "", raw.lower())
        return JOURNAL_MACROS.get(key, to_latex_ascii(raw))

    # No journal. A book or thesis puts the publisher or school here, which is
    # what the printed volumes do; a preprint gets its arXiv identifier.
    for field in ("publisher", "school", "institution", "booktitle", "howpublished"):
        if entry.get(field):
            return to_latex_ascii(entry[field])
    if entry.get("eprint"):
        prefix = entry.get("archiveprefix", "arXiv") or "arXiv"
        return f"{to_latex_ascii(prefix)}:{to_latex_ascii(entry['eprint'])}"
    warn(entry, "no journal, publisher or eprint")
    return "~"


def page_field(entry: dict) -> str:
    pages = entry.get("pages") or entry.get("eid") or ""
    if not pages:
        return "~"
    # Acta prints the first page only.
    return to_latex_ascii(re.split(r"-{1,3}|\u2013", pages)[0].strip())


def entry_to_refitem(entry: dict, warn) -> str:
    authors, sort_key = format_authors(entry.get("author") or entry.get("editor", ""))
    if not authors:
        warn(entry, "no author or editor")
        authors = "~"
    year = entry.get("year", "")
    if not year:
        warn(entry, "no year")
        year = "~"
    return (
        f"\\refitem{{{to_latex_ascii(authors)}}}{{{to_latex_ascii(year)}}}"
        f"{{{journal_field(entry, warn)}}}"
        f"{{{to_latex_ascii(entry.get('volume', '')) or '~'}}}"
        f"{{{page_field(entry)}}}"
    ), sort_key, year


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bibfile", type=Path, help="BibTeX input, e.g. docs/lit/refs.bib")
    ap.add_argument("-o", "--output", type=Path,
                    help="write here instead of stdout, e.g. paper/references.tex")
    ap.add_argument("--keys", nargs="*", metavar="KEY",
                    help="emit only these citation keys (default: all)")
    args = ap.parse_args()

    problems: list[str] = []

    def warn(entry, message):
        problems.append(f"  {entry['__key__']}: {message}")

    entries = parse_bibtex(args.bibfile.read_text(encoding="utf-8"))
    if args.keys:
        wanted = set(args.keys)
        entries = [e for e in entries if e["__key__"] in wanted]
        for missing in sorted(wanted - {e["__key__"] for e in entries}):
            print(f"warning: key not in {args.bibfile}: {missing}", file=sys.stderr)
    if not entries:
        print(f"error: no usable entries in {args.bibfile}", file=sys.stderr)
        return 1

    rendered = []
    for entry in entries:
        before = len(problems)
        line, sort_key, year = entry_to_refitem(entry, warn)
        if len(problems) > before:
            line = f"% FIXME -- check this entry against the paper itself\n{line}"
        rendered.append((sort_key, year, entry["__key__"], line))
    rendered.sort(key=lambda r: (r[0], r[1], r[2]))

    body = "\n".join(line for *_, line in rendered)
    text = (
        f"%% Generated by scripts/bib2acta.py from {args.bibfile} -- do not edit.\n"
        f"%% Edit the .bib and regenerate. Entries marked FIXME need a human.\n"
        "\\begin{references}\n"
        f"{body}\n"
        "\\end{references}\n"
    )

    if args.output:
        args.output.write_text(text, encoding="ascii")
        print(f"wrote {len(rendered)} references to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)

    if problems:
        print(f"\n{len(problems)} entries need checking:", file=sys.stderr)
        print("\n".join(problems), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
