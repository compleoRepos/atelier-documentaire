"""RUN26 F25 - recovery of low-confidence OCR lines on a preprocessed copy.

Measured on the corpus (run25): 125 OCR blocks below 0.60 confidence were
sent to the model as if they were reliable; several were pure OCR noise
(short fragments unrelated to the printed words) while the scan clearly reads
an address and a date.

For every line of such a block the page raster (already a working copy, the
original file is never touched) is cropped, converted to grey, enlarged to a
fixed height, denoised (median 3), contrast-normalised and binarised (Otsu),
then re-read by Tesseract as one line (psm 7) in the block language. The new
reading replaces the line only when ALL of these hold (``accept_reading``):

* confidence >= 0.80 and at least 0.15 above the first reading;
* its length is at least 45 % of the length implied by the line box
  and 75 % of the first reading (a confident but truncated reading of 4
  letters for a 12-letter word is refused);
* it contains a letter or a digit and differs from the first reading beyond
  case, accents and punctuation (otherwise the first reading is kept);
* when the first reading was itself plausible (>= 0.45) its numbers -- digits
  and separators -- are unchanged ("1.234,56" vs "1 234.56" is a conflict
  between two plausible readings, left to a human);
* when it has words of 3+ letters, at least half are known words of the
  block or document languages, unless its confidence is >= 0.90;
* no other block covers more than 30 % of the line (ambiguous zone);
* no right-to-left script on either side (word order is not proven).

Two variants are read (binarised, and grey for shaded form cells where
Otsu turns the shading into ink); the more confident reading is kept. A
re-reading equal to the first one (beyond case, accents, punctuation) with
confidence >= 0.80 CONFIRMS it: the text is kept, the line confidence is
raised and the confirmation is recorded.

A block that stays below 0.60 without lexical evidence (``needs_review``) is
marked ``ocr_unreliable`` / ``low_confidence_not_recovered``: it is not sent
to a model and is listed for human review. Lines already rewritten by the
check-box rules are never re-read. Idempotent: an attempted line keeps its
``ocr_recovery`` record and is not re-read on a reused analysis.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from typing import Any

VERSION = "ocr-recovery-2"
RECOVER_BELOW = 0.60
REVIEW_BELOW = 0.60
ACCEPT_MIN = 0.80
ACCEPT_GAIN = 0.15
PLAUSIBLE_FIRST_READING = 0.45
MIN_LENGTH_SHARE = 0.45
MIN_FIRST_READING_SHARE = 0.75
CHAR_WIDTH_EM = 0.6
TARGET_HEIGHT_PX = 96
BORDER_PX = 12
OVERLAP_MAX = 0.30
LEXICAL_ZIPF = 2.5
LEXICAL_SHARE = 0.8
NEW_READING_KNOWN_SHARE = 0.5
NEW_READING_TRUSTED = 0.90
# F29 (run27): lexical plausibility of a CONFIDENT OCR reading. Tesseract can
# report 0.7-0.9 on a deformed reading; translating it means guessing the
# source. Calibrated on the corpus (counts only): among the 187 Latin-script
# OCR blocks of 8+ words, the readings below 0.70 are all deformed, the next
# ones (>= 0.75) are readable with sporadic errors, proper nouns or addresses.
# Limited to Latin script (the lexicon lookup of other scripts is not reliable
# here) and to blocks long enough for a share to be meaningful.
IMPLAUSIBLE_BELOW = 0.70
IMPLAUSIBLE_MIN_WORDS = 8
IMPLAUSIBLE_MIN_LATIN = 0.90

TESSERACT_CODES = {
    "ara": "ara",
    "ar": "ara",
    "deu": "deu",
    "de": "deu",
    "eng": "eng",
    "en": "eng",
    "fra": "fra",
    "fr": "fra",
    "ita": "ita",
    "it": "ita",
    "nld": "nld",
    "nl": "nld",
    "spa": "spa",
    "es": "spa",
}
_NUMERIC = re.compile(r"\d(?:[\d.,:/-]*\d)?")
_RTL = re.compile(r"[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]")
_WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
_LINE_SKIP_KEYS = ("ocr_text_raw", "checkbox_token", "ocr_noise", "ocr_recovery")

Reader = Callable[[Any, str], "tuple[str, float] | None"]


def _box_size(box: list[float]) -> tuple[float, float]:
    return max(0.0, float(box[2]) - float(box[0])), max(0.0, float(box[3]) - float(box[1]))


def expected_chars(box: list[float]) -> float:
    width, height = _box_size(box)
    return width / max(CHAR_WIDTH_EM * height, 1e-6)


def _compact(text: str) -> str:
    return "".join(ch for ch in text or "" if not ch.isspace())


def _fold(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch.casefold() for ch in decomposed if ch.isalnum())


def accept_reading(
    old_text: str,
    old_conf: float,
    new_text: str,
    new_conf: float,
    box: list[float],
    known_share: float | None = None,
) -> str:
    """Empty string when the new reading is accepted, else the refusal reason.

    ``known_share`` is the share of known words of the new reading (None when
    it has no word of 3+ letters or no lexicon is available)."""
    if not _compact(new_text):
        return "empty_reading"
    if not _fold(new_text):
        return "no_alphanumeric"
    if _RTL.search(old_text or "") or _RTL.search(new_text or ""):
        return "right_to_left_script"
    if _fold(new_text) == _fold(old_text):
        # Same letters and digits: a confirmation only if the numbers, with
        # their separators, are identical ("1.234,56" != "1 234.56").
        if _NUMERIC.findall(old_text or "") == _NUMERIC.findall(new_text):
            return "same_reading"
        return "numbers_disagree"
    if new_conf < ACCEPT_MIN or new_conf < old_conf + ACCEPT_GAIN:
        return "not_more_reliable"
    length = len(_compact(new_text))
    if length < MIN_LENGTH_SHARE * expected_chars(box):
        return "shorter_than_line"
    if length < MIN_FIRST_READING_SHARE * len(_compact(old_text)):
        return "shorter_than_first_reading"
    if old_conf >= PLAUSIBLE_FIRST_READING and _NUMERIC.findall(old_text or "") != _NUMERIC.findall(
        new_text
    ):
        return "numbers_disagree"
    if (
        known_share is not None
        and known_share < NEW_READING_KNOWN_SHARE
        and new_conf < NEW_READING_TRUSTED
    ):
        return "not_lexically_supported"
    return ""


def _overlap_share(box: list[float], other: list[float]) -> float:
    width = min(box[2], other[2]) - max(box[0], other[0])
    height = min(box[3], other[3]) - max(box[1], other[1])
    if width <= 0 or height <= 0:
        return 0.0
    area = max((box[2] - box[0]) * (box[3] - box[1]), 1e-6)
    return width * height / area


def preprocess_line(rgb: Any, box: list[float], scale: float) -> list[Any]:
    """Enlarged, denoised, contrast-normalised crop: [Otsu-binarised, grey]."""
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps

    height, width = rgb.shape[:2]
    px = [float(v) * scale for v in box]
    pad = 0.15 * (px[3] - px[1])
    x0, y0 = max(0, int(px[0] - pad)), max(0, int(px[1] - pad))
    x1, y1 = min(width, int(round(px[2] + pad))), min(height, int(round(px[3] + pad)))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return []
    grey = Image.fromarray(np.asarray(rgb[y0:y1, x0:x1]).mean(axis=2).astype(np.uint8))
    ratio = TARGET_HEIGHT_PX / max(1, grey.height)
    grey = grey.resize((max(1, int(grey.width * ratio)), TARGET_HEIGHT_PX), Image.LANCZOS)
    grey = ImageOps.autocontrast(grey.filter(ImageFilter.MedianFilter(3)), cutoff=1)
    values = np.asarray(grey)
    hist = np.bincount(values.ravel(), minlength=256).astype(float)
    total = float(values.size)
    levels = np.arange(256, dtype=float)
    weight = np.cumsum(hist)
    mass = np.cumsum(levels * hist)
    valid = (weight > 0) & (weight < total)
    if not valid.any():
        return []
    mean_low = np.where(valid, mass / np.maximum(weight, 1e-9), 0.0)
    mean_high = np.where(valid, (mass[-1] - mass) / np.maximum(total - weight, 1e-9), 0.0)
    between = np.where(valid, weight * (total - weight) * (mean_low - mean_high) ** 2, -1.0)
    threshold = int(np.argmax(between))
    binary = Image.fromarray(np.where(values > threshold, 255, 0).astype(np.uint8))
    return [
        ImageOps.expand(binary, border=BORDER_PX, fill=255),
        ImageOps.expand(grey, border=BORDER_PX, fill=255),
    ]


def tesseract_reader(image: Any, lang: str) -> tuple[str, float] | None:
    try:
        import pytesseract

        data = pytesseract.image_to_data(
            image,
            lang=lang,
            config="--psm 7",
            output_type=pytesseract.Output.DICT,
            timeout=30,
        )
    except Exception:  # noqa: BLE001 - an unavailable reader recovers nothing
        return None
    words = [
        (str(text), float(conf))
        for text, conf in zip(data.get("text", []), data.get("conf", []), strict=False)
        if str(text).strip() and float(conf) >= 0
    ]
    if not words:
        return "", 0.0
    chars = sum(len(text) for text, _ in words)
    return " ".join(text for text, _ in words), sum(len(t) * c for t, c in words) / chars / 100.0


def available_codes() -> set[str]:
    try:
        import pytesseract

        return set(pytesseract.get_languages(config=""))
    except Exception:  # noqa: BLE001
        return set()


def block_language(block: dict[str, Any], languages: list[str], available: set[str]) -> str | None:
    own = TESSERACT_CODES.get(str(block.get("language") or "").lower())
    if own and own in available:
        return own
    doc = [TESSERACT_CODES.get(str(code).lower()) for code in languages]
    usable = [code for code in dict.fromkeys(doc) if code and code in available]
    return "+".join(usable) or None


def _recompute(block: dict[str, Any], lines: list[dict[str, Any]]) -> None:
    from .segmentation import join_line_texts

    texts = [str(line.get("text") or "") for line in lines]
    chars = [max(1, len(text)) for text in texts]
    confs = [float(line.get("confidence") or 0.0) for line in lines]
    block.setdefault("ocr_text_initial", block.get("text"))
    block["text"] = join_line_texts(texts)
    block["confidence"] = round(
        sum(c * n for c, n in zip(confs, chars, strict=True)) / sum(chars), 4
    )
    block["min_line_confidence"] = round(min(confs), 4)


def recover_block(
    block: dict[str, Any],
    page_blocks: list[dict[str, Any]],
    rgb: Any,
    scale: float,
    languages: list[str],
    stats: dict[str, Any],
    *,
    reader: Reader | None = None,
    available: set[str] | None = None,
) -> int:
    """Re-read the low-confidence lines of one OCR block; returns lines replaced."""
    conf = block.get("confidence")
    lines = block.get("source_lines") or []
    if (
        conf is None
        or float(conf) >= RECOVER_BELOW
        or not lines
        or block.get("ocr_unreliable")
        or block.get("protected")
    ):
        return 0
    reader = reader or tesseract_reader
    lang = block_language(
        block, languages, available if available is not None else available_codes()
    )
    if not lang:
        stats["ocr_recovery_no_language_model"] = stats.get("ocr_recovery_no_language_model", 0) + 1
        return 0
    stats["ocr_recovery_blocks_tried"] = stats.get("ocr_recovery_blocks_tried", 0) + 1
    others = [b for b in page_blocks if b is not block and b.get("bbox")]
    replaced = confirmed_lines = 0
    for line in lines:
        box = line.get("bbox")
        old_conf = float(line.get("confidence") or 0.0)
        if not box or old_conf >= RECOVER_BELOW or any(key in line for key in _LINE_SKIP_KEYS):
            continue
        stats["ocr_recovery_lines_tried"] = stats.get("ocr_recovery_lines_tried", 0) + 1
        old_text = str(line.get("text") or "")
        reason = ""
        if any(_overlap_share(box, other["bbox"]) > OVERLAP_MAX for other in others):
            reason = "ambiguous_zone"
            new_text, new_conf = "", 0.0
        else:
            readings = [reader(image, lang) for image in preprocess_line(rgb, box, scale)]
            readings = [r for r in readings if r is not None]
            new_text, new_conf = max(readings, key=lambda r: r[1]) if readings else ("", 0.0)
            if not readings:
                reason = "reader_unavailable"
        reason = reason or accept_reading(
            old_text,
            old_conf,
            new_text,
            new_conf,
            box,
            known_share(new_text, block.get("language"), languages),
        )
        confirmed = reason == "same_reading" and new_conf >= ACCEPT_MIN
        line["ocr_recovery"] = {
            "method": VERSION,
            "initial_confidence": round(old_conf, 4),
            "reread_confidence": round(float(new_conf), 4),
            "accepted": not reason,
            "reason": "confirmed" if confirmed else reason or "accepted",
        }
        if confirmed:
            stats["ocr_recovery_lines_confirmed"] = stats.get("ocr_recovery_lines_confirmed", 0) + 1
            line["confidence"] = round(max(old_conf, float(new_conf)), 4)
            confirmed_lines += 1
            continue
        key = f"ocr_recovery_refused_{reason}" if reason else "ocr_recovery_lines_recovered"
        stats[key] = stats.get(key, 0) + 1
        if reason:
            continue
        line["ocr_text_initial"] = old_text
        line["text"] = new_text
        line["confidence"] = round(float(new_conf), 4)
        line["provenance"] = "ocr:tesseract:recovered"
        replaced += 1
    if replaced or confirmed_lines:
        _recompute(block, lines)
    if confirmed_lines:
        block["ocr_confirmed_lines"] = confirmed_lines
    if replaced:
        block["ocr_recovered_lines"] = replaced
        stats["ocr_recovery_blocks_changed"] = stats.get("ocr_recovery_blocks_changed", 0) + 1
    return replaced


def _isos(language: str | None, languages: list[str], *, widen: bool) -> list[str]:
    from .language_evidence import _ISO

    own = _ISO.get(str(language or "").lower())
    codes = [own] if own and not widen else [own, *(_ISO.get(str(c).lower()) for c in languages)]
    return [iso for iso in dict.fromkeys(codes) if iso]


def known_share(text: str, language: str | None, languages: list[str]) -> float | None:
    """Share of words (3+ letters) known in the block or document languages."""
    from .language_evidence import _zipf, available

    words = [word.lower() for word in _WORD.findall(text or "")]
    isos = _isos(language, languages, widen=True)
    if not words or not isos or not available():
        return None
    known = sum(1 for word in words if max(_zipf(word, iso) for iso in isos) >= LEXICAL_ZIPF)
    return known / len(words)


def lexically_supported(text: str, language: str | None, languages: list[str]) -> bool:
    """At least one word and >= 80 % of words (3+ letters) are known words
    (zipf >= 2.5) of the block language (else the document languages)."""
    from .language_evidence import _ISO, _zipf, available

    if not available():
        return False
    isos = [_ISO.get(str(language or "").lower())]
    if not isos[0]:
        isos = [_ISO.get(str(code).lower()) for code in languages]
    isos = [iso for iso in dict.fromkeys(isos) if iso]
    words = [word.lower() for word in _WORD.findall(text or "")]
    if not words or not isos:
        return False
    known = sum(1 for word in words if max(_zipf(word, iso) for iso in isos) >= LEXICAL_ZIPF)
    return known / len(words) >= LEXICAL_SHARE


def needs_review(block: dict[str, Any], languages: list[str]) -> bool:
    conf = block.get("confidence")
    if conf is None or float(conf) >= REVIEW_BELOW or not block.get("source_lines"):
        return False
    return not lexically_supported(str(block.get("text") or ""), block.get("language"), languages)


def latin_share(text: str) -> float:
    letters = [ch for ch in text or "" if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for ch in letters if "LATIN" in unicodedata.name(ch, "")) / len(letters)


def lexically_implausible(block: dict[str, Any], languages: list[str]) -> bool:
    """F29 (run27): a measured OCR reading whose words are mostly unknown in
    the block and document languages is not translated (human review).

    ``False`` when the lexicon is unavailable or the rule does not apply
    (non-Latin script, fewer than 8 words, no measured confidence, block
    language undetected or unknown to the lexicon): the other
    OCR gates still apply; this one never marks a block reliable.
    """
    text = str(block.get("text") or "")
    if not block.get("source_lines") or block.get("confidence") is None:
        return False
    if (
        len(_WORD.findall(text)) < IMPLAUSIBLE_MIN_WORDS
        or latin_share(text) < IMPLAUSIBLE_MIN_LATIN
    ):
        return False
    # The block language must be detected and known to the lexicon: a correct
    # reading in an undetected foreign language is not a deformed reading.
    if not _isos(block.get("language"), [], widen=False):
        return False
    share = known_share(text, block.get("language"), languages)
    return share is not None and share < IMPLAUSIBLE_BELOW
