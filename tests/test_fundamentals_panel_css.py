from adapters.visualization.components import styles
from domain.fit import FORBIDDEN_WORDS

REQUIRED = [
    ".sa-pnl",
    ".sa-pnl-eyebrow",
    ".sa-pnl-dot",
    ".sa-pnl-chips",
    ".sa-pnl-claim",
    ".sa-pnl-reline",
    ".sa-pnl-two",
    ".sa-pnl-subh",
    ".sa-pnl-cap",
    ".sa-vb",
    ".sa-drill",
]


def _block():
    css = styles.GLOBAL_CSS
    s = css.index("/* ===== Stock Analysis redesign — fundamentals panels ===== */")
    e = css.index("/* ===== end Stock Analysis fundamentals panels ===== */")
    return css[s:e]


def test_panel_classes_present():
    block = _block()
    for cls in REQUIRED:
        assert cls in block, f"missing {cls}"


def test_panel_block_uses_tokens_and_clean():
    block = _block()
    assert "var(--ri-line)" in block and "var(--ri-ink)" in block
    low = block.lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low
