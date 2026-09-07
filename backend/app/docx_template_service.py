"""Preenchimento de templates .docx por substituição de tokens."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path


def xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fill_docx_template(source: Path, replacements: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(source, "r") as reader, zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as writer:
        for item in reader.infolist():
            data = reader.read(item.filename)
            if item.filename == "word/document.xml":
                xml = data.decode("utf-8")
                for token, value in replacements.items():
                    safe = xml_escape(str(value))
                    xml = xml.replace(f"[{token}]", safe)
                    xml = xml.replace(token, safe)
                data = xml.encode("utf-8")
            writer.writestr(item, data)
    return buffer.getvalue()
