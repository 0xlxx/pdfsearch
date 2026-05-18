import hashlib
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import fitz  # PyMuPDF

from core.config import INDEX_ROOT
from core.pdf_searcher import find_pdfs


def _hash_path(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]


def _get_index_dir(path: Path) -> Path:
    return INDEX_ROOT / _hash_path(path)


def _read_meta(hash_dir: Path) -> dict | None:
    try:
        return json.loads((hash_dir / "meta.json").read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _read_valid_meta(pdf_path: Path) -> dict | None:
    """Return meta dict if index exists and is fresh (mtime/size match), else None."""
    meta = _read_meta(_get_index_dir(pdf_path))
    if meta is None:
        return None
    try:
        stat = pdf_path.stat()
    except OSError:
        return None
    if meta.get("mtime") != stat.st_mtime or meta.get("size") != stat.st_size:
        return None
    return meta


def _collect_index_map(pdfs: list[Path]) -> dict[str, dict]:
    """Build map of hash_dir_str -> meta for all fresh indexed PDFs."""
    index_map = {}
    for pdf in pdfs:
        meta = _read_valid_meta(pdf)
        if meta:
            index_map[str(_get_index_dir(pdf))] = meta
    return index_map


def _index_one_pdf(pdf_path: Path) -> None:
    """Extract text from a single PDF and write page txt files + meta.json."""
    hash_dir = _get_index_dir(pdf_path)
    try:
        hash_dir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)
        for page_num in range(total_pages):
            text = doc[page_num].get_text("text")
            (hash_dir / f"page_{page_num + 1:04d}.txt").write_text(text)
        doc.close()
        stat = pdf_path.stat()
        meta = {
            "path": str(pdf_path.resolve()),
            "filename": pdf_path.name,
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "pages": total_pages,
        }
        (hash_dir / "meta.json").write_text(json.dumps(meta))
    except Exception as e:
        print(f"  Warning: failed to index {pdf_path.name}: {e}", file=sys.stderr)


def build_index(directory: Path, force: bool = False, workers: int | None = None) -> int:
    """Build/update text index for all PDFs in directory. Returns number indexed."""
    pdfs = find_pdfs(directory)
    if not pdfs:
        print(f"No PDFs found in {directory}")
        return 0

    if workers is None:
        workers = os.cpu_count() or 4

    to_index = []
    for pdf in pdfs:
        if not force and _read_valid_meta(pdf) is not None:
            continue
        to_index.append(pdf)

    if not to_index:
        print(f"All {len(pdfs)} PDF(s) already indexed. Use --reindex to force rebuild.")
        return 0

    print(f"Indexing {len(to_index)} PDF(s) with {workers} workers...")
    start = time.perf_counter()

    try:
        with Pool(workers, maxtasksperchild=10) as pool:
            pool.map(_index_one_pdf, to_index)
    except KeyboardInterrupt:
        print("\n  Indexing interrupted.", file=sys.stderr)
        sys.exit(130)

    elapsed = time.perf_counter() - start
    print(f"Indexed {len(to_index)} PDF(s) in {elapsed:.1f}s")
    return len(to_index)
