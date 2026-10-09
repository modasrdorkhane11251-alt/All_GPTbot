from io import BytesIO
from pathlib import Path
from pypdf import PdfReader
from docx import Document
MAX_BYTES=8*1024*1024
def extract(name,raw):
    if len(raw)>MAX_BYTES: raise ValueError("File too large (8 MB max).")
    ext=Path(name or "").suffix.lower()
    if ext in {".txt",".md",".csv",".json",".py",".js",".html",".xml",".log"}: text=raw.decode("utf-8",errors="replace")
    elif ext==".pdf": text="\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(raw)).pages[:30])
    elif ext==".docx": text="\n".join(p.text for p in Document(BytesIO(raw)).paragraphs)
    else: raise ValueError("Unsupported file. Use TXT, MD, CSV, JSON, code/text, PDF or DOCX.")
    return text[:20000]
