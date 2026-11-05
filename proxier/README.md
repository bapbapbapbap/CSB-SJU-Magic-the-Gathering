# mtg-proxier

Decklist in, printable PDF out. Reads a CSV or plain-text decklist, looks every card up on [Scryfall](https://scryfall.com), and lays the card images out 3×3 at real card size (63 × 88 mm) with cut marks, ready to print, cut, and sleeve in front of a basic land.

**Windows** (PowerShell or cmd, in this folder):

```
.\proxy.bat my-deck.csv
```

On first run it sets up its own Python environment and installs everything. It only needs Python itself, from [python.org](https://www.python.org/downloads/): tick "Add python.exe to PATH" in the installer.

**macOS / Linux:**

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python mtg_proxier.py my-deck.csv
```

That writes `my-deck.pdf` next to the list. **Print at 100% / "Actual size"**, not "Fit to page", or the cards come out small.

## Input

**CSV** with a header row. Columns are matched by name, in any order, and anything unrecognized is ignored, so exports from deckbuilders work as they are:

| What | Column names it recognizes |
|---|---|
| Card name (required) | `Name`, `Card Name`, `Card` |
| Quantity | `Quantity`, `Qty`, `Count`, `Amount` |
| Exact printing | `Scryfall ID` (best), or `Set` / `Set Code` / `Edition Code` / `Edition` + `Collector Number` |
| Category | `Category`, `Categories`, `Board` |

- **Archidekt**: in the export dialog, tick *Exclude maybeboard(s)*, choose CSV, enable at least *Quantity*, *Name* and *Scryfall ID*, and keep *Include header line* checked. The Scryfall ID pins the exact printing you picked.
- **Moxfield**, **ManaBox**, **Deckbox**: their CSV exports work too. A set *name* in an `Edition` column (Deckbox) is ignored, and the card is looked up by name.
- No header? `qty,name[,set,collector_number]` or one name per line works too.

**Plain text** (`.txt`, or anything that isn't `.csv`/`.tsv`) in the usual decklist formats:

```
Commander
1 Atraxa, Praetors' Voice
1x Sol Ring
1 Command Tower (CMM) 1032
SB: 1 Swords to Plowshares
```

## Options

| Flag | Does |
|---|---|
| `--skip-basics` | Leaves out basic lands: Plains, Island, Swamp, Mountain, Forest, Wastes, and snow basics. It checks the name first, so basics are never sent to the API, then checks each card's Scryfall type line to catch anything listed under another name. Dryad Arbor and other nonbasic Forests still print. |
| `--exclude-category NAME` | Drops rows in that Archidekt category or Moxfield board. Repeatable. Default: `Maybeboard`. `--exclude-category none` prints everything. |
| `--no-backs` | Prints only the front of double-faced cards. Default is front and back as separate cards. |
| `--no-fuzzy` | Turns off typo correction. By default, a name that doesn't match exactly is retried with Scryfall's fuzzy search, and every correction is printed (`corrected (line 12): 'Swords to Plow' -> Swords to Plowshares`). It completes partial or missing words; it won't fix swapped letters so you can check it. Printings pinned by Scryfall ID or by set + collector number are never guessed. |
| `--page letter\|a4` | Paper size (default `letter`). |
| `--gap MM` | Space between cards. The default, 0, means neighbors share a cut line, so a sheet takes 4 + 4 cuts. |
| `--card-height MM` | Fine-tune if your printer scales. Width follows at 63:88. |
| `--image png\|large\|normal` | Scryfall image size. `png` (745×1040) is the sharpest. |
| `--corner-fill black\|white\|#hex` | Color behind the rounded corners of the image. |
| `--dry-run` | Look everything up and list what would print, without downloading images or writing a PDF. |

Any card that still can't be found is listed with its line number. The PDF still gets made, and the exit code is 1.

**Typical Commander run:** `python mtg_proxier.py deck.csv --skip-basics`

## Being a good Scryfall citizen

Scryfall's API is free, and the tool follows their rules for using it:

- Sends a real `User-Agent` (`mtg-proxier/<version>`) and an `Accept` header, which are required.
- Looks cards up with `/cards/collection`, 75 at a time, no faster than 2 requests a second, and backs off on `429`.
- Caches images for 24 hours (in `~/.cache/mtg-proxier`), so reprinting a deck doesn't hit the network again.
- Prints card images **unaltered**: no cropping, stretching, recoloring, or watermarks, so the artist credit and copyright line stay on every card.

## Proxies, not counterfeits

These are playtest cards for personal, non-commercial play: testing a deck before you buy into it, or loaning a deck to a new player. Every page is footed *"Playtest cards. Not for sale."* Don't sell them, and don't pass them off as real cards. Card images are © Wizards of the Coast. This project is unofficial Fan Content and isn't approved or endorsed by Wizards of the Coast or by Scryfall.

## What's written into the PDF

Every PDF credits each owner for what's theirs. You can see this in any PDF viewer's document properties, and in Acrobat's copyright panel:

| Field | Says |
|---|---|
| Rights (`/Rights`, XMP `dc:rights`) | Card images, text and names are © Wizards of the Coast LLC. Unofficial Fan Content, not endorsed by Wizards. Not covered by this software's license. |
| Rights owner (XMP `xmpRights:Owner`) | Wizards of the Coast LLC, linked to their [Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy) |
| Source (`/Source`, XMP `dc:source`) | Images and card data came from Scryfall. Not produced by, endorsed by, or affiliated with Scryfall. |
| Generator (`/Generator`, `Creator`) | Made with mtg-proxier, with a link to this repo. The GPL covers the software only, not the PDF or the cards in it. |
| Subject | Playtest cards for personal, non-commercial use. Not for sale. |

The GPL is never stated as the license of the PDF itself. The PDF is mostly Wizards' card art, and that was never ours to license.

## License

The code is [GPL-3.0-or-later](../LICENSES/GPL-3.0-or-later.txt). You can fork it, change it, and ship it, but anything you distribute that's built on it has to be GPL too, with source available. Card images aren't part of this repo: they're downloaded at run time and stay © Wizards of the Coast.

## Testing against the live API

`tests/crash-test.txt` is a deck built to hit every case: split, adventure, transform and modal double-faced cards, basics and snow basics, Dryad Arbor, a partial name, and a card that doesn't exist. The full step-by-step procedure, with the expected output for each run, is in [`llms.txt`](../llms.txt) at the repo root. It's written so an LLM can walk anyone through it, and it reads fine for a person too.

## Tests

```
pip install pytest
pytest tests
```

The tests run against a fake Scryfall, so they need no network access.
