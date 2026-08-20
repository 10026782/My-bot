"""Tiny deterministic single-page PDF generator for the Stirling-PDF POC --
no binary files committed, no PDF-authoring dependency. Produces a real,
correctly-structured PDF (exact xref byte offsets) that a real PDF engine
(PDFBox/JPDFium, i.e. Stirling-PDF itself) can actually open and merge, not
just something that passes a magic-byte check."""

from __future__ import annotations


def minimal_pdf_bytes(*, width: int = 200, height: int = 200) -> bytes:
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        f"<</Type/Page/Parent 2 0 R/MediaBox[0 0 {width} {height}]/Resources<<>>>>".encode(),
    ]
    header = b"%PDF-1.4\n"
    body = bytearray(header)
    pos = len(header)
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(pos)
        entry = f"{index} 0 obj".encode() + obj + b"endobj\n"
        body += entry
        pos += len(entry)
    xref_offset = pos
    xref = bytearray(f"xref\n0 {len(objects) + 1}\n".encode())
    xref += b"0000000000 65535 f \n"
    for offset in offsets:
        xref += f"{offset:010d} 00000 n \n".encode()
    trailer = f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return bytes(body) + bytes(xref) + trailer
