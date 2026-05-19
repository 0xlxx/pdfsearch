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


def open_result(filepath: str, page: int, line_num: int = 0) -> bool:
    """Open a search result at the right location, dispatching by file type.

    PDF  → Skim (AppleScript) → Sioyek (--page) → open (no page nav)
    EPUB → open (Books.app / default EPUB reader)
    TXT  → code -g (VS Code) → subl (Sublime) → open (no line nav)

    Returns True if accurate navigation succeeded, False otherwise.
    """
    path = Path(filepath)
    if not path.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        return False

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _open_pdf(path, page)
    elif suffix == ".epub":
        subprocess.run(["open", str(path)], check=False)
        return False
    elif suffix == ".txt":
        return _open_txt(path, line_num)
    else:
        subprocess.run(["open", str(path)], check=False)
        return False


def _open_pdf(path: Path, page: int) -> bool:
    """Open a PDF at a specific page."""
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

    if shutil.which("sioyek"):
        try:
            subprocess.run(
                ["sioyek", str(path), "--page", str(page)],
                check=False, timeout=10,
            )
            return True
        except Exception:
            pass

    subprocess.run(["open", str(path)], check=False)
    return False


def _open_txt(path: Path, line_num: int) -> bool:
    """Open a text file, trying to jump to line_num."""
    if line_num > 0 and shutil.which("code"):
        subprocess.run(["code", "-g", f"{path}:{line_num}"], check=False)
        return True
    if line_num > 0 and shutil.which("subl"):
        subprocess.run(["subl", f"{path}:{line_num}"], check=False)
        return True
    subprocess.run(["open", str(path)], check=False)
    return False


def handle_open() -> None:
    """Open result at location. Called via --_open <path> <page> [line_num] (from fzf key bindings)."""
    import argparse as ap
    p = ap.ArgumentParser(add_help=False)
    p.add_argument("--_open", nargs="*")
    args, _ = p.parse_known_args()
    if args._open and len(args._open) >= 2:
        filepath = args._open[0]
        page = int(args._open[1])
        line_num = int(args._open[2]) if len(args._open) >= 3 else 0
        open_result(filepath, page, line_num)
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

    # Build fzf input: display \t filepath \t page \t line_num
    lines = []
    for r in valid:
        name = r["filename"]
        if name.lower().endswith(".txt"):
            loc = f"L{r['line_num']}"
        elif name.lower().endswith(".epub"):
            loc = f"ch{r['page']}/{r['total_pages']}"
        else:
            loc = f"p{r['page']}/{r['total_pages']}"
        display = f"{name}  {loc}  ▶  {r['line'][:120]}"
        lines.append(f"{display}\t{r['file']}\t{r['page']}\t{r['line_num']}\n")
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
        f"{shlex.quote(str(self_path))} --_open '{{1}}' '{{2}}' '{{3}}'"
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
            line_num = int(parts[3]) if len(parts) >= 4 else 0

            name = Path(filepath).name
            if name.lower().endswith(".txt"):
                print(f"\n  → Opening {name} at line {line_num}...")
            elif name.lower().endswith(".epub"):
                print(f"\n  → Opening {name} at chapter {page}...")
            else:
                print(f"\n  → Opening {name} at page {page}...")
            open_result(filepath, page, line_num)
