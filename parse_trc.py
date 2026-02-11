"""Parse the TRC guide HTML to extract all building categories and their rules."""

import json
import sys
from html.parser import HTMLParser
from pathlib import Path


class CardExtractor(HTMLParser):
    """Extract accordion cards from the TRC guide HTML."""

    def __init__(self):
        super().__init__()
        self.cards: list[dict] = []
        self.current_card: dict | None = None
        self.in_heading = False
        self.in_li = False
        self.text_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")

        # Detect card container
        if tag == "div" and "card" == cls.strip():
            card_id = attrs_dict.get("id", "")
            if card_id and card_id.isdigit():
                self.current_card = {"id": card_id, "title": "", "items": []}
                self.cards.append(self.current_card)

        # Detect card heading link
        if tag == "a" and "card-link" in cls and self.current_card:
            self.in_heading = True
            self.text_buf = []

        # Detect list items inside card body
        if tag == "li" and self.current_card:
            self.in_li = True
            self.text_buf = []

    def handle_endtag(self, tag):
        if tag == "a" and self.in_heading:
            self.in_heading = False
            if self.current_card:
                title = " ".join(self.text_buf).strip()
                self.current_card["title"] = title

        if tag == "li" and self.in_li:
            self.in_li = False
            text = " ".join(self.text_buf).strip()
            if text and self.current_card and len(text) > 3:
                self.current_card["items"].append(text)

    def handle_data(self, data):
        if self.in_heading or self.in_li:
            stripped = data.strip()
            if stripped:
                self.text_buf.append(stripped)


def main():
    ar_path = Path("decode_output/trc_index.html")
    en_path = Path("decode_output/trc_eindex.html.html")
    out_dir = Path("building_codes_output")
    out_dir.mkdir(exist_ok=True)

    results = {}

    for label, path in [("arabic", ar_path), ("english", en_path)]:
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        parser = CardExtractor()
        parser.feed(html)

        results[label] = {
            "total_categories": len(parser.cards),
            "categories": parser.cards,
        }

        print(f"\n=== {label.upper()} TRC Guide ===")
        print(f"Total categories: {len(parser.cards)}")
        for card in parser.cards:
            items_count = len(card["items"])
            print(f"  [{card['id']}] {card['title']} ({items_count} items)")
            for item in card["items"][:3]:
                print(f"       - {item[:120]}")
            if items_count > 3:
                print(f"       ... and {items_count - 3} more")

    out_file = out_dir / "trc_all_categories.json"
    out_file.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved to {out_file}")


if __name__ == "__main__":
    sys.stdout = open(
        "building_codes_output/trc_parse_output.txt", "w", encoding="utf-8",
    )
    main()
