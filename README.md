# CSB/SJU Magic: The Gathering

Tools I made for Magic: The Gathering, open for anyone to use: a deck box you can print, a free proxy printer, the club's precon decklists, and a staples reference.

| Folder | What's in it |
|---|---|
| [`box/`](box/) | A 3D-printable clamshell deck box sized for double-sleeved Commander decks (STL files) |
| [`proxier/`](proxier/) | Turns a decklist CSV (Archidekt, Moxfield, ManaBox…) into a printable PDF of playtest cards using Scryfall |
| [`decks/`](decks/) | The four CSB/SJU club precons, as CSVs the proxier reads directly, plus links to the [precon folder](https://archidekt.com/folders/1966850) and the [staples folder](https://archidekt.com/folders/1992238) on Archidekt |

## License: open, and it stays open

You're free to use, study, change, share, and sell anything here. The one condition: if you distribute something built from it, you release it under the same license, so nobody can take this and close it up.

| Part | License |
|---|---|
| `proxier/` (code) | [GPL-3.0-or-later](LICENSES/GPL-3.0-or-later.txt) |
| `box/` (3D models) and `decks/` (decklists) | [CC BY-SA 4.0](LICENSES/CC-BY-SA-4.0.txt): credit "chud", share alike |

The one thing that isn't mine to license is the card art. The proxier downloads card images from Scryfall when you run it, and those stay © Wizards of the Coast. None are stored in this repo.

## Quick start: proxy one of these decks

Windows, from the `proxier` folder:

```
.\proxy.bat ..\decks\precon-flashy-flyers.csv --skip-basics
```

macOS / Linux: see [`proxier/README.md`](proxier/README.md).

Print the PDF at 100% scale, cut along the marks, and sleeve each proxy in front of a basic land or a bulk card.

Testing it, or getting an AI assistant to help you run it? Start with [`llms.txt`](llms.txt). It has the full test procedure and the expected results for each step.

---

Unofficial Fan Content permitted under the Wizards of the Coast Fan Content Policy. Not approved or endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.
