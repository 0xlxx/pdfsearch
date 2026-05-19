import html
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


def find_epubs(directory: Path, name_filter: str | None = None) -> list[Path]:
    epubs = sorted(directory.rglob("*.epub"))
    if name_filter:
        epubs = [e for e in epubs if name_filter.lower() in e.name.lower()]
    return epubs


def _html_to_text(html_text: str) -> str:
    """Convert XHTML body content to plain text."""
    # Insert newlines at block-level breaks
    text = re.sub(r'<br\s*/?>', '\n', html_text, flags=re.IGNORECASE)
    text = re.sub(r'</?(?:p|div|h[1-6]|li|tr|section|article|header|footer|table)[^>]*>', '\n', text, flags=re.IGNORECASE)
    # Strip all remaining tags (including <head>, <style>, <script>)
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html.unescape(text)
    # Collapse excess whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def search_epub(
    path: Path,
    pattern: str,
    is_regex: bool,
    context_lines: int,
    ignore_case: bool,
    label: str = "",
) -> list[dict]:
    """Search an EPUB by extracting chapters to temp files and delegating to ripgrep."""
    try:
        zf = zipfile.ZipFile(path)
    except Exception as e:
        return [{"file": str(path), "error": str(e)}]

    html_files = sorted(
        f for f in zf.namelist()
        if f.lower().endswith(('.xhtml', '.html', '.htm'))
        and not f.startswith('__MACOSX')
    )

    if not html_files:
        zf.close()
        return [{"file": str(path), "error": "No XHTML content found in EPUB"}]

    temp_dir = Path(tempfile.mkdtemp(prefix="pdfsearch_epub_"))
    valid_chapters = 0

    try:
        if label:
            print(f"\r  {label}  extracting chapter 1/{len(html_files)}", end="", file=sys.stderr)

        for i, internal_path in enumerate(html_files):
            if label and i > 0:
                print(f"\r  {label}  extracting chapter {i + 1}/{len(html_files)}", end="", file=sys.stderr)
            content = zf.read(internal_path).decode("utf-8", errors="replace")
            text = _html_to_text(content)
            if text:
                valid_chapters += 1
                (temp_dir / f"page_{valid_chapters:04d}.txt").write_text(text)

        zf.close()

        if label:
            print(f"\r\033[K", end="", file=sys.stderr)

        if valid_chapters == 0:
            return []

        index_map = {
            str(temp_dir): {
                "path": str(path),
                "filename": path.name,
                "pages": valid_chapters,
            }
        }

        from core.rg_searcher import search_via_ripgrep

        return search_via_ripgrep(pattern, index_map, is_regex, ignore_case, context_lines)

    except KeyboardInterrupt:
        if label:
            print(f"\r\033[K", end="", file=sys.stderr)
        try:
            zf.close()
        except Exception:
            pass
        raise
    except Exception as e:
        return [{"file": str(path), "error": str(e)}]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
