import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "assets" / "legal-manuals"
manuals = {
    "manual-sdc.docx": "SDC — Manual do Produto LETTER",
    "manual-flash-capital.docx": "Flash Capital — Manual do Produto LETTER",
    "manual-flash-invest.docx": "Flash Invest — Manual do Produto LETTER",
    "manual-quitcon.docx": "QuitCon — Manual do Produto LETTER",
    "manual-lease-equity.docx": "Lease Equity — Manual do Produto LETTER",
    "manual-carta-contemplada.docx": "Carta Contemplada — Manual do Produto LETTER",
    "manual-rede-parceiro.docx": "Rede LETTER — Manual do Parceiro",
}

content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>"""


def make_docx(text: str, path: Path) -> None:
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    doc = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body><w:p><w:r><w:t>{safe}</w:t></w:r></w:p></w:body></w:document>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/_rels/document.xml.rels", doc_rels)
        archive.writestr("word/document.xml", doc)


if __name__ == "__main__":
    for name, title in manuals.items():
        target = root / name
        make_docx(title, target)
        print(f"created {name}")
