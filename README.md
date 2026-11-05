# CSB/SJU Magic: The Gathering

Tools I made for Magic: The Gathering, open for anyone to use: a deck box you can print, a proxy printer, and my decklists.

| Folder | What's in it |
|---|---|
| [`box/`](box/) | A 3D-printable clamshell deck box sized for double-sleeved Commander decks (STL files) |
| [`proxier/`](proxier/) | Turns a decklist CSV (Archidekt, Moxfield, ManaBox…) into a printable PDF of playtest cards using Scryfall |
| [`decks/`](decks/) | My own Commander decklists, in a format the proxier reads directly |

## License: open, and it stays open

You're free to use, study, change, share, and sell anything here. The one condition: if you distribute something built from it, you release it under the same license, so nobody can take this and close it up.

| Part | License |
|---|---|
| `proxier/` (code) | [GPL-3.0-or-later](LICENSES/GPL-3.0-or-later.txt) |
| `box/` (3D models) and `decks/` (decklists) | [CC BY-SA 4.0](LICENSES/CC-BY-SA-4.0.txt): credit "chud", share alike |

The one thing that isn't mine to license is the card art. The proxier downloads card images from Scryfall when you run it, and those stay © Wizards of the Coast. None are stored in this repo.

## Quick start: proxy one of these decks

```
cd proxier
pip install -r requirements.txt
python mtg_proxier.py ../decks/<deck>.csv --skip-basics
```

Print the PDF at 100% scale, cut along the marks, and sleeve each proxy in front of a basic land or a bulk card.

---

Unofficial Fan Content permitted under the Wizards of the Coast Fan Content Policy. Not approved or endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.
