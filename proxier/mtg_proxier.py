#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""mtg-proxier: turn a decklist (CSV or plain text) into a printable PDF of
playtest cards, using card images from the Scryfall API.

    python mtg_proxier.py deck.csv -o deck.pdf

Card images are printed as-is: no cropping, stretching, recoloring or
watermarks, so the artist and copyright lines stay intact (Scryfall's image
guidelines). Playtest cards are for personal, non-commercial use.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

__version__ = "0.1.0"

API = "https://api.scryfall.com"
USER_AGENT = f"mtg-proxier/{__version__}"
REPO_URL = "https://github.com/bapbapbapbap/CSB-SJU-Magic-the-Gathering"
FAN_CONTENT_POLICY = "https://company.wizards.com/en/legal/fancontentpolicy"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json;q=0.9,*/*;q=0.8"}
COLLECTION_BATCH = 75          # Scryfall's max identifiers per /cards/collection call
COLLECTION_INTERVAL = 0.5      # /cards/collection is limited to 2 requests/second
IMAGE_INTERVAL = 0.05          # be polite to the image CDN too
CACHE_TTL = 24 * 3600          # Scryfall asks clients to cache for at least 24 h

MM = 72 / 25.4                 # PDF points per millimetre
PAGE_SIZES = {"letter": (215.9, 279.4), "a4": (210.0, 297.0)}
BASIC_LANDS = {"plains", "island", "swamp", "mountain", "forest", "wastes",
               "snow-covered plains", "snow-covered island", "snow-covered swamp",
               "snow-covered mountain", "snow-covered forest"}


# --------------------------------------------------------------------------
# Decklist parsing
# --------------------------------------------------------------------------

@dataclass
class Entry:
    name: str
    qty: int = 1
    set: str | None = None
    collector_number: str | None = None
    line: int = 0                       # source line, for error messages
    scryfall_id: str | None = None      # exact printing (Archidekt, Moxfield, ManaBox exports)
    categories: tuple[str, ...] = ()    # Archidekt "Category" / Moxfield "Board" etc.

    def identifier(self) -> dict:
        if self.scryfall_id:
            return {"id": self.scryfall_id.lower()}
        if self.set and self.collector_number:
            return {"set": self.set.lower(), "collector_number": self.collector_number}
        if self.set:
            return {"name": self.name, "set": self.set.lower()}
        return {"name": self.name}


HEADER_ALIASES = {
    "name": {"name", "card name", "card", "cardname", "card_name"},
    "qty": {"quantity", "qty", "count", "amount", "#", "number of copies"},
    "set": {"set", "set code", "set_code", "setcode", "edition", "edition code"},
    "collector_number": {"collector number", "collector_number", "collectornumber",
                         "cn", "card number", "number", "collector #"},
    "scryfall_id": {"scryfall id", "scryfall_id", "scryfallid", "scryfall uuid", "scryfall_uuid"},
    "categories": {"category", "categories", "board"},
}
SET_CODE = re.compile(r"^[A-Za-z0-9]{2,6}$")    # "Edition" is a code on Moxfield, a full name on Deckbox
UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

SECTION_HEADERS = re.compile(
    r"^(commander|companion|deck|main ?deck|mainboard|sideboard|maybeboard|"
    r"considering|tokens?|lands?|creatures?|instants?|sorceries|artifacts?|"
    r"enchantments?|planeswalkers?|battles?|other)\s*(\(\d+\))?:?$", re.I)
# "1 Sol Ring", "1x Sol Ring", "1 Sol Ring (C21) 263", "1 Sol Ring [C21]", "Sol Ring"
TEXT_LINE = re.compile(
    r"^(?:(?P<qty>\d+)\s*[xX]?\s+)?(?P<name>.+?)"
    r"(?:\s+[\(\[](?P<set>[A-Za-z0-9]{2,6})[\)\]](?:\s+(?P<cn>[\w★†\-]+))?)?"
    r"(?:\s+\*[A-Z]+\*)?$")          # trailing "*F*" foil markers from some exporters


def _canon_header(h: str) -> str | None:
    h = h.strip().lower()
    for key, aliases in HEADER_ALIASES.items():
        if h in aliases:
            return key
    return None


def parse_csv(text: str) -> list[Entry]:
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return []
    mapping = {i: _canon_header(h) for i, h in enumerate(rows[0])}
    has_header = "name" in mapping.values()
    if not has_header:
        # Headerless: qty,name[,set[,collector_number]] or name only
        mapping = ({0: "qty", 1: "name", 2: "set", 3: "collector_number"}
                   if rows[0][0].strip().isdigit() else {0: "name"})
    body = rows[1:] if has_header else rows
    start = 2 if has_header else 1
    out = []
    for n, row in enumerate(body, start=start):
        vals = {mapping[i]: c.strip() for i, c in enumerate(row) if mapping.get(i) and c.strip()}
        if not vals.get("name"):
            continue
        qty = vals.get("qty", "1")
        try:
            qty = int(float(qty))
        except ValueError:
            raise ValueError(f"line {n}: quantity {qty!r} is not a number")
        set_ = vals.get("set")
        if set_ and not SET_CODE.match(set_):
            set_ = None                          # a set *name*, not a code: fall back to card name
        sid = vals.get("scryfall_id")
        if sid and not UUID.match(sid):
            sid = None
        cats = tuple(c.strip() for c in re.split(r"[,;]", vals.get("categories", "")) if c.strip())
        out.append(Entry(vals["name"], qty, set_, vals.get("collector_number") if set_ else None,
                         n, sid, cats))
    return out


def parse_text(text: str) -> list[Entry]:
    out = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(("//", "#")) or SECTION_HEADERS.match(line):
            continue
        if line.upper().startswith("SB:"):
            line = line[3:].strip()
        m = TEXT_LINE.match(line)
        if not m:
            continue
        out.append(Entry(m["name"].strip(), int(m["qty"] or 1), m["set"], m["cn"], n))
    return out


def parse_decklist(path: Path) -> list[Entry]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in {".csv", ".tsv"}:
        if path.suffix.lower() == ".tsv":
            text = text.replace("\t", ",")
        return parse_csv(text)
    return parse_text(text)


# --------------------------------------------------------------------------
# Scryfall
# --------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def is_basic_land(card: dict) -> bool:
    """True for basic lands, judged by Scryfall's type line ("Basic Land — Forest",
    "Basic Snow Land — Island", Wastes), so foreign or oddly named rows still count."""
    tl = card.get("type_line", "").split("//")[0]
    return "Basic" in tl and "Land" in tl


def card_matches(ident: dict, card: dict) -> bool:
    if "id" in ident:
        return card.get("id", "").lower() == ident["id"]
    if "collector_number" in ident:
        return (card.get("set", "").lower() == ident["set"]
                and str(card.get("collector_number", "")).lower() == ident["collector_number"].lower())
    if "set" in ident and card.get("set", "").lower() != ident["set"]:
        return False
    want = _norm(ident["name"])
    names = {_norm(card.get("name", ""))}
    names |= {_norm(f.get("name", "")) for f in card.get("card_faces", [])}
    return want in names


class Scryfall:
    def __init__(self, cache_dir: Path, session=None, sleep=time.sleep):
        if session is None:
            import requests
            session = requests.Session()
        self.http = session
        self.http.headers.update(HEADERS)
        self.cache = cache_dir
        self.cache.mkdir(parents=True, exist_ok=True)
        self.sleep = sleep
        self._last_collection = 0.0

    def _post_collection(self, idents: list[dict]) -> dict:
        wait = COLLECTION_INTERVAL - (time.monotonic() - self._last_collection)
        if wait > 0:
            self.sleep(wait)
        for attempt in range(4):
            r = self.http.post(f"{API}/cards/collection", json={"identifiers": idents}, timeout=30)
            self._last_collection = time.monotonic()
            if r.status_code == 429:
                self.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError("Scryfall kept answering 429 Too Many Requests; try again in a minute")

    def resolve(self, entries: list[Entry]) -> tuple[dict[int, dict], list[Entry]]:
        """Returns ({entry index: card object}, [entries not found])."""
        found: dict[int, dict] = {}
        unique: list[tuple[str, dict]] = []
        seen = set()
        for e in entries:
            key = json.dumps(e.identifier(), sort_keys=True)
            if key not in seen:
                seen.add(key)
                unique.append((key, e.identifier()))
        by_key: dict[str, dict] = {}
        for i in range(0, len(unique), COLLECTION_BATCH):
            batch = unique[i:i + COLLECTION_BATCH]
            data = self._post_collection([ident for _, ident in batch]).get("data", [])
            for key, ident in batch:
                card = next((c for c in data if card_matches(ident, c)), None)
                if card:
                    by_key[key] = card
        missing = []
        for idx, e in enumerate(entries):
            card = by_key.get(json.dumps(e.identifier(), sort_keys=True))
            if card:
                found[idx] = card
            else:
                missing.append(e)
        return found, missing

    def image(self, url: str) -> Path:
        name = hashlib.sha1(url.split("?")[0].encode()).hexdigest()
        ext = ".png" if ".png" in url else ".jpg"
        path = self.cache / f"{name}{ext}"
        if path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL:
            return path
        r = self.http.get(url, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
        self.sleep(IMAGE_INTERVAL)
        return path


def face_images(card: dict, size: str, backs: bool) -> list[str]:
    """Image URLs to print for one copy of a card: front, plus back for
    transform / modal double-faced cards when backs=True."""
    if "image_uris" in card:                       # single image: normal, split, flip, adventure, meld
        return [card["image_uris"][size]]
    faces = [f["image_uris"][size] for f in card.get("card_faces", []) if "image_uris" in f]
    return faces if backs else faces[:1]


# --------------------------------------------------------------------------
# PDF layout
# --------------------------------------------------------------------------

@dataclass
class Layout:
    page: str = "letter"
    card_w: float = 63.0          # mm
    card_h: float = 88.0          # mm
    gap: float = 0.0              # mm between cards
    cols: int = 3
    rows: int = 3
    crop_marks: bool = True
    corner_fill: str | None = "black"   # fill behind rounded PNG corners; None = paper white

    @property
    def per_page(self) -> int:
        return self.cols * self.rows

    def origin(self) -> tuple[float, float]:
        pw, ph = PAGE_SIZES[self.page]
        grid_w = self.cols * self.card_w + (self.cols - 1) * self.gap
        grid_h = self.rows * self.card_h + (self.rows - 1) * self.gap
        if grid_w > pw or grid_h > ph:
            raise ValueError(f"{self.cols}x{self.rows} grid ({grid_w:.1f}x{grid_h:.1f} mm) "
                             f"doesn't fit on {self.page} ({pw}x{ph} mm)")
        return (pw - grid_w) / 2, (ph - grid_h) / 2

    def slot(self, i: int) -> tuple[float, float]:
        """Bottom-left corner (mm, PDF coordinates) of slot i, filled left→right, top→bottom."""
        ox, oy = self.origin()
        col, row = i % self.cols, i // self.cols
        x = ox + col * (self.card_w + self.gap)
        y = oy + (self.rows - 1 - row) * (self.card_h + self.gap)
        return x, y


# What this PDF is, and whose is what. The tool's license (GPL) covers the tool,
# not this output: the card images in it belong to Wizards of the Coast, and the
# image hosting and card data come from Scryfall. Nothing here claims either.
META_SUBJECT = "Magic: The Gathering playtest cards. Personal, non-commercial use. Not for sale."
META_RIGHTS = ("Card images, card text and card names are \u00a9 Wizards of the Coast LLC. "
               "Unofficial Fan Content; not approved or endorsed by Wizards of the Coast. "
               "These rights are not covered by any license of the software that made this file.")
META_SOURCE = ("Card images and card data retrieved from Scryfall (https://scryfall.com) at the time "
               "this file was made. Not produced by, endorsed by, or affiliated with Scryfall.")
META_GENERATOR = (f"Made with mtg-proxier {__version__} ({REPO_URL}). The software is licensed "
                  "GPL-3.0-or-later; that license applies to the software only, not to this "
                  "document or the card images in it.")
META_KEYWORDS = "Magic: The Gathering; MTG; playtest cards; proxies; not for sale; Scryfall"


def _xml(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _xmp_packet(title: str, producer: str, created: str) -> bytes:
    def alt(v):
        return f'<rdf:Alt><rdf:li xml:lang="x-default">{_xml(v)}</rdf:li></rdf:Alt>'
    xml = f"""<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
    xmlns:xmpRights="http://ns.adobe.com/xap/1.0/rights/">
   <dc:format>application/pdf</dc:format>
   <dc:title>{alt(title)}</dc:title>
   <dc:description>{alt(META_SUBJECT)}</dc:description>
   <dc:rights>{alt(META_RIGHTS)}</dc:rights>
   <dc:source>https://scryfall.com</dc:source>
   <dc:subject><rdf:Bag>{"".join(f"<rdf:li>{_xml(k.strip())}</rdf:li>" for k in META_KEYWORDS.split(";"))}</rdf:Bag></dc:subject>
   <xmpRights:Marked>True</xmpRights:Marked>
   <xmpRights:Owner><rdf:Bag><rdf:li>Wizards of the Coast LLC</rdf:li></rdf:Bag></xmpRights:Owner>
   <xmpRights:UsageTerms>{alt(META_SUBJECT + " " + META_SOURCE)}</xmpRights:UsageTerms>
   <xmpRights:WebStatement>{FAN_CONTENT_POLICY}</xmpRights:WebStatement>
   <xmp:CreatorTool>{_xml(f"mtg-proxier {__version__} ({REPO_URL})")}</xmp:CreatorTool>
   <xmp:CreateDate>{created}</xmp:CreateDate>
   <xmp:MetadataDate>{created}</xmp:MetadataDate>
   <pdf:Producer>{_xml(producer)}</pdf:Producer>
   <pdf:Keywords>{_xml(META_KEYWORDS)}</pdf:Keywords>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    return xml.encode("utf-8")


def write_metadata(path: Path, title: str) -> None:
    """Stamp attribution into the PDF: standard Info fields, custom /Rights,
    /Source and /Generator keys, and an XMP packet (dc:rights, xmpRights:*),
    which is what Acrobat's copyright panel and asset managers read."""
    from datetime import datetime, timezone
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(str(path)))
    producer = str((writer.metadata or {}).get("/Producer", "ReportLab"))
    now = datetime.now(timezone.utc)
    writer.add_metadata({
        "/Title": title,
        "/Author": "",
        "/Subject": META_SUBJECT,
        "/Keywords": META_KEYWORDS,
        "/Creator": f"mtg-proxier {__version__} ({REPO_URL})",
        "/Rights": META_RIGHTS,
        "/Source": META_SOURCE,
        "/Generator": META_GENERATOR,
    })
    writer.xmp_metadata = _xmp_packet(title, producer, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    from pypdf.generic import NameObject
    stream = writer.root_object["/Metadata"].get_object()      # tag it so readers recognize it
    stream[NameObject("/Type")] = NameObject("/Metadata")
    stream[NameObject("/Subtype")] = NameObject("/XML")
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as f:
        writer.write(f)
    os.replace(tmp, path)


FOOTER = ("Playtest cards. Not for sale. Card images © Wizards of the Coast LLC. "
          "Images and data via Scryfall, not affiliated. Print at 100% / actual size.")


def render_pdf(images: list[Path], out: Path, layout: Layout) -> int:
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import black, HexColor

    pw, ph = PAGE_SIZES[layout.page]
    c = canvas.Canvas(str(out), pagesize=(pw * MM, ph * MM))
    c.setTitle(out.stem)
    c.setAuthor("")
    c.setCreator(f"mtg-proxier {__version__} ({REPO_URL})")
    pages = max(1, -(-len(images) // layout.per_page))
    for p in range(pages):
        chunk = images[p * layout.per_page:(p + 1) * layout.per_page]
        for i, img in enumerate(chunk):
            x, y = layout.slot(i)
            if layout.corner_fill:
                c.setFillColor(HexColor("#000000") if layout.corner_fill == "black"
                               else HexColor(layout.corner_fill))
                c.rect(x * MM, y * MM, layout.card_w * MM, layout.card_h * MM, stroke=0, fill=1)
            # preserveAspectRatio: never stretch the card image
            c.drawImage(str(img), x * MM, y * MM, layout.card_w * MM, layout.card_h * MM,
                        preserveAspectRatio=True, anchor="c", mask="auto")
        if layout.crop_marks:
            _crop_marks(c, layout, black)
        c.setFillColor(black)
        c.setFont("Helvetica", 6)
        c.drawCentredString(pw / 2 * MM, 2 * MM, FOOTER)
        c.drawRightString((pw - 5) * MM, (ph - 4) * MM, f"{p + 1}/{pages}")
        c.showPage()
    c.save()
    write_metadata(out, out.stem)
    return pages


def _crop_marks(c, layout: Layout, color) -> None:
    """Short ticks in the page margin lining up with every cut line."""
    pw, ph = PAGE_SIZES[layout.page]
    ox, oy = layout.origin()
    xs, ys = set(), set()
    for col in range(layout.cols):
        x = ox + col * (layout.card_w + layout.gap)
        xs |= {x, x + layout.card_w}
    for row in range(layout.rows):
        y = oy + row * (layout.card_h + layout.gap)
        ys |= {y, y + layout.card_h}
    top, right = oy + layout.rows * layout.card_h + (layout.rows - 1) * layout.gap, \
        ox + layout.cols * layout.card_w + (layout.cols - 1) * layout.gap
    tick = 3.0
    c.setStrokeColor(color)
    c.setLineWidth(0.25)
    for x in xs:
        c.line(x * MM, max(oy - tick, 0.5) * MM, x * MM, (oy - 0.75) * MM)
        c.line(x * MM, (top + 0.75) * MM, x * MM, min(top + tick, ph - 0.5) * MM)
    for y in ys:
        c.line(max(ox - tick, 0.5) * MM, y * MM, (ox - 0.75) * MM, y * MM)
        c.line((right + 0.75) * MM, y * MM, min(right + tick, pw - 0.5) * MM, y * MM)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def default_cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or (
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "") if os.name == "nt"
        else os.path.expanduser("~/.cache"))
    return Path(base) / "mtg-proxier"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mtg-proxier",
        description="Decklist (CSV or text) -> printable PDF of playtest cards via Scryfall.")
    p.add_argument("decklist", type=Path, help=".csv/.tsv with a header row, or a plain-text decklist")
    p.add_argument("-o", "--output", type=Path, help="PDF path (default: <decklist>.pdf)")
    p.add_argument("--page", choices=sorted(PAGE_SIZES), default="letter")
    p.add_argument("--gap", type=float, default=0.0, help="mm between cards (default 0: shared cut lines)")
    p.add_argument("--card-height", type=float, default=88.0,
                   help="mm; width follows at 63/88 (use to correct printer scaling)")
    p.add_argument("--image", choices=["png", "large", "normal"], default="png",
                   help="Scryfall image size (png = 745x1040, best for print)")
    p.add_argument("--no-backs", action="store_true", help="skip back faces of double-faced cards")
    p.add_argument("--skip-basics", action="store_true",
                   help="leave out basic lands (Plains, Island, Swamp, Mountain, Forest, Wastes, snow basics)")
    p.add_argument("--exclude-category", action="append", default=None, metavar="NAME",
                   help="drop rows in this Archidekt category / Moxfield board; repeatable "
                        "(default: Maybeboard). Pass --exclude-category none to keep everything")
    p.add_argument("--no-crop-marks", action="store_true")
    p.add_argument("--corner-fill", default="black",
                   help="color behind the rounded card corners: black, white, or #rrggbb")
    p.add_argument("--cache-dir", type=Path, default=None)
    p.add_argument("--dry-run", action="store_true", help="resolve cards and report, no images/PDF")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv=None, session=None, sleep=time.sleep) -> int:
    args = build_parser().parse_args(argv)
    if not args.decklist.exists():
        print(f"error: {args.decklist} not found", file=sys.stderr)
        return 2
    try:
        entries = parse_decklist(args.decklist)
    except ValueError as e:
        print(f"error: {args.decklist}: {e}", file=sys.stderr)
        return 2
    excluded = {_norm(c) for c in (args.exclude_category or ["Maybeboard"])} - {"none"}
    if excluded:
        before = len(entries)
        entries = [e for e in entries if not excluded & {_norm(c) for c in e.categories}]
        if before - len(entries):
            print(f"Skipping {before - len(entries)} line(s) in: {', '.join(sorted(excluded))}")
    if args.skip_basics:   # cheap name check first, so basics never hit the API
        entries = [e for e in entries if _norm(e.name) not in BASIC_LANDS]
    if not entries:
        print("error: no cards to print in the decklist", file=sys.stderr)
        return 2

    sf = Scryfall(args.cache_dir or default_cache(), session=session, sleep=sleep)
    total = sum(e.qty for e in entries)
    print(f"Looking up {len(entries)} unique lines ({total} cards) on Scryfall...")
    found, missing = sf.resolve(entries)
    if args.skip_basics:   # then the type line, for anything the name check missed
        found = {i: c for i, c in found.items() if not is_basic_land(c)}
    for e in missing:
        where = f" [{e.set}{' #' + e.collector_number if e.collector_number else ''}]" if e.set else ""
        print(f"  not found (line {e.line}): {e.name}{where}", file=sys.stderr)
    if args.dry_run:
        for idx, card in sorted(found.items()):
            e = entries[idx]
            print(f"  {e.qty} x {card['name']} ({card['set'].upper()} {card['collector_number']})")
        return 1 if missing else 0

    images: list[Path] = []
    for idx, card in sorted(found.items()):
        urls = face_images(card, args.image, backs=not args.no_backs)
        paths = [sf.image(u) for u in urls]
        images.extend(paths * entries[idx].qty)

    layout = Layout(page=args.page, gap=args.gap,
                    card_h=args.card_height, card_w=args.card_height * 63 / 88,
                    crop_marks=not args.no_crop_marks,
                    corner_fill=None if args.corner_fill.lower() == "white" else args.corner_fill)
    out = args.output or args.decklist.with_suffix(".pdf")
    pages = render_pdf(images, out, layout)
    print(f"Wrote {out}: {len(images)} cards on {pages} page(s).")
    if missing:
        print(f"{len(missing)} line(s) not found; see above.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
