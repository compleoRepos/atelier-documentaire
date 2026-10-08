from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from fastapi import HTTPException

ALLOWED = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def _bad(code: str, detail: str, status_code: int = 415) -> None:
    raise HTTPException(status_code=status_code, detail={"code": code, "message": detail})


def validate_upload(
    data: bytes, filename: str, content_type: str | None, max_pages: int = 200
) -> tuple[str, str]:
    if not data:
        _bad("EMPTY_FILE", "Fichier vide", 422)
    ext = Path(filename or "").suffix.lower().lstrip(".")
    if ext not in ALLOWED:
        _bad("UNSUPPORTED_FORMAT", "Format non pris en charge")
    ctype = (content_type or "").lower().split(";", 1)[0]
    if ctype != ALLOWED[ext]:
        _bad("MIME_MISMATCH", "Type MIME incompatible avec l'extension")
    if ext == "pdf":
        _validate_pdf(data, max_pages)
    elif ext == "docx":
        _validate_docx(data)
    else:
        _validate_image(data, ext)
    return ext, ALLOWED[ext]


def _validate_pdf(data: bytes, max_pages: int) -> None:
    if not data.startswith(b"%PDF-"):
        _bad("MAGIC_MISMATCH", "Signature PDF absente")
    if re.search(rb"/(?:JavaScript|JS)(?:\s|/|>)", data, re.I):
        _bad("PDF_JAVASCRIPT", "JavaScript PDF interdit")
    if re.search(rb"/(?:EmbeddedFile|Filespec|EmbeddedFiles|AA|OpenAction)(?:\s|/|>)", data):
        _bad("PDF_ACTIVE_CONTENT", "Pièce jointe ou action PDF interdite")
    try:
        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
        if doc.is_encrypted:
            _bad("PDF_ENCRYPTED", "PDF chiffré non accepté", 422)
        if doc.page_count > max_pages:
            _bad("PAGE_LIMIT", f"Le document dépasse {max_pages} pages", 422)
        if doc.xref_length() > 50000:
            _bad("PDF_OBJECT_LIMIT", "Trop d'objets PDF", 422)
        for xref in range(1, doc.xref_length()):
            obj = doc.xref_object(xref, compressed=False)
            # Les noms PDF peuvent échapper chaque caractère avec #xx.
            obj = re.sub(r"#([0-9A-Fa-f]{2})", lambda match: chr(int(match.group(1), 16)), obj)
            if re.search(
                r"/(?:JavaScript|JS|EmbeddedFile|Filespec|EmbeddedFiles|AA|OpenAction|Launch|RichMedia)(?:\s|/|>)",
                obj,
                re.I,
            ):
                _bad("PDF_ACTIVE_CONTENT", "Action ou contenu PDF actif interdit", 422)
        doc.close()
    except HTTPException:
        raise
    except Exception:
        _bad("PDF_INVALID", "PDF illisible", 422)


def _validate_docx(data: bytes) -> None:
    if not data.startswith(b"PK\x03\x04"):
        _bad("MAGIC_MISMATCH", "Conteneur DOCX invalide")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > 2000:
                _bad("ZIP_ENTRIES", "Trop d'entrées ZIP", 422)
            total = 0
            names = set()
            for info in infos:
                name = info.filename.replace("\\", "/")
                names.add(name)
                if name.startswith("/") or any(part == ".." for part in name.split("/")):
                    _bad("ZIP_TRAVERSAL", "Chemin ZIP interdit", 422)
                if info.file_size > 50 * 1024 * 1024:
                    _bad("ZIP_ENTRY_LIMIT", "Entrée ZIP trop volumineuse", 422)
                total += info.file_size
                if total > 200 * 1024 * 1024 or (
                    info.compress_size and info.file_size / info.compress_size > 1000
                ):
                    _bad("ZIP_BOMB", "Ratio de compression ZIP dangereux", 422)
                if name.lower().endswith((".exe", ".dll", ".js", ".vbs", ".bat", ".cmd", ".ps1")):
                    _bad("ACTIVE_CONTENT", "Contenu actif DOCX interdit", 422)
                if name.lower().startswith("word/embeddings/"):
                    _bad("EMBEDDED_OBJECT", "Objet incorporé DOCX interdit", 422)
                if "vbaproject" in name.lower() or name.lower().endswith(".vba"):
                    _bad("DOCX_MACRO", "Macro DOCX interdite", 422)
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                _bad("DOCX_INVALID", "DOCX incomplet", 422)
            from xml.etree.ElementTree import ParseError

            from defusedxml.common import DefusedXmlException
            from defusedxml.ElementTree import fromstring

            try:
                for name in names:
                    if name.lower().endswith(".rels"):
                        root = fromstring(archive.read(name))
                        for node in root.iter():
                            if any(
                                key.rsplit("}", 1)[-1].casefold() == "targetmode"
                                and value.casefold() == "external"
                                for key, value in node.attrib.items()
                            ):
                                _bad("EXTERNAL_RELATION", "Relation externe DOCX interdite", 422)
                content_types = fromstring(archive.read("[Content_Types].xml"))
                if any(
                    "macroenabled" in value.lower() or "vbaproject" in value.lower()
                    for node in content_types.iter()
                    for value in node.attrib.values()
                ):
                    _bad("DOCX_MACRO", "Type de contenu macro DOCX interdit", 422)
            except (ParseError, DefusedXmlException):
                _bad("DOCX_XML_INVALID", "XML DOCX invalide ou dangereux", 422)
    except HTTPException:
        raise
    except (zipfile.BadZipFile, KeyError):
        _bad("DOCX_INVALID", "Conteneur DOCX illisible", 422)


def _validate_image(data: bytes, ext: str) -> None:
    magic = (ext == "png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or (
        ext in {"jpg", "jpeg"} and data.startswith(b"\xff\xd8\xff")
    )
    if not magic:
        _bad("MAGIC_MISMATCH", "Signature image incompatible")
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            if (
                image.width * image.height > 80_000_000
                or image.width > 12000
                or image.height > 12000
            ):
                _bad("IMAGE_DIMENSIONS", "Dimensions image excessives", 422)
            image.verify()
    except HTTPException:
        raise
    except Exception:
        _bad("IMAGE_INVALID", "Image illisible", 422)
