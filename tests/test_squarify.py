from adapters.visualization.components.squarify import Rect, squarify


def test_rects_cover_area_and_are_proportional():
    rects = squarify([50.0, 30.0, 20.0], 0.0, 0.0, 100.0, 100.0)
    assert len(rects) == 3
    total = sum(r.w * r.h for r in rects)
    assert abs(total - 100.0 * 100.0) < 1.0
    areas = [r.w * r.h for r in rects]
    assert areas[0] > areas[1] > areas[2]
    assert abs(areas[0] / total - 0.5) < 0.02


def test_no_rect_escapes_container():
    rects = squarify([1.0, 1.0, 1.0, 97.0], 0.0, 0.0, 200.0, 120.0)
    for r in rects:
        assert r.x >= -0.01 and r.y >= -0.01
        assert r.x + r.w <= 200.01 and r.y + r.h <= 120.01


def test_single_item_fills_container():
    rects = squarify([42.0], 5.0, 5.0, 50.0, 60.0)
    assert len(rects) == 1
    r = rects[0]
    assert isinstance(r, Rect)
    assert abs(r.w - 50.0) < 0.01 and abs(r.h - 60.0) < 0.01


def test_empty_returns_empty():
    assert squarify([], 0.0, 0.0, 10.0, 10.0) == []
