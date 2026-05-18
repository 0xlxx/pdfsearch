from core.pdf_searcher import _compute_context


def test_compute_context_zero():
    lines = ["a", "b", "c", "d"]
    before, after = _compute_context(lines, 1, 0)
    assert before == []
    assert after == []


def test_compute_context_normal():
    lines = ["line1", "line2", "line3", "line4", "line5"]
    before, after = _compute_context(lines, 2, 1)
    assert before == ["line2"]
    assert after == ["line4"]


def test_compute_context_boundaries():
    lines = ["line1", "line2", "line3"]
    # Test top boundary
    before, after = _compute_context(lines, 0, 2)
    assert before == []
    assert after == ["line2", "line3"]

    # Test bottom boundary
    before, after = _compute_context(lines, 2, 2)
    assert before == ["line1", "line2"]
    assert after == []
