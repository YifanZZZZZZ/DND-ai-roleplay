#!/usr/bin/env python3
"""Create a labeled PNG contact sheet from a JSON manifest."""

from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_sheet(items: list[dict], output: Path, columns: int, thumb_width: int) -> None:
    if not items:
        raise ValueError("manifest has no items")
    columns = max(1, columns)
    label_height = 54
    gap = 16
    cell_width = thumb_width
    cell_height = int(thumb_width * 0.75) + label_height
    rows = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * cell_width + (columns + 1) * gap,
                              rows * cell_height + (rows + 1) * gap), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, item in enumerate(items):
        source = Path(item["file"])
        image = Image.open(source).convert("RGB")
        max_height = cell_height - label_height
        image.thumbnail((cell_width, max_height))
        column = index % columns
        row = index // columns
        x = gap + column * (cell_width + gap) + (cell_width - image.width) // 2
        y = gap + row * (cell_height + gap) + (max_height - image.height) // 2
        sheet.paste(image, (x, y))
        label = str(item.get("label") or item.get("id") or source.stem)
        draw.text((gap + column * (cell_width + gap),
                   gap + row * (cell_height + gap) + max_height + 8),
                  label[:80], fill="black", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, "PNG")


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        items = []
        for index, color in enumerate(("#7E9CC2", "#C4936A", "#7BA17B"), 1):
            path = root / f"test-{index}.png"
            Image.new("RGB", (320, 240), color).save(path)
            items.append({"id": f"TEST_{index}", "file": str(path), "label": f"Test {index}"})
        output = root / "sheet.png"
        create_sheet(items, output, 2, 240)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("self-test did not create a contact sheet")
    print("Contact sheet self-test: OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path,
                        help="JSON array of objects containing id, file, and optional label")
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--thumb-width", type=int, default=420)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.manifest or not args.output:
        parser.error("provide manifest and output, or use --self-test")
    items = json.loads(args.manifest.read_text(encoding="utf-8"))
    create_sheet(items, args.output, args.columns, args.thumb_width)
    print(args.output)


if __name__ == "__main__":
    main()
