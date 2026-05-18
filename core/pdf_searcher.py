import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF


def find_pdfs(directory: Path, name_filter: str | None = None) -> list[Path]:
    pdfs = sorted(directory.rglob("*.pdf"))
    if name_filter:
        pdfs = [p for p in pdfs if name_filter.lower() in p.name.lower()]
    return pdfs


def search_pdf(
    path: Path,
    pattern: str,
    is_regex: bool,
    context_lines: int,
    ignore_case: bool,
    label: str = "",
) -> list[dict]:
    results = []
    compiled = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    total_pages = 0

    try:
        doc = fitz.open(str(path))
        total_pages = len(doc)

        for page_num in range(total_pages):
            if label:
                print(f"\r  {label}  page {page_num + 1}/{total_pages}", end="", file=sys.stderr)
            page = doc[page_num]
            text = page.get_text("text")
            if not text:
                continue

            lines = text.splitlines()

            for line_idx, line in enumerate(lines):
                match_iter = compiled.finditer(line) if is_regex else None

                if is_regex:
                    for m in match_iter:
                        results.append(
                            _build_result(
                                path, page_num, line_idx, line, m.start(),
                                m.end(), lines, context_lines, total_pages
                            )
                        )
                else:
                    search_line = line.lower() if ignore_case else line
                    search_pat = pattern.lower() if ignore_case else pattern
                    start = 0
                    while True:
                        idx = search_line.find(search_pat, start)
                        if idx == -1:
                            break
                        results.append(
                            _build_result(
                                path, page_num, line_idx, line, idx,
                                idx + len(pattern), lines, context_lines, total_pages
                            )
                        )
                        start = idx + 1

        if label:
            print("\r\033[K", end="", file=sys.stderr)
        doc.close()
    except KeyboardInterrupt:
        print("\r\033[K", end="", file=sys.stderr)
        doc.close()
        raise
    except Exception as e:
        results.append({
            "file": str(path),
            "error": str(e),
        })

    return results


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


def _build_result(
    path, page_num, line_idx, line, match_start, match_end, lines, context_lines, total_pages
):
    ctx_before, ctx_after = _compute_context(lines, line_idx, context_lines)
    return {
        "file": str(path),
        "filename": path.name,
        "page": page_num + 1,
        "total_pages": total_pages,
        "line_num": line_idx + 1,
        "line": line.strip(),
        "match": line[match_start:match_end],
        "match_start": match_start,
        "match_end": match_end,
        "context_before": ctx_before,
        "context_after": ctx_after,
    }


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
