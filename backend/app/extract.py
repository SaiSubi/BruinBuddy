"""Text extraction and chunking, shared by uploads (materials.py) and the 18.05 seed (ingest.py)."""
import re
import unicodedata

CHUNK_TARGET = 1400  # characters, roughly 350 tokens
CHUNK_MIN = 200
TEXT_PART = 3000     # plain-text files are split into "pages" of about this many characters


class NoText(Exception):
    """The file has no extractable text (for example a scanned PDF)."""


def clean_text(text: str) -> str:
    """NFKC-normalise (turns math-italic letters into plain ones) and fold table cells
    that PyMuPDF emits one per line back into a single line, to save tokens."""
    text = unicodedata.normalize("NFKC", text).replace(" ", " ")
    out, run = [], []
    for line in text.split("\n"):
        line = line.strip()
        if 0 < len(line) <= 8:
            run.append(line)
            continue
        if run:
            out.append(" ".join(run))
            run = []
        if line:
            out.append(line)
    if run:
        out.append(" ".join(run))
    return "\n".join(out)


def split_page(text: str) -> list[str]:
    text = re.sub(r"[ \t]+\n", "\n", clean_text(text)).strip()
    if len(text) <= CHUNK_TARGET:
        return [text] if len(text) >= 40 else []
    paras = re.split(r"\n\s*\n", text)
    chunks, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > CHUNK_TARGET:
            chunks.append(cur.strip())
            cur = ""
        while len(p) > CHUNK_TARGET * 1.5:  # very long paragraph: hard split on whitespace
            cut = p.rfind(" ", 0, CHUNK_TARGET)
            cut = cut if cut > CHUNK_MIN else CHUNK_TARGET
            chunks.append((cur + "\n\n" + p[:cut]).strip() if cur else p[:cut].strip())
            cur, p = "", p[cut:].lstrip()
        cur = (cur + "\n\n" + p) if cur else p
    if cur.strip():
        if chunks and len(cur) < CHUNK_MIN:
            chunks[-1] += "\n\n" + cur.strip()
        else:
            chunks.append(cur.strip())
    return [c for c in chunks if len(c) >= 40]


def _text_parts(text: str) -> list[str]:
    paras, parts, cur = re.split(r"\n\s*\n", text), [], ""
    for p in paras:
        if cur and len(cur) + len(p) > TEXT_PART:
            parts.append(cur)
            cur = ""
        cur = f"{cur}\n\n{p}" if cur else p
    if cur.strip():
        parts.append(cur)
    return parts


def extract_pages(data: bytes, file_name: str) -> list[tuple[int, str]]:
    """Return [(page_number, text)] for a PDF, .txt or .md file. Raises NoText if nothing usable is found."""
    if file_name.lower().endswith(".pdf"):
        import pymupdf  # imported lazily: only needed when a PDF is processed
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            pages = [(i, page.get_text("text")) for i, page in enumerate(doc, start=1)]
    else:
        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
        pages = list(enumerate(_text_parts(text), start=1))
    pages = [(n, t) for n, t in pages if len(t.strip()) >= 40]
    if not pages:
        raise NoText()
    return pages


def chunk_pages(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [(n, c) for n, t in pages for c in split_page(t)]
