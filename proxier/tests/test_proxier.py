# SPDX-License-Identifier: GPL-3.0-or-later
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mtg_proxier as mp  # noqa: E402


# ---------------------------------------------------------------- parsing

def test_csv_moxfield_style_header():
    text = "Count,Name,Edition,Collector Number\n1,Sol Ring,C21,263\n2,Island,,\n"
    e = mp.parse_csv(text)
    assert [(x.qty, x.name, x.set, x.collector_number) for x in e] == [
        (1, "Sol Ring", "C21", "263"), (2, "Island", None, None)]


def test_csv_manabox_style_header_any_column_order():
    text = "Name,Set code,Collector number,Quantity,Foil\nCommand Tower,cmm,1032,1,normal\n"
    (e,) = mp.parse_csv(text)
    assert (e.name, e.set, e.collector_number, e.qty) == ("Command Tower", "cmm", "1032", 1)


def test_csv_headerless():
    assert [(x.qty, x.name) for x in mp.parse_csv("1,Sol Ring\n3,Forest\n")] == [(1, "Sol Ring"), (3, "Forest")]
    assert [(x.qty, x.name) for x in mp.parse_csv("Sol Ring\nForest\n")] == [(1, "Sol Ring"), (1, "Forest")]


def test_csv_bad_quantity_names_the_line():
    with pytest.raises(ValueError, match="line 3"):
        mp.parse_csv("qty,name\n1,Sol Ring\nlots,Forest\n")


def test_text_decklist_formats():
    text = """Commander
1 Atraxa, Praetors' Voice
// ramp
1x Sol Ring
1 Command Tower (CMM) 1032
1 Arcane Signet [ELD]
1 Fire // Ice
Sideboard
SB: 2 Swords to Plowshares
1 Lightning Bolt (2X2) 117 *F*
"""
    got = [(e.qty, e.name, e.set, e.collector_number) for e in mp.parse_text(text)]
    assert got == [
        (1, "Atraxa, Praetors' Voice", None, None),
        (1, "Sol Ring", None, None),
        (1, "Command Tower", "CMM", "1032"),
        (1, "Arcane Signet", "ELD", None),
        (1, "Fire // Ice", None, None),
        (2, "Swords to Plowshares", None, None),
        (1, "Lightning Bolt", "2X2", "117"),
    ]


def test_identifier_shapes():
    assert mp.Entry("Sol Ring").identifier() == {"name": "Sol Ring"}
    assert mp.Entry("Sol Ring", set="C21").identifier() == {"name": "Sol Ring", "set": "c21"}
    assert mp.Entry("Sol Ring", set="C21", collector_number="263").identifier() == {
        "set": "c21", "collector_number": "263"}


# ---------------------------------------------------------------- fake Scryfall

def _png(color, size=(745, 1040)):
    """Plain placeholder image with transparent corners, like Scryfall's png."""
    img = Image.new("RGBA", size, color)
    for x in range(30):
        for y in range(30 - x):
            for cx, cy in [(x, y), (size[0] - 1 - x, y), (x, size[1] - 1 - y), (size[0] - 1 - x, size[1] - 1 - y)]:
                img.putpixel((cx, cy), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _uuid(set_, cn):
    import hashlib
    h = hashlib.md5(f"{set_}{cn}".encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _card(name, set_, cn, faces=None, type_line="Artifact"):
    base = f"https://cards.scryfall.io/png/front/{set_}/{cn}"
    c = {"object": "card", "id": _uuid(set_, cn), "name": name, "set": set_,
         "collector_number": cn, "type_line": type_line}
    if faces:
        c["card_faces"] = [{"name": f, "image_uris": {"png": f"{base}-{i}.png?1", "large": f"{base}-{i}.jpg"}}
                           for i, f in enumerate(faces)]
    else:
        c["image_uris"] = {"png": f"{base}.png?1", "large": f"{base}.jpg"}
    return c


DB = [
    _card("Sol Ring", "c21", "263"),
    _card("Sol Ring", "cmm", "400"),
    _card("Command Tower", "cmm", "1032"),
    _card("Forest", "fdn", "280", type_line="Basic Land \u2014 Forest"),
    _card("Snow-Covered Island", "khm", "277", type_line="Basic Snow Land \u2014 Island"),
    _card("Wastes", "ogw", "183", type_line="Basic Land"),
    _card("Dryad Arbor", "fut", "174", type_line="Land Creature \u2014 Forest Dryad"),
    _card("Delver of Secrets // Insectile Aberration", "isd", "51",
          faces=["Delver of Secrets", "Insectile Aberration"],
          type_line="Creature \u2014 Human Wizard // Creature \u2014 Human Insect"),
    _card("Fire // Ice", "mh2", "290"),
    # Adventure as the real API shapes it: one image, faces carry names only
    dict(_card("Brazen Borrower // Petty Theft", "eld", "39", type_line="Creature // Instant \u2014 Adventure"),
         card_faces=[{"name": "Brazen Borrower"}, {"name": "Petty Theft"}]),
    # and the same layout with no card_faces at all, to prove the " // " split alone works
    _card("Bonecrusher Giant // Stomp", "eld", "115", type_line="Creature // Instant \u2014 Adventure"),
]


class Resp:
    def __init__(self, status=200, payload=None, content=b""):
        self.status_code, self._payload, self.content = status, payload, content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, throttle_first=0):
        self.headers = {}
        self.posts, self.gets, self.named = [], [], []
        self.throttle = throttle_first

    def post(self, url, json=None, timeout=None):
        assert url.endswith("/cards/collection")
        assert len(json["identifiers"]) <= mp.COLLECTION_BATCH
        self.posts.append(json["identifiers"])
        if self.throttle:
            self.throttle -= 1
            return Resp(429)
        data, nf = [], []
        for ident in json["identifiers"]:
            hits = [c for c in DB if mp.card_matches(ident, c)]
            (data.append(hits[0]) if hits else nf.append(ident))
        return Resp(payload={"object": "list", "not_found": nf, "data": data})

    def get(self, url, params=None, timeout=None):
        self.gets.append(url)
        if url.endswith("/cards/named"):
            self.named.append(params)
            q = params["fuzzy"].lower().replace(" ", "")
            for c in DB:
                if "set" in params and c["set"] != params["set"]:
                    continue
                n = c["name"].lower().replace(" ", "")
                if sorted(q) == sorted(n[:len(q)]) or n.startswith(q):   # crude stand-in for fuzzy
                    return Resp(payload=c)
            return Resp(404, payload={"object": "error"})
        return Resp(content=_png((90, 90, 120, 255)))


def test_required_headers_are_set(tmp_path):
    s = FakeSession()
    mp.Scryfall(tmp_path, session=s, sleep=lambda _: None)
    assert s.headers["User-Agent"].startswith("mtg-proxier/")
    assert "Accept" in s.headers


def test_resolve_matches_by_name_set_and_number(tmp_path):
    sf = mp.Scryfall(tmp_path, session=FakeSession(), sleep=lambda _: None)
    entries = [mp.Entry("Sol Ring", set="cmm", collector_number="400"),
               mp.Entry("sol ring"),
               mp.Entry("Delver of Secrets"),
               mp.Entry("Not A Real Card")]
    found, missing = sf.resolve(entries)
    assert found[0]["set"] == "cmm"
    assert found[1]["name"] == "Sol Ring"
    assert found[2]["name"].startswith("Delver")
    assert [m.name for m in missing] == ["Not A Real Card"]


def test_resolve_batches_at_75_and_dedupes(tmp_path):
    s = FakeSession()
    sf = mp.Scryfall(tmp_path, session=s, sleep=lambda _: None)
    entries = [mp.Entry(f"Card {i}") for i in range(160)] + [mp.Entry("Card 3")]
    sf.resolve(entries)
    assert [len(p) for p in s.posts] == [75, 75, 10]


def test_resolve_backs_off_on_429(tmp_path):
    waits = []
    s = FakeSession(throttle_first=2)
    sf = mp.Scryfall(tmp_path, session=s, sleep=waits.append)
    found, _ = sf.resolve([mp.Entry("Sol Ring")])
    assert found and len(s.posts) == 3 and 1 in waits and 2 in waits


def test_face_images():
    delver = next(c for c in DB if c["name"].startswith("Delver"))
    assert len(mp.face_images(delver, "png", backs=True)) == 2
    assert len(mp.face_images(delver, "png", backs=False)) == 1
    fire_ice = next(c for c in DB if c["name"] == "Fire // Ice")
    assert len(mp.face_images(fire_ice, "png", backs=True)) == 1   # split card: one image


def test_image_cache_is_reused(tmp_path):
    s = FakeSession()
    sf = mp.Scryfall(tmp_path, session=s, sleep=lambda _: None)
    a = sf.image("https://cards.scryfall.io/png/front/x.png?123")
    b = sf.image("https://cards.scryfall.io/png/front/x.png?456")
    assert a == b and len(s.gets) == 1


# ---------------------------------------------------------------- layout + end to end

@pytest.mark.parametrize("page", ["letter", "a4"])
def test_layout_fits_and_centers(page):
    lay = mp.Layout(page=page)
    pw, ph = mp.PAGE_SIZES[page]
    ox, oy = lay.origin()
    assert ox > 5 and oy > 5
    assert ox + 3 * 63 == pytest.approx(pw - ox)
    assert lay.slot(0) == pytest.approx((ox, oy + 2 * 88))      # top-left first
    assert lay.slot(8) == pytest.approx((ox + 2 * 63, oy))


def test_layout_too_big_raises():
    with pytest.raises(ValueError, match="doesn't fit"):
        mp.Layout(page="letter", gap=10).origin()


def test_end_to_end_pdf(tmp_path, capsys):
    deck = tmp_path / "deck.csv"
    deck.write_text("Quantity,Name,Set,Collector Number\n"
                    "1,Sol Ring,c21,263\n"
                    "1,Command Tower,,\n"
                    "8,Forest,,\n"
                    "1,Delver of Secrets,,\n"
                    "1,Totally Fake Card,,\n")
    out = tmp_path / "deck.pdf"
    rc = mp.main([str(deck), "-o", str(out), "--cache-dir", str(tmp_path / "cache")],
                 session=FakeSession(), sleep=lambda _: None)
    err = capsys.readouterr().err
    assert rc == 1 and "Totally Fake Card" in err          # missing card reported, PDF still made
    assert out.exists()
    info = subprocess.run(["pdfinfo", str(out)], capture_output=True, text=True).stdout
    assert _pages(out) == 2                                  # 1+1+8+2 faces = 12 cards -> 2 pages
    assert "612 x 792 pts" in info                           # US Letter


def test_skip_basics_and_no_backs(tmp_path):
    deck = tmp_path / "d.txt"
    deck.write_text("8 Forest\n1 Delver of Secrets\n1 Sol Ring\n")
    out = tmp_path / "d.pdf"
    rc = mp.main([str(deck), "-o", str(out), "--skip-basics", "--no-backs",
                  "--cache-dir", str(tmp_path / "c")], session=FakeSession(), sleep=lambda _: None)
    assert rc == 0
    assert _pages(out) == 1


def test_dry_run_makes_no_pdf(tmp_path, capsys):
    deck = tmp_path / "d.txt"
    deck.write_text("1 Sol Ring\n")
    rc = mp.main([str(deck), "--dry-run", "--cache-dir", str(tmp_path / "c")],
                 session=FakeSession(), sleep=lambda _: None)
    assert rc == 0 and not (tmp_path / "d.pdf").exists()
    assert "Sol Ring (C21 263)" in capsys.readouterr().out


# ---------------------------------------------------------------- Archidekt + basics

ARCHIDEKT_HEADER = ("Quantity,Name,Finish,Condition,Date Added,Language,Purchase Price,Tags,"
                    "Edition Name,Edition Code,Multiverse Id,Scryfall ID,MTGO ID,Collector Number,"
                    "Mana Value,Colors,Identities,Mana cost,Types,Sub-types,Super-types,Rarity,Price,Category")


def _arch_row(qty, name, set_name, set_, cn, category):
    return (f'{qty},"{name}",Normal,NM,2026-11-01,EN,,,"{set_name}",{set_},,{_uuid(set_, cn)},,{cn},'
            f',,,,,,,,,"{category}"')


ARCHIDEKT_DECK = "\n".join([
    ARCHIDEKT_HEADER,
    _arch_row(1, "Sol Ring", "Commander Masters", "cmm", "400", "Ramp"),
    _arch_row(1, "Command Tower", "Commander Masters", "cmm", "1032", "Land"),
    _arch_row(12, "Forest", "Foundations", "fdn", "280", "Land"),
    _arch_row(3, "Snow-Covered Island", "Kaldheim", "khm", "277", "Land"),
    _arch_row(1, "Wastes", "Oath of the Gatewatch", "ogw", "183", "Land"),
    _arch_row(1, "Dryad Arbor", "Future Sight", "fut", "174", "Land,Creature"),
    _arch_row(1, "Fire // Ice", "Modern Horizons 2", "mh2", "290", "Maybeboard"),
]) + "\n"


def test_archidekt_csv_parses_ids_and_categories():
    rows = mp.parse_csv(ARCHIDEKT_DECK)
    sol = rows[0]
    assert (sol.qty, sol.name, sol.set, sol.collector_number) == (1, "Sol Ring", "cmm", "400")
    assert sol.identifier() == {"id": _uuid("cmm", "400")}       # exact printing wins
    assert rows[5].categories == ("Land", "Creature")
    assert rows[6].categories == ("Maybeboard",)


def test_set_name_in_edition_column_is_not_used_as_code():
    (e,) = mp.parse_csv("Count,Name,Edition,Card Number\n4,Sol Ring,Commander 2021,263\n")
    assert e.set is None and e.collector_number is None and e.identifier() == {"name": "Sol Ring"}


def test_is_basic_land():
    by_name = {c["name"]: c for c in DB}
    assert mp.is_basic_land(by_name["Forest"])
    assert mp.is_basic_land(by_name["Snow-Covered Island"])
    assert mp.is_basic_land(by_name["Wastes"])
    assert not mp.is_basic_land(by_name["Dryad Arbor"])         # Forest subtype, not basic
    assert not mp.is_basic_land(by_name["Command Tower"])


def _pages(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    return int(next(l.split()[-1] for l in out.splitlines() if l.startswith("Pages:")))


def test_archidekt_skip_basics_and_maybeboard(tmp_path, capsys):
    deck = tmp_path / "archidekt.csv"
    deck.write_text(ARCHIDEKT_DECK)
    out = tmp_path / "a.pdf"
    s = FakeSession()
    rc = mp.main([str(deck), "-o", str(out), "--skip-basics", "--cache-dir", str(tmp_path / "c")],
                 session=s, sleep=lambda _: None)
    assert rc == 0
    printed = capsys.readouterr().out
    assert "Skipping 1 line(s) in: maybeboard" in printed
    assert "3 cards" in printed and _pages(out) == 1           # Sol Ring, Command Tower, Dryad Arbor
    looked_up = [i for batch in s.posts for i in batch]
    assert len(looked_up) == 3                                 # basics never sent to Scryfall


def test_archidekt_keep_everything(tmp_path):
    deck = tmp_path / "archidekt.csv"
    deck.write_text(ARCHIDEKT_DECK)
    out = tmp_path / "a.pdf"
    rc = mp.main([str(deck), "-o", str(out), "--exclude-category", "none",
                  "--cache-dir", str(tmp_path / "c")], session=FakeSession(), sleep=lambda _: None)
    assert rc == 0 and _pages(out) == 3                        # 1+1+12+3+1+1+1 = 20 cards


def test_basic_caught_by_type_line_when_name_differs(tmp_path):
    """A basic listed under an unexpected name (e.g. foreign) is still dropped via type line."""
    deck = tmp_path / "d.csv"
    deck.write_text(f"Quantity,Name,Scryfall ID\n10,Wald,{_uuid('fdn', '280')}\n1,Sol Ring,\n")
    out = tmp_path / "d.pdf"
    rc = mp.main([str(deck), "-o", str(out), "--skip-basics", "--cache-dir", str(tmp_path / "c")],
                 session=FakeSession(), sleep=lambda _: None)
    assert rc == 0 and _pages(out) == 1


# ---------------------------------------------------------------- PDF metadata

def test_pdf_metadata_attributes_correctly(tmp_path):
    import xml.etree.ElementTree as ET
    from pypdf import PdfReader

    deck = tmp_path / "Atraxa Superfriends.txt"
    deck.write_text("1 Sol Ring\n")
    out = tmp_path / "out.pdf"
    assert mp.main([str(deck), "-o", str(out), "--cache-dir", str(tmp_path / "c")],
                   session=FakeSession(), sleep=lambda _: None) == 0
    r = PdfReader(str(out))
    info = r.metadata

    assert info["/Title"] == "out"
    assert "Not for sale" in info["/Subject"]
    assert "Wizards of the Coast LLC" in info["/Rights"]
    assert "not covered by any license of the software" in info["/Rights"]
    assert "Scryfall" in info["/Source"] and "Not produced by, endorsed by, or affiliated with Scryfall" in info["/Source"]
    assert "GPL-3.0-or-later" in info["/Generator"] and "software only" in info["/Generator"]
    assert mp.REPO_URL in info["/Creator"]
    # The GPL is only ever named as the software's license, never the document's
    for key in ("/Title", "/Subject", "/Rights", "/Source", "/Keywords"):
        assert "GPL" not in info[key]

    raw = r.trailer["/Root"]["/Metadata"].get_object().get_data()
    root = ET.fromstring(raw.split(b"?>", 1)[1].rsplit(b"<?xpacket", 1)[0])   # well-formed XML
    ns = {"dc": "http://purl.org/dc/elements/1.1/",
          "xmpRights": "http://ns.adobe.com/xap/1.0/rights/",
          "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}
    rights = root.find(".//dc:rights/rdf:Alt/rdf:li", ns).text
    assert rights == mp.META_RIGHTS
    assert root.find(".//xmpRights:Marked", ns).text == "True"
    assert root.find(".//xmpRights:Owner/rdf:Bag/rdf:li", ns).text == "Wizards of the Coast LLC"
    assert root.find(".//xmpRights:WebStatement", ns).text == mp.FAN_CONTENT_POLICY
    assert root.find(".//dc:source", ns).text == "https://scryfall.com"
    assert not out.with_suffix(".pdf.tmp").exists()


def test_xmp_stream_is_tagged(tmp_path):
    from pypdf import PdfReader
    deck = tmp_path / "d.txt"
    deck.write_text("1 Sol Ring\n")
    out = tmp_path / "d.pdf"
    mp.main([str(deck), "-o", str(out), "--cache-dir", str(tmp_path / "c")],
            session=FakeSession(), sleep=lambda _: None)
    md = PdfReader(str(out)).trailer["/Root"]["/Metadata"].get_object()
    assert md["/Type"] == "/Metadata" and md["/Subtype"] == "/XML"
    r = subprocess.run(["pdfinfo", str(out)], capture_output=True, text=True)
    assert "Unknown Metadata" not in r.stderr


# ---------------------------------------------------------------- adventures, fuzzy

def test_adventure_and_split_match_on_either_half(tmp_path):
    sf = mp.Scryfall(tmp_path, session=FakeSession(), sleep=lambda _: None)
    found, missing = sf.resolve([mp.Entry("Brazen Borrower"), mp.Entry("Bonecrusher Giant"),
                                 mp.Entry("Fire"), mp.Entry("Fire // Ice")])
    assert not missing and len(found) == 4
    assert mp.face_images(found[0], "png", backs=True) == [found[0]["image_uris"]["png"]]   # one image


def test_fuzzy_corrects_typos_and_says_so(tmp_path, capsys):
    deck = tmp_path / "d.txt"
    deck.write_text("1 Sol Rnig\n1 Zzzz Not A Card\n")
    s = FakeSession()
    rc = mp.main([str(deck), "-o", str(tmp_path / "d.pdf"), "--cache-dir", str(tmp_path / "c")],
                 session=s, sleep=lambda _: None)
    err = capsys.readouterr().err
    assert "corrected (line 1): 'Sol Rnig' -> Sol Ring" in err
    assert "not found (line 2): Zzzz Not A Card" in err
    assert rc == 1 and len(s.named) == 2


def test_fuzzy_never_guesses_a_pinned_printing(tmp_path):
    s = FakeSession()
    sf = mp.Scryfall(tmp_path, session=s, sleep=lambda _: None)
    assert sf.fuzzy(mp.Entry("Sol Ring", set="c21", collector_number="999")) is None
    assert sf.fuzzy(mp.Entry("Sol Ring", scryfall_id="00000000-0000-0000-0000-000000000000")) is None
    assert s.named == []


def test_no_fuzzy_flag(tmp_path, capsys):
    deck = tmp_path / "d.txt"
    deck.write_text("1 Sol Rnig\n1 Sol Ring\n")
    s = FakeSession()
    rc = mp.main([str(deck), "--no-fuzzy", "-o", str(tmp_path / "d.pdf"), "--cache-dir", str(tmp_path / "c")],
                 session=s, sleep=lambda _: None)
    assert rc == 1 and s.named == [] and "not found (line 1): Sol Rnig" in capsys.readouterr().err
