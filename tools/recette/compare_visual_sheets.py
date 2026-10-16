"""Visual comparison sheets for corpus acceptance (contain document images:
the destination must be private; a destination inside this repository is refused).

Usage: compare_visual_sheets.py <baseline_out> <final_out> <dest_dir>

Per page: original | baseline candidate | final candidate | diff(final vs original).
Per document: crops of visual regions (stamp/logo/monochrome candidates) that are
protected in one run but not in the other, for human audit of reclassification.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SHEET_DPI = 80
CROP_DPI = 200
VISUAL = {"stamp_or_logo_candidate", "monochrome_visual_candidate"}
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
REPO_ROOT = Path(__file__).resolve().parents[2]


def render(pdf: Path, index: int, dpi: int) -> Image.Image:
    doc = fitz.open(pdf)
    pix = doc[index].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    return img


def diff_image(a: Image.Image, b: Image.Image) -> Image.Image:
    x = np.asarray(a.convert("L"), dtype=int)
    y = np.asarray(b.convert("L").resize(a.size), dtype=int)
    d = np.abs(x - y) > 40
    base = np.stack([x] * 3, axis=2).astype(np.uint8) // 2 + 127
    base[d] = [220, 30, 30]
    return Image.fromarray(base)


def labelled(images: list[Image.Image], labels: list[str]) -> Image.Image:
    w = sum(i.width for i in images) + 10 * (len(images) - 1)
    h = max(i.height for i in images) + 30
    sheet = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(sheet)
    x = 0
    for img, label in zip(images, labels, strict=True):
        sheet.paste(img, (x, 30))
        draw.text((x + 4, 4), label, fill=(0, 0, 0), font=FONT)
        x += img.width + 10
    return sheet


def visual_set(analysis: dict) -> set[tuple]:
    return {
        (int(r["page"]), tuple(round(v, 1) for v in r["bbox"]))
        for r in analysis.get("protected_visual_regions") or []
        if r.get("subtype") in VISUAL
    }


def main() -> int:
    base_root, final_root, dest_root = (Path(p) for p in sys.argv[1:4])
    dest_root = dest_root.resolve()
    if dest_root == REPO_ROOT or REPO_ROOT in dest_root.parents:
        print("REFUSED: destination inside the repository", file=sys.stderr)
        return 2
    dest_root.mkdir(parents=True, exist_ok=True)
    for final_dir in sorted(final_root.glob("DOC-00*")):
        name = final_dir.name
        base_dir = base_root / name
        if not (final_dir / "candidate.pdf").exists() or not (base_dir / "candidate.pdf").exists():
            print(name, "SKIPPED_MISSING_CANDIDATE")
            continue
        analysis = json.load(open(final_dir / "analysis.json"))
        base_analysis = json.load(open(base_dir / "analysis.json"))
        original = Path(analysis["source_path"])
        dest = dest_root / name
        dest.mkdir(parents=True, exist_ok=True)
        pages = len(fitz.open(original))
        for i in range(pages):
            o = render(original, i, SHEET_DPI)
            b = render(base_dir / "candidate.pdf", i, SHEET_DPI)
            f = render(final_dir / "candidate.pdf", i, SHEET_DPI)
            labelled(
                [o, b, f, diff_image(o, f)],
                ["Original", "Avant (reference)", "Apres (final)", "Diff final/original"],
            ).save(dest / f"page-{i + 1:03d}.png", optimize=True)
        own, ref = visual_set(analysis), visual_set(base_analysis)
        crops = []
        for tag, regions in (
            ("retire_final", ref - own),
            ("ajoute_final", own - ref),
            ("commun", own & ref),
        ):
            for pno, bbox in sorted(regions):
                s = CROP_DPI / 72
                box = tuple(
                    int(round(v * s)) for v in (bbox[0] - 4, bbox[1] - 4, bbox[2] + 4, bbox[3] + 4)
                )
                parts = [
                    render(p, pno - 1, CROP_DPI).crop(box)
                    for p in (original, base_dir / "candidate.pdf", final_dir / "candidate.pdf")
                ]
                parts = [
                    p.resize(
                        (
                            max(1, int(p.width * min(1.0, 260 / max(1, p.height)))),
                            max(1, int(p.height * min(1.0, 260 / max(1, p.height)))),
                        )
                    )
                    for p in parts
                ]
                crops.append(labelled(parts, [f"{tag} p{pno} orig", "avant", "apres"]))
        if crops:
            w = max(c.width for c in crops)
            h = sum(c.height + 8 for c in crops)
            sheet = Image.new("RGB", (w, h), (235, 235, 235))
            y = 0
            for c in crops:
                sheet.paste(c, (0, y))
                y += c.height + 8
            sheet.save(dest / "visual-regions-audit.png", optimize=True)
        print(
            name,
            "pages",
            pages,
            "visual_removed",
            len(ref - own),
            "visual_added",
            len(own - ref),
            "visual_common",
            len(own & ref),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
