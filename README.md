> [!WARNING]
> **DEPRECATED**: This repository is now archived and deprecated.
> It has been completely rewritten in Rust for better performance and LLM-agent workflow compatibility.
> Please use the new replacement tool: **[paperfetcher](https://github.com/0xlxx/paperfetcher)**

# pdfsearch

High-performance PDF full-text search with text indexing and fzf interactive mode.

## Install

```bash
brew install 0xlxx/tap/pdfsearch
```

Requires `fzf` and `ripgrep` for full functionality:

```bash
brew install fzf ripgrep
```

Interactive mode also requires Skim for page-accurate PDF opening:

```bash
brew install --cask skim
```

## Usage

```bash
# Build text index (one-time, multi-threaded)
pdfsearch --index

# Search — near-instant after indexing
pdfsearch "鸦片战争"

# Interactive mode — filter with fzf, double-click to open
pdfsearch "鸦片战争" -I

# Search a specific directory
pdfsearch "关键词" -d ~/Documents/pdfs

# Regex search
pdfsearch "秦.*统一" -r

# Filter by filename
pdfsearch "变法" --files "必修"

# Show context around matches
pdfsearch "封建" -c 2

# JSON output for scripting
pdfsearch "关键词" --json | jq '.matches[].page'

# Search a specific PDF file by path
pdfsearch "关键词" --file ~/Documents/specific.pdf --json

# Extract a page from a specific PDF
pdfsearch --file ~/Documents/specific.pdf --extract-page 42

# List PDFs as structured JSON
pdfsearch --list --json | jq '.files[].filename'

# Skip index, search PDFs directly
pdfsearch "关键词" --no-index
```

## Claude Code

Add [pdfsearch skill](https://github.com/0xlxx/skills) to let Claude search your PDF collection. Claude can find relevant textbook passages, read full pages for context, and answer questions grounded in your PDFs — no MCP server needed.

```bash
git clone https://github.com/0xlxx/skills.git ~/.claude/skills/
```

## How it works

`pdfsearch --index` pre-extracts text from all PDFs using PyMuPDF (multi-process), then `ripgrep` searches the index in milliseconds. Re-index when you add or modify PDFs.

### Interactive mode

`-I` opens search results in fzf with live filtering and one-click navigation:

| Key | Action |
|-----|--------|
| Enter | Open selected, quit fzf |
| Ctrl-O | Open selected, stay in fzf |
| Double-click | Open selected, quit fzf |
| F1-F9 | Jump to nth result, open, quit |
| Tab | Multi-select, Enter opens all marked |
| Esc | Quit |

Matches open at the exact page via Skim (AppleScript). Falls back to Sioyek if Skim is unavailable. Install one of them for page-accurate navigation:
