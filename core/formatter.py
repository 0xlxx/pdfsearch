def format_result(result: dict, show_context: bool) -> str:
    if "error" in result:
        return f"  ⚠ {result['error']}"

    file_label = f"{result['filename']}  p{result['page']}/{result['total_pages']}  L{result['line_num']}"

    line = result["line"]
    m_start = result["match_start"]
    m_end = result["match_end"]
    highlighted = (
        line[:m_start]
        + "\033[1;33m"
        + line[m_start:m_end]
        + "\033[0m"
        + line[m_end:]
    )

    out = f"\n  \033[1;36m{file_label}\033[0m\n"

    if show_context and (result["context_before"] or result["context_after"]):
        for ctx_line in result["context_before"]:
            out += f"    {ctx_line}\n"
        out += f"  ▶ {highlighted}\n"
        for ctx_line in result["context_after"]:
            out += f"    {ctx_line}\n"
    else:
        out += f"  ▶ {highlighted}\n"

    return out
