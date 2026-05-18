import json
import subprocess
import sys
from pathlib import Path

from core.pdf_searcher import _compute_context


def _rg_match_to_result(
    match: dict, index_map: dict[str, dict]
) -> dict | None:
    """Convert a single ripgrep JSON match entry to unified result dict."""
    data = match.get("data", {})
    path_text = data.get("path", {}).get("text", "")
    page_path = Path(path_text)
    hash_dir = str(page_path.parent)

    meta = index_map.get(hash_dir)
    if meta is None:
        return None

    page_num = int(page_path.stem.split("_")[1])
    line_num = data.get("line_number", 1)
    line_idx = line_num - 1

    try:
        lines = page_path.read_text().splitlines()
    except OSError:
        return None

    matched_line = lines[line_idx] if 0 <= line_idx < len(lines) else ""

    submatches = data.get("submatches", [])
    if submatches:
        matched_text = submatches[0].get("match", {}).get("text", "")
        # rg reports byte offsets; convert to character offsets for highlighting
        line_bytes = matched_line.encode("utf-8")
        m_start = len(line_bytes[:submatches[0].get("start", 0)].decode("utf-8"))
        m_end = len(line_bytes[:submatches[0].get("end", 0)].decode("utf-8"))
    else:
        m_start = 0
        m_end = 0
        matched_text = ""

    return {
        "file": meta["path"],
        "filename": meta["filename"],
        "page": page_num,
        "total_pages": meta["pages"],
        "line_num": line_idx + 1,
        "line": matched_line.strip(),
        "match": matched_text,
        "match_start": m_start,
        "match_end": m_end,
        "context_before": [],
        "context_after": [],
        "_lines": lines,
        "_line_idx": line_idx,
    }


def _add_context(result: dict, context_lines: int) -> None:
    """Mutate result with context lines around the match (uses cached page lines)."""
    if context_lines <= 0:
        return
    lines = result.pop("_lines", None)
    line_idx = result.pop("_line_idx", None)
    if lines is None or line_idx is None:
        return
    result["context_before"], result["context_after"] = _compute_context(
        lines, line_idx, context_lines
    )


def search_via_ripgrep(
    query: str,
    index_map: dict[str, dict],
    is_regex: bool,
    ignore_case: bool,
    context_lines: int,
) -> list[dict]:
    """Search indexed PDFs using ripgrep. Returns unified result list."""
    search_paths = []
    for hash_dir_str, meta in index_map.items():
        hash_dir = Path(hash_dir_str)
        for page_num in range(1, meta["pages"] + 1):
            search_paths.append(hash_dir / f"page_{page_num:04d}.txt")

    if not search_paths:
        return []

    rg_args = ["rg", "--json", "--with-filename", "--line-number", "--no-heading"]

    if not is_regex:
        rg_args.append("--fixed-strings")
    if ignore_case:
        rg_args.append("--ignore-case")

    rg_args.append("--")
    rg_args.append(query)
    rg_args.extend(str(p) for p in search_paths)

    try:
        proc = subprocess.run(rg_args, capture_output=True, text=True)
    except FileNotFoundError:
        print("ripgrep (rg) not found. Install with: brew install ripgrep", file=sys.stderr)
        return []

    if proc.returncode not in (0, 1):
        return []

    results = []
    for line_text in proc.stdout.splitlines():
        try:
            entry = json.loads(line_text)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "match":
            continue

        result = _rg_match_to_result(entry, index_map)
        if result is None:
            continue

        if context_lines > 0:
            _add_context(result, context_lines)
        else:
            result.pop("_lines", None)
            result.pop("_line_idx", None)

        results.append(result)

    return results
