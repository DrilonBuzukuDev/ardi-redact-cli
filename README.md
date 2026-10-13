# ardi-redact-cli

Redact direct personal information locally from Word documents, Markdown, plain
text, and SRT/VTT subtitles. Python 3.12+, uv, and a spaCy model are required.
The installed command is **`ardi-redact`**; the repository and distribution are
**`ardi-redact-cli`**.

## Install from GitHub

Replace `USERNAME` with the repository owner:

```bash
uv tool install git+https://github.com/USERNAME/ardi-redact-cli.git
ardi-redact --install-model
ardi-redact --help
```

The second command installs `en_core_web_sm` into the tool's Python environment
using `uv pip`. Installation downloads dependencies/models; redaction itself
uses no network or external API. Models are explicit downloads so installation
does not silently contact GitHub during document processing.

## Usage

```bash
ardi-redact file.docx
ardi-redact notes.md
ardi-redact interview.vtt
ardi-redact subtitles.srt
ardi-redact notes.txt
ardi-redact ./documents --recursive
ardi-redact file.txt --dry-run
ardi-redact file.txt --model en_core_web_sm
ardi-redact file.txt --phone-region AT
ardi-redact file.txt --organizations
ardi-redact file.txt --overwrite
```

Outputs are adjacent to inputs: `filename.ext` → `filename_pii.ext`. Originals
are never overwritten. Existing outputs are rejected unless `--overwrite` is
set. Outputs are published atomically; partial files are cleaned up on failure.
Symlink inputs/outputs and outputs pointing to the original are rejected.
Directory processing skips generated `*_pii` files and unsupported formats;
without `--recursive`, only the immediate directory is scanned. A failed file
does not prevent processing the remaining files; the command exits with status 1
if any file fails. `--dry-run` reports counts without writing anything.

### Languages

| Language | Alias | Small model |
| --- | --- | --- |
| English (default) | `en` | `en_core_web_sm` |
| German | `de` | `de_core_news_sm` |
| Spanish | `es` | `es_core_news_sm` |
| French | `fr` | `fr_core_news_sm` |
| Italian | `it` | `it_core_news_sm` |

```bash
ardi-redact --install-model --model de
ardi-redact transcript.docx --model de --phone-region DE
```

Each model is installed separately. The installer uses version 3.8.0 of these
pipelines, compatible with the required spaCy 3.8 series. `--model` also accepts
an already installed compatible spaCy model or a local pipeline directory.
`--phone-region` defaults to `AT` and controls interpretation of national phone
numbers independently of the model language. International numbers are detected
using their country code.

### Detection and placeholders

| Category | Detection |
| --- | --- |
| `PERSON` | spaCy `PERSON` / multilingual `PER` |
| `LOCATION` | spaCy `GPE`, `LOC`, `FAC` |
| `EMAIL` | spaCy `token.like_email` |
| `PHONE` | phonenumbers valid-number matching |
| `GPS` | Decimal latitude/longitude pairs, comma or semicolon separated; validated to ±90/±180 |
| `DATE` | spaCy `DATE`, enabled by default |
| `ORG` | spaCy `ORG`, only with `--organizations` |

```text
John Smith lives in Vienna.
Email: john@example.com
```

becomes:

```text
[PERSON_1] lives in [LOCATION_1].
Email: [EMAIL_1]
```

Placeholders are consistent within each file across paragraphs, tables, headers,
footers, and cues. Values are matched ignoring case and repeated whitespace;
phone punctuation is ignored. Numbering restarts for each file, except existing
placeholder numbers are reserved to avoid collisions. Counts report redacted
occurrences, not unique values. Structured email/GPS/phone matches take priority
over overlapping NER matches; remaining ties prefer longer spans.

Only the listed categories are detected. Addresses, identifiers, usernames,
financial information, and other sensitive content have no dedicated detector.
NER is statistical: it can miss names/locations/dates or classify ordinary words
as entities. Multilingual models have different entity inventories (some do not
include `DATE`). GPS supports decimal degrees, not DMS or arbitrary integer pairs.
Review redacted documents before sharing them.

## Format behavior

- **TXT:** UTF-8 (optional BOM) and BOM-marked UTF-16; preserve original line
  endings and all text outside detected spans.
- **Markdown:** retain headings, emphasis delimiters, links, inline code, and
  fenced blocks. Text inside code and link labels/destinations is scanned. A
  placeholder inside a URL changes that URL; the surrounding Markdown syntax
  remains. Markdown uses a lightweight syntax projection, not a full CommonMark
  parser; complex HTML and extensions can reduce detection accuracy.
- **SRT/VTT:** scan cue text together across lines; retain identifiers,
  timestamps, cue settings, line endings, markup tags, and blank separators.
  VTT header/NOTE/STYLE/REGION metadata is preserved and excluded, with a warning.
  Subtitle tags and attributes are structural and not scanned. Malformed cues
  fail instead of being silently skipped.
- **DOCX:** use python-docx to validate the document, then edit Word XML text
  nodes while retaining runs, tables (including nested tables), hyperlinks,
  headers, footers, and untouched package members. Entities can span multiple
  runs. A placeholder inherits the first affected run's formatting; subsequent
  affected runs retain their formatting but lose the entity's characters.
  Line breaks and tabs stay in place. Warnings identify unscanned text boxes,
  comments, footnotes/endnotes, deleted tracked changes, field instructions,
  hyperlink targets, images, embedded objects, and metadata. These parts may
  still contain PII. DOCX package metadata is not scrubbed.

  Imported alternative-format DOCX content (`altChunk`) is also preserved with
  a warning and is not scanned.

Redaction preserves structural formatting; replacing long text with placeholders
can change visual wrapping and pagination. Whitespace inside a matched value may
be removed, while structural line breaks remain. The tool never prints source
text, detector values, or tracebacks. Source filenames are shown for progress,
so avoid PII in filenames when capturing terminal output. Only redacted outputs
are persisted; temporary output files have private permissions. Unscanned content
in preserved document parts remains in outputs as described above.

## Development

```bash
uv sync
uv run ardi-redact --install-model
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv build
```

Pyright uses strict checking. Tests use a deterministic spaCy EntityRuler so the
core test suite needs no model downloads. A real English-model integration test
also runs when that model is installed and is otherwise skipped. No CI workflows
are included.

`uv sync` removes packages absent from the lockfile, including manually installed
models. Reinstall a model afterward, or use `uv sync --inexact` to retain it.

The package separates detection (`detection.py`), placeholder assignment and
offset mapping (`redaction.py`), file adapters (`formats.py`), atomic processing
(`processing.py`), model management (`models.py`), and the CLI (`cli.py`).

MIT licensed. Model distributions have their own licenses; consult the
[spaCy model catalog](https://spacy.io/models) and
[installation documentation](https://spacy.io/usage/models/).
