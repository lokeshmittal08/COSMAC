"""Build small Word, PDF and image files in memory for tests and demos."""

from __future__ import annotations

import io
import zipfile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _run(text: str, props: str = "") -> str:
    return f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{text}</w:t></w:r>'


def make_docx(
    paragraphs: list[str],
    *,
    hidden: str | None = None,
    white: str | None = None,
    tiny: str | None = None,
    deleted: str | None = None,
    comment: str | None = None,
    title: str | None = None,
    header: str | None = None,
) -> bytes:
    body = "".join(f"<w:p>{_run(p)}</w:p>" for p in paragraphs)
    if hidden:
        body += f"<w:p>{_run(hidden, '<w:vanish/>')}</w:p>"
    if white:
        body += "<w:p>" + _run(white, '<w:color w:val="FFFFFF"/>') + "</w:p>"
    if tiny:
        body += "<w:p>" + _run(tiny, '<w:sz w:val="2"/>') + "</w:p>"
    if deleted:
        body += f'<w:p><w:del w:id="1" w:author="a"><w:r><w:delText>{deleted}</w:delText></w:r></w:del></w:p>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(
            "word/document.xml", f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'
        )
        if comment:
            z.writestr(
                "word/comments.xml",
                f'<w:comments xmlns:w="{W}"><w:comment w:id="0"><w:p>{_run(comment)}</w:p></w:comment></w:comments>',
            )
        if header:
            z.writestr(
                "word/header1.xml", f'<w:hdr xmlns:w="{W}"><w:p>{_run(header)}</w:p></w:hdr>'
            )
        if title:
            z.writestr(
                "docProps/core.xml",
                '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                f'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{title}</dc:title></cp:coreProperties>',
            )
    return buffer.getvalue()


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(
    lines: list[str],
    *,
    tiny: str | None = None,
    title: str | None = None,
    annotation: str | None = None,
) -> bytes:
    """A one-page PDF with a text layer. ``tiny`` is drawn at 0.5 point."""
    ops = ["BT", "/F1 12 Tf", "72 720 Td", "16 TL"]
    for line in lines:
        ops += [f"({_esc(line)}) Tj", "T*"]
    if tiny:
        ops += ["/F1 0.5 Tf", f"({_esc(tiny)}) Tj", "T*", "/F1 12 Tf"]
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")
    annots = "/Annots [6 0 R] " if annotation else ""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R {annots}/Resources << /Font << /F1 5 0 R >> >> >>".encode(),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    if annotation:
        objects.append(
            f"<< /Type /Annot /Subtype /Text /Rect [10 10 30 30] /Contents ({_esc(annotation)}) >>".encode()
        )
    info_ref = b""
    if title:
        objects.append(f"<< /Title ({_esc(title)}) >>".encode())
        info_ref = f" /Info {len(objects)} 0 R".encode()
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode()
        + b" /Root 1 0 R"
        + info_ref
        + b" >>\n"
    )
    out += f"startxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def make_png(lines: list[str], *, faint: str | None = None, text_chunk: str | None = None) -> bytes:
    """An image of text. ``faint`` is drawn almost white on white."""
    from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

    try:
        font = ImageFont.load_default(size=30)
    except TypeError:  # older Pillow
        font = ImageFont.load_default()
    height = 80 + 60 * (len(lines) + (1 if faint else 0))
    image = Image.new("RGB", (1500, height), "white")
    draw = ImageDraw.Draw(image)
    y = 40
    for line in lines:
        draw.text((40, y), line, fill="black", font=font)
        y += 60
    if faint:
        draw.text((40, y), faint, fill=(246, 246, 246), font=font)
    info = PngImagePlugin.PngInfo()
    if text_chunk:
        info.add_text("Description", text_chunk)
    buffer = io.BytesIO()
    image.save(buffer, "PNG", pnginfo=info)
    return buffer.getvalue()
