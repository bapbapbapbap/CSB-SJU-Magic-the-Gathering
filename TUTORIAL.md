# Tutorial: print a deck of proxies

This takes you from nothing to a sleeved, playable deck. No programming needed. The first time through takes about 20 minutes plus printing and cutting. After that, a new deck takes a couple of minutes.

You'll need:
- A computer. The steps are written for Windows, and [macOS / Linux](#macos-and-linux) is at the end.
- A printer, or a friend with one. All you have to send them is the PDF.
- Scissors or a paper trimmer, sleeves, and something to back the proxies with: bulk cards or basic lands.

---

## 1. Install Python (once)

1. Go to **[python.org/downloads](https://www.python.org/downloads/)** and click the big yellow download button.
2. Run the installer. On the first screen, **tick "Add python.exe to PATH"** at the bottom, *then* click Install Now.

> That checkbox is the one step people miss. If you forget it, run the installer again, choose **Modify**, and turn it on.

## 2. Download this project (once)

1. At the top of the [project page](https://github.com/bapbapbapbap/CSB-SJU-Magic-the-Gathering), click the green **Code** button, then **Download ZIP**.
2. Find the ZIP in your Downloads, right-click it, and choose **Extract All…**. You get a folder called `CSB-SJU-Magic-the-Gathering-main`.

> Know git? `git clone https://github.com/bapbapbapbap/CSB-SJU-Magic-the-Gathering` works too, and `git pull` gets updates later.

## 3. Open a terminal in the `proxier` folder

1. Open the extracted folder, then the **`proxier`** folder inside it.
2. Right-click an empty spot in the folder and choose **Open in Terminal**. On older Windows, hold **Shift**, right-click, and choose **Open PowerShell window here**.

A window opens with a prompt ending in `\proxier>`. Every command below goes in that window.

## 4. Print one of the club precons

There are five, all in the `decks` folder:

| Deck | Commander | Command |
|---|---|---|
| Strength in Numbers | Iroas, God of Victory | `.\proxy.bat ..\decks\precon-strength-in-numbers.txt --skip-basics` |
| Flashy flyers | Errant and Giada | `.\proxy.bat ..\decks\precon-flashy-flyers.csv --skip-basics` |
| Green is the new black | Davvol, Evincar of Rath | `.\proxy.bat ..\decks\precon-green-is-the-new-black.csv --skip-basics` |
| Greasy ass artifacts | Osgir, the Reconstructor | `.\proxy.bat ..\decks\precon-greasy-ass-artifacts.csv --skip-basics` |
| Kill the cat for the +1/+1 | Drizzt Do'Urden | `.\proxy.bat ..\decks\precon-kill-the-cat.csv --skip-basics` |

Copy one command, paste it into the terminal (right-click pastes), and press Enter.

**The first time**, you'll see `First run: setting up Python environment…` while it installs what it needs. That happens once. Then:

```
Looking up 73 unique lines (73 cards) on Scryfall...
Wrote ..\decks\precon-strength-in-numbers.pdf: 73 cards on 9 page(s).
  page 1 notes: Basic lands not included (27): 17 Plains, 10 Mountain
```

Downloading the images takes a few minutes the first time. Reprinting the same deck within a day is much faster, because images are kept for 24 hours.

The PDF lands **next to the decklist**, in the `decks` folder.

**What `--skip-basics` does:** basic lands aren't printed, because everyone has those. Page 1 of the PDF says how many of each to add, so the person holding the printout knows.

## 5. Print it at actual size

Open the PDF and print it. In the print dialog:

- Set **Scale** to **100%** or **Actual size**.
- **Turn off "Fit to page" / "Shrink to fit".** Most dialogs turn this on by default, and it makes every card come out small.
- Single-sided, color.

Sending it to a friend to print? Send the PDF and tell them **"100%, not fit to page"**.

**Check one card with a ruler before cutting the rest.** It should measure **63 × 88 mm (about 2½ × 3½ in)**, and lining it up on a real card should match. If yours comes out a little off, see [Cards print the wrong size](#cards-print-the-wrong-size).

## 6. Cut and sleeve

- Cut along the small tick marks in the margins. Neighboring cards share an edge, so each sheet takes **4 straight cuts down and 4 across**. A paper trimmer makes this quick.
- Sleeve each proxy **in front of** a bulk card or a basic land. The real card gives it the stiffness and thickness of a real card, so it shuffles normally.
- Double-faced cards print as two separate cards, front and back. Sleeve them back to back, or keep the back face beside you.

That's a deck. Go play.

---

## Proxy your own deck

### From Archidekt

Open your deck, then **Export** (in the deck's menu). Either kind works:

- **Text** with categories turned on. Copy it into a file named `mydeck.txt`. The tool reads the category tags, like `[Removal]`, and skips anything in Maybeboard or Sideboard.
- **CSV.** Tick **Exclude maybeboard(s)**, and make sure **Scryfall ID** is among the columns. That ID gets you the exact printing you chose. Keep **Include header line** checked.

Exporting several decks at once gives you a ZIP: extract it first. Then run:

```
.\proxy.bat C:\path\to\mydeck.csv --skip-basics
```

> Tip: type `.\proxy.bat ` (with the space), then drag the decklist file from File Explorer into the terminal window. It fills in the path for you.

To make PDFs for a whole folder of decks in one go:

```
Get-ChildItem C:\path\to\folder\*.csv | ForEach-Object { .\proxy.bat $_.FullName --skip-basics }
```

### From Moxfield, ManaBox, or anywhere else

CSV exports from Moxfield, ManaBox and Deckbox work as they are. So does a plain list:

```
1 Sol Ring
1 Command Tower
1x Swords to Plowshares
1 Arcane Signet [ELD]
```

Save it as a `.txt` file and run it the same way. If a name has a typo or is cut short, the tool asks Scryfall for the closest match and tells you what it changed (`corrected (line 12): 'Swords to Plow' -> Swords to Plowshares`). If it can't find a card at all, it says so, makes the PDF anyway, and lists the card on page 1.

### Useful options

| Add this | To |
|---|---|
| `--dry-run` | Check every card resolves, without downloading images or making a PDF. A good first step for a new list. |
| `--no-backs` | Print only the front of double-faced cards |
| `--no-ub` | Use non-Universes Beyond art wherever a non-UB printing exists |
| `--page a4` | Print on A4 paper instead of US Letter |
| `--gap 2` | Leave a 2 mm gap between cards, if you'd rather cut each card on its own |
| `--exclude-category none` | Print everything, Maybeboard and Sideboard included |

The full list is in the [proxier reference](proxier/README.md#options).

---

## When something goes wrong

| You see | Do this |
|---|---|
| `Python 3.9 or newer was not found` | Install Python ([step 1](#1-install-python-once)) with "Add python.exe to PATH" ticked, then close and reopen the terminal. |
| `proxy.bat is not recognized` | Type `.\proxy.bat`, with the `.\` in front. PowerShell needs it. Also check the prompt ends in `\proxier>`. |
| `running scripts is disabled on this system` | You tried to activate a Python environment by hand. You don't need to: use `.\proxy.bat`, which isn't affected. |
| The Microsoft Store opens | Windows' fake `python` shortcut. Install Python from python.org (step 1) and run `.\proxy.bat` again. |
| `not found (line N): …` | Check the spelling on that line of your list. The PDF is still made, and page 1 lists what's missing. |
| `Installing requirements failed` | You're offline, or the network blocks it. Try again on another connection. |
| Cards come out small | "Fit to page" was on. Reprint at **100% / Actual size**. |

### Cards print the wrong size

If a card still measures off at 100%, your printer is scaling. Measure the card's **height** in mm, then rerun with:

```
--card-height <88 × 88 ÷ your measurement>
```

For example, a card that measures 86.5 mm needs `--card-height 89.5`. Reprint one page and measure again.

---

## macOS and Linux

From a terminal in the `proxier` folder, once:

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Then, for each deck:

```
.venv/bin/python mtg_proxier.py ../decks/precon-strength-in-numbers.txt --skip-basics
```

Everything else above is the same.

---

## The fine print

These are **playtest cards**, for trying decks and loaning them to new players. Don't sell them, and don't pass them off as real cards. Every page says *"Playtest cards. Not for sale."*, and every PDF's document properties credit Wizards of the Coast for the cards and Scryfall for the images. The tool prints card images exactly as Scryfall serves them, artist credit included.
