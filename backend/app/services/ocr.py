"""Text extraction: native PDF text first, Tesseract OCR (English + Hindi) as fallback.

If neither is possible (e.g. tesseract missing) we return method='unavailable' and the
pipeline asks the patient to verify manually — we never fabricate text.
"""
from __future__ import annotations

import io
import logging
import re
import shutil
from dataclasses import dataclass

from app.core.config import get_settings

log = logging.getLogger(__name__)

MIN_NATIVE_CHARS = 80


@dataclass
class OCRResult:
    text: str
    method: str  # pdf_text | pdf_ocr | image_ocr | unavailable
    pages: int
    mean_confidence: float | None = None
    warnings: list[str] | None = None


def _tesseract_available() -> bool:
    settings = get_settings()
    if settings.tesseract_cmd:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        return True
    return shutil.which("tesseract") is not None


LOW_CONFIDENCE = 0.75


def _preprocess(img):  # noqa: ANN001
    from PIL import ImageOps

    img = ImageOps.exif_transpose(img)
    img = img.convert("L")
    if img.width < 1600:
        scale = 1600 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    return ImageOps.autocontrast(img)


def _deskew_angle(img) -> float:  # noqa: ANN001
    """Angle (degrees) that makes text lines horizontal: maximise the variance of row ink sums."""
    from PIL import Image

    small = img.copy()
    small.thumbnail((900, 900))
    ink = small.point(lambda v: 255 if v < 140 else 0)
    best, best_angle = -1.0, 0.0
    for tenth in range(-100, 101, 5):
        rot = ink.rotate(tenth / 10, resample=Image.BILINEAR)
        rows = rot.resize((1, rot.height), Image.BOX).tobytes()
        mean = sum(rows) / len(rows)
        score = sum((r - mean) ** 2 for r in rows)
        if score > best:
            best, best_angle = score, tenth / 10
    return best_angle


def _enhance(img):  # noqa: ANN001
    """For phone photos: flatten shadows (divide out the paper background), then straighten the page."""
    from PIL import Image, ImageChops, ImageFilter, ImageOps

    if img.width < 2200:
        scale = 2200 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    background = img.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(25))
    flat = Image.eval(ImageChops.subtract(background, img), lambda v: 255 - v)
    angle = _deskew_angle(flat)
    if abs(angle) >= 0.5:
        flat = flat.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=255)
    return ImageOps.autocontrast(flat, cutoff=1)


def _ocr_pass(img, langs: str) -> tuple[str, float | None]:  # noqa: ANN001
    """One Tesseract run; lines are rebuilt from the word boxes so we don't OCR the page twice."""
    import pytesseract

    data = pytesseract.image_to_data(img, lang=langs, config="--psm 6", output_type=pytesseract.Output.DICT)
    lines: dict[tuple[int, int, int], list[str]] = {}
    confs = []
    for i, word in enumerate(data["text"]):
        if str(data["conf"][i]) in ("-1", "-1.0"):
            continue
        confs.append(float(data["conf"][i]))
        if word.strip():
            lines.setdefault((data["block_num"][i], data["par_num"][i], data["line_num"][i]), []).append(word)
    text = "\n".join(" ".join(ws) for _, ws in sorted(lines.items()))
    return text, (sum(confs) / len(confs) / 100 if confs else None)


def _mostly_latin(text: str) -> bool:
    deva = len(re.findall(r"[\u0900-\u097F]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return latin > 0 and deva / (deva + latin) < 0.08


def _better(a: tuple[str, float | None], b: tuple[str, float | None], margin: float) -> tuple[str, float | None]:
    return b if b[1] is not None and (a[1] is None or b[1] > a[1] + margin) else a


def _ocr_image(img) -> tuple[str, float | None]:  # noqa: ANN001
    langs = get_settings().ocr_languages
    base = _preprocess(img)
    try:
        best = _ocr_pass(base, langs)
        # Mixed eng+hin models sometimes read Latin glyphs as Devanagari ("HbA1c" → "1081८"). If the page is
        # essentially English, prefer the Latin-only read unless it is clearly worse.
        latin_langs = "+".join(code for code in langs.split("+") if code in ("eng", "lat")) or None
        if latin_langs and latin_langs != langs and _mostly_latin(best[0]):
            best = _better(best, _ocr_pass(base, latin_langs), -0.03)
            if best[1] is not None:
                langs = latin_langs if _mostly_latin(best[0]) else langs
        if best[1] is not None and best[1] < LOW_CONFIDENCE:
            best = _better(best, _ocr_pass(_enhance(base), langs), 0.05)
        return best
    except Exception:  # noqa: BLE001
        import pytesseract

        return pytesseract.image_to_string(base, lang=langs, config="--psm 6"), None


def _page_text(page) -> str:  # noqa: ANN001
    """Layout mode keeps table rows on one line (name · value · unit · range); fall back to plain mode."""
    try:
        txt = page.extract_text(extraction_mode="layout") or ""
    except Exception:  # noqa: BLE001
        txt = ""
    if len(txt.strip()) < 20:
        txt = page.extract_text() or ""
    txt = re.sub(r"[ \t]{4,}", "    ", txt)
    return re.sub(r"\n{3,}", "\n\n", txt)


def extract_text(data: bytes, mime_type: str) -> OCRResult:
    warnings: list[str] = []
    if mime_type == "application/pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = len(reader.pages)
        native = "\n".join(_page_text(p) for p in reader.pages).strip()
        if len(native) >= MIN_NATIVE_CHARS:
            return OCRResult(native, "pdf_text", pages, 0.98)
        if not _tesseract_available():
            return OCRResult(native, "unavailable", pages, None, ["Scanned PDF and OCR engine not installed"])
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        texts, confs = [], []
        for i in range(min(len(pdf), 10)):
            img = pdf[i].render(scale=2.5).to_pil()
            t, c = _ocr_image(img)
            texts.append(t)
            if c is not None:
                confs.append(c)
        if len(pdf) > 10:
            warnings.append("Only the first 10 pages were read")
        return OCRResult("\n".join(texts).strip(), "pdf_ocr", pages, sum(confs) / len(confs) if confs else None, warnings)

    if mime_type.startswith("image/"):
        if not _tesseract_available():
            return OCRResult("", "unavailable", 1, None, ["OCR engine not installed"])
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        text, conf = _ocr_image(img)
        if conf is not None and conf < 0.6:
            warnings.append("Image is hard to read — please check every field carefully")
        return OCRResult(text.strip(), "image_ocr", 1, conf, warnings)

    return OCRResult("", "unavailable", 0, None, [f"Unsupported file type {mime_type}"])
