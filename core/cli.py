import argparse
import json
import sys
import time
from pathlib import Path

from core.formatter import format_result
from core.index_manager import _collect_index_map, build_index
from core.interactive import _check_page_viewer, handle_open, run_fzf_interactive
from core.pdf_searcher import extract_page, find_pdfs, find_texts, list_pdfs, list_pdfs_json, search_pdf
from core.rg_searcher import search_txt, search_via_ripgrep


def main():
    # Hidden flag for fzf sub-processes (handled before argparse to avoid clutter)
    if "--_open" in sys.argv:
        handle_open()

    parser = argparse.ArgumentParser(
        description="High-performance PDF full-text search (PyMuPDF backend)",
        epilog="Examples:\n"
               "  pdfsearch --index                        # build index for instant search\n"
               "  pdfsearch '鸦片战争'                       # search (uses index if available)\n"
               "  pdfsearch '鸦片战争' -I                    # search + interactive fzf mode\n"
               "  pdfsearch '秦.*统一' -r                    # regex search\n"
               "  pdfsearch '封建' -c 2 --files '必修'       # context lines + name filter\n"
               "  pdfsearch --file /path/to/doc.pdf --extract-page 15  # extract page from specific file\n"
               "  pdfsearch --extract-page 15               # extract full page text\n"
               "  pdfsearch --list --json                    # list PDFs as structured JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", nargs="?", help="Search query (plain text or regex with -r)")
    parser.add_argument("-d", "--dir", default=".", help="Directory to search (default: .)")
    parser.add_argument("-r", "--regex", action="store_true", help="Treat query as regex")
    parser.add_argument("-c", "--context", type=int, default=0, help="Context lines around match")
    parser.add_argument("-i", "--ignore-case", action="store_true", default=True, help="Ignore case (default: True)")
    parser.add_argument("--case-sensitive", action="store_true", help="Case-sensitive search")
    parser.add_argument("--files", help="Filter PDF filenames (substring match)")
    parser.add_argument("--file", "-f", help="Direct PDF file path (overrides directory-based discovery)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("-I", "--interactive", action="store_true", help="Interactive mode with fzf: filter, preview, and open PDFs")
    parser.add_argument("--extract-page", type=int, help="Extract full text of a page (by page number)")
    parser.add_argument("--list", action="store_true", help="List all PDFs with metadata, don't search")
    parser.add_argument("--index", action="store_true", help="Build/update text index for fast search")
    parser.add_argument("--reindex", action="store_true", help="Force rebuild text index from scratch")
    parser.add_argument("--no-index", action="store_true", help="Skip index, search PDFs directly")
    args = parser.parse_args()

    if args.interactive and args.json:
        print("Error: -I/--interactive and --json are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    directory = Path(args.dir).expanduser().resolve()

    if args.file:
        file_path = Path(args.file).expanduser().resolve()
        if not file_path.is_file():
            print(f"Error: '{args.file}' is not a file or does not exist", file=sys.stderr)
            sys.exit(1)
        if file_path.suffix.lower() == ".txt":
            pdfs = []
            txts = [file_path]
        else:
            pdfs = [file_path]
            txts = []
    else:
        if not directory.is_dir():
            print(f"Error: '{directory}' is not a directory", file=sys.stderr)
            sys.exit(1)
        pdfs = find_pdfs(directory, args.files)
        txts = find_texts(directory, args.files)

    def _exit_no_pdfs():
        msg = f"No PDFs found in {directory}"
        if args.files:
            msg += f" matching '{args.files}'"
        print(msg)
        sys.exit(0)

    if args.index or args.reindex:
        if not pdfs:
            _exit_no_pdfs()
        build_index(directory, force=args.reindex)
        return

    if args.list:
        if not pdfs:
            _exit_no_pdfs()
        if args.json:
            list_pdfs_json(pdfs)
        else:
            list_pdfs(pdfs)
        return

    if args.extract_page:
        if not pdfs:
            _exit_no_pdfs()
        text = extract_page(pdfs[0], args.extract_page)
        if text is None:
            print(f"Page {args.extract_page} not found in {pdfs[0].name}", file=sys.stderr)
            sys.exit(1)
        print(text)
        return

    if not args.query:
        parser.print_help()
        sys.exit(1)

    ignore_case = not args.case_sensitive
    start_time = time.perf_counter()

    try:
        all_results = []
        index_map = {} if args.no_index else _collect_index_map(pdfs)

        if index_map:
            all_results = search_via_ripgrep(
                args.query, index_map, args.regex, ignore_case, args.context,
            )
            indexed_paths = {Path(m["path"]).resolve() for m in index_map.values()}
            unindexed = [p for p in pdfs if p.resolve() not in indexed_paths]
        else:
            unindexed = pdfs

        for i, pdf in enumerate(unindexed):
            label = f"{pdf.name}  [{i + 1}/{len(unindexed)}]"
            all_results.extend(search_pdf(pdf, args.query, args.regex, args.context, ignore_case, label))

        for txt in txts:
            all_results.extend(search_txt(txt, args.query, args.regex, ignore_case, args.context))

        elapsed = time.perf_counter() - start_time
        used_index = bool(index_map)

        has_matches = any("error" not in r for r in all_results)

        if args.interactive:
            run_fzf_interactive(all_results)
            if not _check_page_viewer() and has_matches:
                print("  Install Skim for page-accurate PDF opening: brew install --cask skim", file=sys.stderr)
            return

        if args.json:
            match_count = len([r for r in all_results if "error" not in r])
            output = {
                "query": args.query,
                "elapsed_ms": round(elapsed * 1000, 2),
                "indexed": used_index,
                "total_matches": match_count,
                "matches": all_results,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            show_context = args.context > 0
            for r in all_results:
                print(format_result(r, show_context), end="")

            match_count = len([r for r in all_results if "error" not in r])
            error_count = len([r for r in all_results if "error" in r])
            files_with_matches = len({r["file"] for r in all_results if "error" not in r})

            print(f"\n  ──────────────────────────────")
            print(f"  {match_count} match(es) across {files_with_matches} file(s)")
            if error_count:
                print(f"  {error_count} file(s) with errors")
            if used_index:
                print(f"  Searched index ({len(pdfs)} PDFs) in {elapsed:.2f}s")
            else:
                parts = []
                if pdfs:
                    parts.append(f"{len(pdfs)} PDF(s)")
                if txts:
                    parts.append(f"{len(txts)} txt file(s)")
                print(f"  Searched {' + '.join(parts)} in {elapsed:.2f}s")
            if not used_index and pdfs:
                print(f"  Tip: run 'pdfsearch --index' for near-instant searches")
            if not _check_page_viewer() and has_matches:
                print(f"  Tip: install Skim for page-accurate opening: brew install --cask skim")
    except KeyboardInterrupt:
        print("\r\033[K\n  Interrupted.", file=sys.stderr)
        sys.exit(130)
