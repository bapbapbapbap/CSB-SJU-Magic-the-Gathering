# Decks

The CSB/SJU club precons: five Commander decks built for loaning to new players, so anyone can borrow a whole deck and play before buying any cards. All five live on Archidekt in the [CSB/SJU Precon folder](https://archidekt.com/folders/1966850). The files here are straight Archidekt exports, CSV or text, and the proxier reads them as they are.

| Deck | Commander | File |
|---|---|---|
| Strength in Numbers | Iroas, God of Victory | [`precon-strength-in-numbers.txt`](precon-strength-in-numbers.txt) |
| Flashy flyers | Errant and Giada | [`precon-flashy-flyers.csv`](precon-flashy-flyers.csv) |
| Green is the new black | Davvol, Evincar of Rath | [`precon-green-is-the-new-black.csv`](precon-green-is-the-new-black.csv) |
| Greasy ass artifacts | Osgir, the Reconstructor | [`precon-greasy-ass-artifacts.csv`](precon-greasy-ass-artifacts.csv) |
| Kill the cat for the +1/+1 | Drizzt Do'Urden | [`precon-kill-the-cat.csv`](precon-kill-the-cat.csv) |

Proxy one (Windows, from the `proxier` folder; new to this? see the [tutorial](../TUTORIAL.md)):

```
.\proxy.bat ..\decks\precon-strength-in-numbers.txt --skip-basics
```

Maybeboard and Sideboard cards are left out automatically. Basic lands are skipped and listed with their counts on page 1 of the PDF.

## More decks

A larger library of bracket 2 Commander decks built for the club: [Archidekt bracket 2 folder](https://archidekt.com/folders/2002245). Export any of them (CSV or text) and run it through the proxier the same way. The [tutorial](../TUTORIAL.md#from-archidekt) covers the export settings.

## Staples

A hand-built reference of Commander staples, sorted by job (ramp, draw, interaction, tutors and more): [Archidekt staples folder](https://archidekt.com/folders/1992238).

## License

[CC BY-SA 4.0](../LICENSES/CC-BY-SA-4.0.txt): copy them, change them, play them. If you publish a version, credit "chud" and share it under the same license.
