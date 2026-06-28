# tests/test_stock_analysis_top_css.py
from adapters.visualization.components import styles
from domain.fit import FORBIDDEN_WORDS

REQUIRED = [
    ".sa-stage",
    ".sa-hero",
    ".sa-ribbon",
    ".sa-hbody",
    ".sa-htop",
    ".sa-coname",
    ".sa-tkr",
    ".sa-grade",
    ".sa-prow",
    ".sa-price",
    ".sa-chg",
    ".sa-metab",
    ".sa-rngw",
    ".sa-eyebrow",
    ".sa-tagmono",
    ".sa-prose",
    ".sa-chips",
    ".sa-cchip",
    ".sa-grid6",
    ".sa-vt",
    ".sa-twocol-fit",
    ".sa-lgnd",
    ".sa-ckey",
    ".sa-ghead",
    ".sa-chev",
    ".sa-gname",
    ".sa-ggrade",
    ".sa-gweek",
    ".sa-gt",
]


def _block() -> str:
    css = styles.GLOBAL_CSS
    start = css.index("/* ===== Stock Analysis redesign — top sections ===== */")
    end = css.index("/* ===== end Stock Analysis top sections ===== */")
    return css[start:end]


def test_top_section_classes_present():
    block = _block()
    for cls in REQUIRED:
        assert cls in block, f"missing CSS class {cls}"


def test_stage_caps_width_800():
    assert "max-width:800px" in _block()


def test_new_block_uses_tokens():
    block = _block()
    assert (
        "var(--ri-line)" in block
        and "var(--ri-teal)" in block
        and "var(--ri-ink)" in block
    )


def test_top_block_clean_of_slop():
    # guards only the new top-sections block; legacy classes elsewhere are out of scope
    low = _block().lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
