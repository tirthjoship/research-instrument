# tests/test_stock_analysis_css.py
import inspect

from adapters.visualization.components import styles
from domain.fit import FORBIDDEN_WORDS

REQUIRED_CLASSES = [
    ".sa-chip",
    ".sa-info",
    ".sa-tip",
    ".sa-tip-basis",
    ".sa-tile",
    ".sa-strip",
    ".sa-panel",
    ".sa-twocol",
    ".sa-claim",
    ".sa-group",
    ".sa-gtiles",
    ".sa-pe-row",
    ".sa-rangebar",
    ".t-amber",
    ".t-green",
    ".t-grey",
    ".t-petrol",
    ".t-crimson",
]


def test_design_system_classes_present():
    css = styles.GLOBAL_CSS
    for cls in REQUIRED_CLASSES:
        assert cls in css, f"missing CSS class {cls}"


def test_new_css_uses_tokens_not_raw_hex_in_tones():
    # tone classes must reference --ri-* tokens, not raw hex
    css = styles.GLOBAL_CSS
    assert (
        "var(--ri-amber)" in css
        and "var(--ri-green)" in css
        and "var(--ri-teal)" in css
    )


def test_styles_source_clean():
    src = inspect.getsource(styles).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in src
