import json
import shutil
import sys
import tempfile
from pathlib import Path

import fitz  # PyMuPDF


def find_pdfs(directory: Path, name_filter: str | None = None) -> list[Path]:
    pdfs = sorted(directory.rglob("*.pdf"))
    if name_filter:
        pdfs = [p for p in pdfs if name_filter.lower() in p.name.lower()]
    return pdfs


def find_texts(directory: Path, name_filter: str | None = None) -> list[Path]:
    texts = sorted(directory.rglob("*.txt"))
    if name_filter:
        texts = [t for t in texts if name_filter.lower() in t.name.lower()]
    return texts


def search_pdf(
    path: Path,
    pattern: str,
    is_regex: bool,
    context_lines: int,
    ignore_case: bool,
    label: str = "",
) -> list[dict]:
    """Search a PDF by extracting text to temp pages and delegating to ripgrep."""
    try:
        doc = fitz.open(str(path))
        total_pages = len(doc)
    except Exception as e:
        return [{"file": str(path), "error": str(e)}]

    if total_pages == 0:
        doc.close()
        return []

    temp_dir = Path(tempfile.mkdtemp(prefix="pdfsearch_"))

    try:
        for page_num in range(total_pages):
            if label:
                print(f"\r  {label}  extracting page {page_num + 1}/{total_pages}", end="", file=sys.stderr)
            text = doc[page_num].get_text("text")
            (temp_dir / f"page_{page_num + 1:04d}.txt").write_text(text)

        doc.close()

        if label:
            print(f"\r\033[K", end="", file=sys.stderr)

        index_map = {
            str(temp_dir): {
                "path": str(path),
                "filename": path.name,
                "pages": total_pages,
            }
        }

        # Lazy import to break circular dependency (rg_searcher imports _compute_context from here)
        from core.rg_searcher import search_via_ripgrep

        return search_via_ripgrep(pattern, index_map, is_regex, ignore_case, context_lines)

    except KeyboardInterrupt:
        if label:
            print(f"\r\033[K", end="", file=sys.stderr)
        try:
            doc.close()
        except Exception:
            pass
        raise
    except Exception as e:
        return [{"file": str(path), "error": str(e)}]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _compute_context(
    lines: list[str], line_idx: int, context_lines: int
) -> tuple[list[str], list[str]]:
    """Return (context_before, context_after) as stripped line lists."""
    if context_lines <= 0:
        return [], []
    ctx_start = max(0, line_idx - context_lines)
    ctx_end = min(len(lines), line_idx + context_lines + 1)
    return (
        [l.strip() for l in lines[ctx_start:line_idx]],
        [l.strip() for l in lines[line_idx + 1:ctx_end]],
    )


def extract_page(path: Path, page_num: int) -> str | None:
    try:
        doc = fitz.open(str(path))
        if page_num < 1 or page_num > len(doc):
            doc.close()
            return None
        text = doc[page_num - 1].get_text("text")
        doc.close()
        return text
    except Exception:
        return None


def list_pdfs(pdfs: list[Path]) -> None:
    print(f"\n  Found {len(pdfs)} PDF(s):\n")
    for p in pdfs:
        try:
            doc = fitz.open(str(p))
            pages = len(doc)
            size_mb = p.stat().st_size / (1024 * 1024)
            title = doc.metadata.get("title") or "(no title)"
            doc.close()
            print(f"  \033[1m{p.name}\033[0m")
            print(f"    Pages: {pages}  Size: {size_mb:.1f} MB  Title: {title}\n")
        except Exception as e:
            print(f"  \033[1m{p.name}\033[0m")
            print(f"    ⚠ Cannot read: {e}\n")

    total_size = sum(p.stat().st_size for p in pdfs) / (1024 * 1024)
    print(f"  Total: {len(pdfs)} files, {total_size:.1f} MB")


def list_pdfs_json(pdfs: list[Path]) -> None:
    files = []
    for p in pdfs:
        try:
            doc = fitz.open(str(p))
            pages = len(doc)
            size_mb = p.stat().st_size / (1024 * 1024)
            title = doc.metadata.get("title") or ""
            doc.close()
            files.append({
                "filename": p.name,
                "path": str(p),
                "pages": pages,
                "size_mb": round(size_mb, 1),
                "title": title,
            })
        except Exception as e:
            files.append({"filename": p.name, "path": str(p), "error": str(e)})
    total_mb = sum(p.stat().st_size for p in pdfs) / (1024 * 1024)
    print(json.dumps(
        {"total": len(pdfs), "total_size_mb": round(total_mb, 1), "files": files},
        ensure_ascii=False, indent=2,
    ))
