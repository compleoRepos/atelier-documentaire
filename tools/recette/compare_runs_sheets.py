"""Multi-run visual comparison sheets (run18 §12). Contains document images:
the destination must be private; a destination inside this repository is refused.

Usage:
  compare_runs_sheets.py --run baseline=<out> --run run17=<out> --run run18=<out> --dest <dir>

Per page: Original | each run's candidate | diff(last run vs original) |
diff(last run vs previous run). Red pixels = grey level differs by > 40.

Per document, visual-region audit, same method for every run: the union of the
protected visual regions (stamps, logos, signatures, photos, monochrome
candidates) detected by ANY run is cropped in the original and in every
candidate; for each crop the share of pixels changed against the original is
measured. A region whose changed share exceeds ALTERED_SHARE in a run is
listed as altered for that run (``visual-regions.json``, counters only) and
shown on ``visual-regions-audit.png`` for human review.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SHEET_DPI = 80
CROP_DPI = 150
ALTERED_SHARE = 0.02
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
SMALL = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
REPO_ROOT = Path(__file__).resolve().parents[2]


def render(pdf: Path, index: int, dpi: int) -> Image.Image:
    doc = fitz.open(pdf)
    try:
        if index >= len(doc):
            return Image.new("RGB", (10, 10), "white")
        pix = doc[index].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()


def changed_mask(a: Image.Image, b: Image.Image) -> np.ndarray:
    x = np.asarray(a.convert("L"), dtype=int)
    y = np.asarray(b.convert("L").resize(a.size), dtype=int)
    return np.abs(x - y) > 40


def diff_image(a: Image.Image, b: Image.Image) -> Image.Image:
    x = np.asarray(a.convert("L"), dtype=int)
    d = changed_mask(a, b)
    base = np.stack([x] * 3, axis=2).astype(np.uint8) // 2 + 127
    base[d] = [220, 30, 30]
    return Image.fromarray(base)


def labelled(images: list[Image.Image], labels: list[str], font=FONT) -> Image.Image:
    w = sum(i.width for i in images) + 10 * (len(images) - 1)
    h = max(i.height for i in images) + 30
    sheet = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(sheet)
    x = 0
    for img, label in zip(images, labels, strict=True):
        sheet.paste(img, (x, 30))
        draw.text((x + 4, 6), label, fill=(0, 0, 0), font=font)
        x += img.width + 10
    return sheet


def visual_regions(analysis: dict) -> set[tuple]:
    out = set()
    for r in analysis.get("protected_visual_regions") or []:
        bbox = r.get("bbox")
        if not bbox or r.get("subtype") in {None, "text"}:
            continue
        out.add((int(r["page"]), tuple(round(float(v), 1) for v in bbox), str(r.get("subtype"))))
    return out


def _merge(regions: set[tuple]) -> list[tuple]:
    """Drop near-duplicates (same page, IoU > 0.7) coming from different runs."""
    kept: list[tuple] = []
    for page, bbox, subtype in sorted(regions):
        dup = False
        for kp, kb, _ks in kept:
            if kp != page:
                continue
            ix = max(0.0, min(bbox[2], kb[2]) - max(bbox[0], kb[0]))
            iy = max(0.0, min(bbox[3], kb[3]) - max(bbox[1], kb[1]))
            inter = ix * iy
            union = (
                (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                + (kb[2] - kb[0]) * (kb[3] - kb[1])
                - inter
            )
            if union > 0 and inter / union > 0.7:
                dup = True
                break
        if not dup:
            kept.append((page, bbox, subtype))
    return kept


def _fit(img: Image.Image, height: int = 220) -> Image.Image:
    s = min(1.0, height / max(1, img.height), 420 / max(1, img.width))
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", action="append", required=True, help="label=out_dir, in order")
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--only", action="append")
    args = ap.parse_args()
    runs = [(spec.split("=", 1)[0], Path(spec.split("=", 1)[1])) for spec in args.run]
    dest_root = args.dest.resolve()
    if dest_root == REPO_ROOT or REPO_ROOT in dest_root.parents:
        print("REFUSED: destination inside the repository", file=sys.stderr)
        return 2
    dest_root.mkdir(parents=True, exist_ok=True)
    last_label, last_root = runs[-1]
    for last_dir in sorted(last_root.glob("DOC-0*")):
        name = last_dir.name
        if args.only and name not in args.only:
            continue
        dirs = [(label, root / name) for label, root in runs]
        missing = [label for label, d in dirs if not (d / "candidate.pdf").exists()]
        if missing:
            print(name, "SKIPPED_MISSING_CANDIDATE", missing)
            continue
        analyses = {label: json.load(open(d / "analysis.json")) for label, d in dirs}
        original = Path(analyses[last_label]["source_path"])
        dest = dest_root / name
        dest.mkdir(parents=True, exist_ok=True)
        pages = len(fitz.open(original))
        for i in range(pages):
            o = render(original, i, SHEET_DPI)
            cands = [render(d / "candidate.pdf", i, SHEET_DPI) for _l, d in dirs]
            images = [o, *cands, diff_image(o, cands[-1])]
            labels = ["Original", *[label for label, _d in dirs], f"Diff {last_label}/original"]
            if len(cands) >= 2:
                images.append(diff_image(cands[-2], cands[-1]))
                labels.append(f"Diff {last_label}/{dirs[-2][0]}")
            labelled(images, labels).save(dest / f"page-{i + 1:03d}.png", optimize=True)
        union: set[tuple] = set()
        for a in analyses.values():
            union |= visual_regions(a)
        regions = _merge(union)
        report = []
        crops = []
        cache: dict[tuple, Image.Image] = {}

        def page_img(pdf: Path, pno: int, _cache=cache) -> Image.Image:
            key = (str(pdf), pno)
            if key not in _cache:
                _cache[key] = render(pdf, pno - 1, CROP_DPI)
            return _cache[key]

        for pno, bbox, subtype in regions:
            s = CROP_DPI / 72
            box = tuple(int(round(v * s)) for v in bbox)
            if box[2] - box[0] < 2 or box[3] - box[1] < 2:
                continue
            orig_crop = page_img(original, pno).crop(box)
            entry = {"page": pno, "subtype": subtype, "changed_share": {}, "protected_in": []}
            parts, plabels = [_fit(orig_crop)], [f"p{pno} {subtype[:18]} orig"]
            for label, d in dirs:
                crop = page_img(d / "candidate.pdf", pno).crop(box)
                share = float(changed_mask(orig_crop, crop).mean())
                entry["changed_share"][label] = round(share, 4)
                if any(
                    r[0] == pno and r[2] == subtype and abs(r[1][0] - bbox[0]) < 6
                    for r in visual_regions(analyses[label])
                ):
                    entry["protected_in"].append(label)
                parts.append(_fit(crop))
                plabels.append(f"{label} {share:.1%}")
            entry["altered_in"] = [
                label for label, v in entry["changed_share"].items() if v > ALTERED_SHARE
            ]
            report.append(entry)
            if entry["altered_in"] or set(entry["protected_in"]) != {lbl for lbl, _ in dirs}:
                crops.append(labelled(parts, plabels, font=SMALL))
        if crops:
            w = max(c.width for c in crops)
            h = sum(c.height + 8 for c in crops)
            sheet = Image.new("RGB", (w, h), (235, 235, 235))
            y = 0
            for c in crops:
                sheet.paste(c, (0, y))
                y += c.height + 8
            sheet.save(dest / "visual-regions-audit.png", optimize=True)
        summary = {
            "regions": len(report),
            "altered": {label: sum(label in e["altered_in"] for e in report) for label, _d in dirs},
            "threshold_changed_share": ALTERED_SHARE,
            "regions_detail": report,
        }
        (dest / "visual-regions.json").write_text(json.dumps(summary, indent=1))
        print(
            name, "pages", pages, "regions", len(report), "altered", summary["altered"], flush=True
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
