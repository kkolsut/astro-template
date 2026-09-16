# Acta Astronomica house style

Source: <https://acta.astrouw.edu.pl/acta/MISC/Acta_Style/>. `acta.cls` and
`acta-template.tex` were downloaded from there and `acta.cls` is **never
edited** — it is the journal's file, and a patched copy is the first thing an
editor notices. Local fixes go in `compat/`.

## Building

```bash
cd paper
make check     # what the system is missing
make           # two pdflatex passes -> ms.pdf
```

`make` is plain `pdflatex`, twice. There is no BibTeX step — see References.

### Packages

`make check` reports required and optional separately. The class is from 2008
and Fedora ships texlive in small pieces, so a fresh machine is missing
several:

```bash
sudo dnf install texlive-amsmath texlive-amsfonts texlive-supertabular \
                 texlive-times texlive-helvetic     # required
sudo dnf install texlive-courier                    # optional, see below
```

Without `texlive-times` the build falls back to Latin Modern and says so
loudly. It compiles, but the line breaking and page count are not the
journal's — fine for reading a draft, never for a proof.

Courier is optional and cosmetic: `pslatex` narrowed Courier to 85% for
typewriter text, and without the metrics `\texttt` stays Computer Modern.
Visible wherever the text sets a filename or a keyword, harmless otherwise.

### What `compat/` is for

Two things no current package provides, so they cannot be installed:

- **`pslatex.sty`** — the last line of `acta.cls` loads `pslatex`, a package
  declared obsolete and removed from TeX Live. The shim loads `mathptmx` +
  `helvet` instead, which is what `pslatex` selected, and falls back to Latin
  Modern with a warning when the Times metrics are absent.
- **`pcrbo.tfm`** — the class does `\font\ttit=pcrbo at 8pt` at load time, so a
  missing Courier-BoldOblique metric is fatal before the document even starts.
  The file here is `cmitt10.tfm` under another name. It only affects
  `\TableFontIt`, which nothing uses by default.

`TEXINPUTS` and `TEXFONTS` in the `Makefile` put `compat/` on the search path,
**last** — the empty element in `.::compat` is kpathsea's own default path, so
a real file always beats a stand-in. Install `texlive-courier` and the genuine
`pcrbo` metric takes over with no change here.

Two path facts that cost an afternoon each:

- `TEXFONTS` is separate from `TEXINPUTS`. A `.tfm` is not found via the
  latter, so adding `compat/` to `TEXINPUTS` alone leaves the class failing on
  `pcrbo`.
- The shim decides between Times and Latin Modern with `\IfFileExists`, which
  also only searches `TEXINPUTS` — so it can never see a `.tfm` by itself, and
  silently chose Latin Modern on a machine that had Times installed. The
  `Makefile` resolves the font directories with `kpsewhich` and adds them, so
  the probes mean something. **Running `pdflatex` by hand, outside `make`,
  falls back to Latin Modern.** Use `make`.

## Structure

- Papers are divided into numbered Chapters (`\section`), which may have
  numbered Paragraphs (`\subsection`, e.g. 2.3). Each gets a short descriptive
  title. Short notes and *Letters* are not divided.
- The paper opens with an abstract stating the principal conclusion.
- Key words come from the common list shared by the major journals.

## Title page

```latex
\SetPages{0}{0}          % first and last page in the volume; editor assigns
\SetVol{76}{2026}        % volume and year
\begin{Titlepage}
\Title{Title of the Paper}
\Author{S~u~r~n~a~m~e, I.N.}{Affiliation\\e-mail: ...}
\Received{Month Day, Year}
\end{Titlepage}
\Abstract{...}{key words}
```

Surnames are letterspaced with `~` between letters; initials follow, unspaced.
Several authors at one affiliation share a single `\Author`; several
affiliations are numbered with `$^1$`, `$^N$` superscripts.

## Figures

```latex
\begin{figure}[htb]
\centering
\includegraphics[width=12cm]{figures/name.pdf}
\FigCap{Caption.}
\label{fig:name}
\end{figure}
```

`\FigCap` is what steps the figure counter, so **`\label` must come after it**
— before it, the reference points at the previous figure and nothing warns you.

The class's `\Figure{height}{caption}` form reserves blank space for a figure
pasted in later; prefer `\includegraphics`.

Text width is 12.5 cm — size figures to that and do not scale them afterwards,
or the fonts inside no longer match the body. Everything under `figures/` is
produced by something in `scripts/`; see the `figure-smith` agent.

## Tables

```latex
\MakeTable{lcc}{12.5cm}{Caption.}{\hline
Quantity & Value & Unit\\
\hline
$P$ & $1.2345 \pm 0.0007$ & d\\
\hline}
```

Second argument is the caption's width, not the table's. Tables are set in
LaTeX, never pasted as images. `\MakeTableSep` puts one on its own page;
`supertabular` handles one that runs over a page.

## References

**Acta does not use BibTeX.** The reference list is a `references` environment
of `\refitem` entries:

```latex
\refitem{Authors}{Year}{Journal}{Volume}{Page}
```

- A `~` in any of the last three fields omits it — that is how books, theses
  and preprints are written.
- Authors read `Surname, I.N., Surname, I.N., and Surname, I.N.`
- Only the **first** page is given, not a range.
- The list is alphabetical by first author surname, then year.
- Journal macros defined by the class: `\AA \AAS \ApJ \ApJS \AJ \IBVS \PASP
  \Acta \MNRAS \AN \PR`. Anything else is written out.

Generate the list rather than typing it:

```bash
uv run python scripts/bib2acta.py docs/lit/refs.bib -o paper/references.tex
```

`lit-scout` maintains `docs/lit/refs.bib`; the converter handles the ADS export
format, maps ADS journal macros onto the class's, and flags anything it cannot
resolve with `% FIXME` instead of guessing. Entries with no BibTeX source can
be added to `references.tex` by hand, but then say so in a comment.

In-text citations are author–year in running text, with `\textit{et al.}`:
Udalski *et al.* (2015), or parenthetically (Udalski *et al.* 2015). There is
no `\cite` — every citation is typed, so every one has to be checked against
the reference list by hand. `paper-wright` does that check.

## Encoding

`acta.cls` loads `inputenc` with **latin2**, so a UTF-8 source file will not
compile. Write non-ASCII as LaTeX commands: `Szyma\'nski`, `Wyrzykowski, \L{}.`
`bib2acta.py` does this conversion on its output.

## Units and notation

Project-wide conventions in `../CLAUDE.md` still apply — explicit units,
explicit frames, explicit time systems, uncertainties on every value. In the
manuscript that means: state the time system the ephemeris is in, give the
confidence level of every limit, and say which magnitude system is meant.
