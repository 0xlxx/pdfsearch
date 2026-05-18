import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def check_fzf() -> bool:
    return shutil.which("fzf") is not None


def _has_skim() -> bool:
    """Check if Skim.app is installed (it has no CLI binary, check the bundle)."""
    skim_paths = [
        Path("/Applications/Skim.app"),
        Path.home() / "Applications/Skim.app",
    ]
    return any(p.exists() for p in skim_paths)


def _check_page_viewer() -> bool:
    """Return True if a page-accurate PDF viewer is available."""
    return _has_skim() or shutil.which("sioyek") is not None


def open_pdf_at_page(filepath: str, page: int) -> bool:
    """Open a PDF at a specific page, trying viewers in priority order.

    Chain: Skim (AppleScript) → Sioyek (--page) → open (no page nav).
    Returns True if page-accurate navigation succeeded, False otherwise.
    """
    path = Path(filepath)
    if not path.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        return False

    # 1. Skim via AppleScript — most reliable page navigation
    if _has_skim():
        script = f'''
        tell application "Skim"
            activate
            open POSIX file "{path}"
            delay 0.3
            tell document 1
                set current page to page {page}
            end tell
        end tell
        '''
        try:
            subprocess.run(["osascript", "-e", script], check=False, timeout=10)
            return True
        except Exception:
            pass

    # 2. Sioyek via --page flag (brew install sioyek)
    if shutil.which("sioyek"):
        try:
            subprocess.run(
                ["sioyek", str(path), "--page", str(page)],
                check=False, timeout=10,
            )
            return True
        except Exception:
            pass

    # 3. Fallback: open in default viewer (no page navigation)
    subprocess.run(["open", str(path)], check=False)
    return False


def handle_open() -> None:
    """Open PDF at page. Called via --_open <path> <page> (from fzf key bindings)."""
    import argparse as ap
    p = ap.ArgumentParser(add_help=False)
    p.add_argument("--_open", nargs=2)
    args, _ = p.parse_known_args()
    if args._open:
        open_pdf_at_page(args._open[0], int(args._open[1]))
        sys.exit(0)


def run_fzf_interactive(results: list[dict]) -> None:
    """Pipe search results to fzf for interactive filtering and one-click open."""
    if not check_fzf():
        print("fzf not found. Install with: brew install fzf", file=sys.stderr)
        return

    valid = [r for r in results if "error" not in r]
    if not valid:
        print("No matches to open.", file=sys.stderr)
        return

    # Build fzf input: display \t filepath \t page
    lines = []
    for r in valid:
        display = f"{r['filename']}  p{r['page']}  ▶  {r['line'][:120]}"
        lines.append(f"{display}\t{r['file']}\t{r['page']}\n")
    fzf_input = "".join(lines)

    # Resolve self-path for --_open sub-calls.
    # In brew installs, PyMuPDF lives alongside the script in libexec,
    # and the brew wrapper sets PYTHONPATH. fzf subprocesses (Ctrl-O)
    # bypass the wrapper, so we embed PYTHONPATH directly.
    # NOTE: since this is now in core/interactive.py, the entrypoint is parent's parent.
    # But actually, the script executed is the entrypoint. Let's just use sys.argv[0] to be safe
    # or resolve sys.argv[0].
    self_path = Path(sys.argv[0]).resolve()
    lib_dir = str(self_path.parent)

    open_cmd = (
        f"PYTHONPATH={shlex.quote(lib_dir)} "
        f"{shlex.quote(str(self_path))} --_open '{{1}}' '{{2}}'"
    )

    fzf_args = [
        "fzf",
        "--delimiter=\t",
        "--with-nth=1",
        "--bind", ",".join(f"f{i}:pos({i})+accept" for i in range(1, 10)),
        "--bind", f"ctrl-o:execute-silent({open_cmd})",
        "--bind", f"double-click:execute-silent({open_cmd})+accept",
        "--multi",
        "--header", "Enter=open+quit  Ctrl-O=open+stay  F1-F9=jump  Tab=multi  DblClick=open  Esc=quit",
        "--header-first",
    ]

    try:
        proc = subprocess.run(
            fzf_args,
            input=fzf_input,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        print("fzf not found. Install with: brew install fzf", file=sys.stderr)
        return

    # Exit codes: 0=selection made, 1=no match, 130=interrupted (Esc/Ctrl-C)
    if proc.returncode not in (0, 1):
        return

    stdout = proc.stdout.strip()
    if not stdout:
        return

    for line_text in stdout.splitlines():
        parts = line_text.split("\t")
        if len(parts) >= 3:
            filepath = parts[1]
            page = int(parts[2])
            print(f"\n  → Opening {Path(filepath).name} at page {page}...")
            open_pdf_at_page(filepath, page)
