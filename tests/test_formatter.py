from core.formatter import format_result


def test_format_result_error():
    result = {"error": "File read failed"}
    output = format_result(result, show_context=False)
    assert "⚠ File read failed" in output


def test_format_result_no_context():
    result = {
        "filename": "test.pdf",
        "page": 1,
        "total_pages": 10,
        "line_num": 5,
        "line": "This is a test match here.",
        "match": "test match",
        "match_start": 10,
        "match_end": 20,
    }
    output = format_result(result, show_context=False)
    assert "test.pdf" in output
    assert "p1/10" in output
    assert "L5" in output
    assert "This is a" in output
    assert "test match" in output
    assert "\033[1;33m" in output  # Highlight color code


def test_format_result_with_context():
    result = {
        "filename": "test.pdf",
        "page": 1,
        "total_pages": 1,
        "line_num": 2,
        "line": "Middle line with match",
        "match": "match",
        "match_start": 17,
        "match_end": 22,
        "context_before": ["First line context"],
        "context_after": ["Third line context"],
    }
    output = format_result(result, show_context=True)
    assert "First line context" in output
    assert "Middle line with match" in output
    assert "Third line context" in output
