# pdfsearch

High-performance PDF full-text search with fzf interactive mode.

## Install

```bash
brew install 0xlxx/tap/pdfsearch
```

Requires `fzf` for interactive mode:

```bash
brew install fzf
```

## Usage

```bash
# Search all PDFs in current directory
pdfsearch "鸦片战争"

# Regex search
pdfsearch "秦.*统一" -r

# Interactive mode — filter with fzf, open in Preview
pdfsearch "鸦片战争" -I

# Search a specific directory
pdfsearch "关键词" -d ~/Documents/pdfs

# Filter by filename
pdfsearch "变法" --files "必修"

# Show context around matches
pdfsearch "封建" -c 2

# JSON output for scripting
pdfsearch "关键词" --json | jq '.[].page'
```

### Interactive mode

`-I` opens search results in fzf with live filtering, page preview, and one-key
navigation:

| Key | Action |
|-----|--------|
| Enter | Open selected in Preview, quit fzf |
| Ctrl-O | Open selected, stay in fzf |
| F1–F9 | Jump to nth result, open, quit |
| Tab | Multi-select, Enter opens all marked |
| Esc | Quit |

Matches open in Preview.app at the exact page via AppleScript.
