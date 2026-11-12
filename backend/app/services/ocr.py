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


def _preprocess(img):  # noqa: ANN001
    from PIL import ImageOps

    img = ImageOps.exif_transpose(img)
    img = img.convert("L")
    if img.width < 1600:
        scale = 1600 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    return ImageOps.autocontrast(img)


def _ocr_image(img) -> tuple[str, float | None]:  # noqa: ANN001
    import pytesseract

    langs = get_settings().ocr_languages
    img = _preprocess(img)
    try:
        data = pytesseract.image_to_data(img, lang=langs, config="--psm 6", output_type=pytesseract.Output.DICT)
        confs = [float(c) for c in data["conf"] if str(c) not in ("-1", "-1.0")]
        mean = sum(confs) / len(confs) / 100 if confs else None
    except Exception:  # noqa: BLE001
        mean = None
    text = pytesseract.image_to_string(img, lang=langs, config="--psm 6")
    return text, mean


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
