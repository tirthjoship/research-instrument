from __future__ import annotations

from unittest.mock import MagicMock, patch

from adapters.visualization.components.onboarding import render_landing_door_html


def test_door_local_shows_privacy_copy() -> None:
    """Local: privacy copy present, heading present, no dead HTML buttons."""
    html = render_landing_door_html(local=True)
    assert "stays on your machine" in html.lower()
    assert "Load a book to begin" in html
    # Dead decorative buttons removed — no <button in the HTML banner
    assert "<button" not in html


def test_door_hosted_hides_privacy_and_upload() -> None:
    html = render_landing_door_html(local=False)
    assert "stays on your machine" not in html.lower()  # no false promise
    assert "isn't running local-only" in html  # honest notice
    assert "Load a book to begin" in html  # heading still present
    # Dead decorative buttons removed from the banner HTML
    assert "<button" not in html


def test_door_no_dead_html_buttons_local() -> None:
    """render_landing_door_html(local=True) must not contain <button elements."""
    html = render_landing_door_html(local=True)
    assert "<button" not in html, (
        "Dead HTML buttons must be removed from the door banner; "
        "real actions are rendered as st.button / st.file_uploader"
    )


def test_door_no_dead_html_buttons_hosted() -> None:
    """render_landing_door_html(local=False) must not contain <button elements."""
    html = render_landing_door_html(local=False)
    assert (
        "<button" not in html
    ), "Dead HTML buttons must be removed from the door banner (hosted mode)"


# ---------------------------------------------------------------------------
# Task 5: belt-and-suspenders privacy tripwire + forbidden-word scans
# ---------------------------------------------------------------------------


def test_privacy_copy_never_shown_when_not_local() -> None:
    from adapters.visualization.components.onboarding import render_landing_door_html

    assert "stays on your machine" not in render_landing_door_html(local=False).lower()


def test_onboarding_no_forbidden_words() -> None:
    import inspect

    from adapters.visualization.components import onboarding
    from application import runtime_guard, sample_book
    from domain.fit import FORBIDDEN_WORDS

    for mod in (onboarding, runtime_guard, sample_book):
        src = inspect.getsource(mod).lower()
        for w in FORBIDDEN_WORDS:
            assert w not in src, f"forbidden word {w!r} in {mod.__name__}"


# ---------------------------------------------------------------------------
# New onboarding layout: 2-column action row, always-visible uploader
# ---------------------------------------------------------------------------


def test_sample_book_button_rendered_on_first_landing() -> None:
    """_handle_onboarding must render ob_sample button when no book in session."""
    import streamlit as st

    from adapters.visualization.tabs.weekly_brief import _handle_onboarding

    button_keys: list[str] = []

    def capture_button(label: str, **kwargs: object) -> bool:
        button_keys.append(str(kwargs.get("key", "")))
        return False

    with (
        patch.object(st, "markdown"),
        patch.object(st, "columns", return_value=[MagicMock(), MagicMock()]),
        patch.object(st, "button", side_effect=capture_button),
        patch.object(st, "file_uploader", return_value=None),
        patch(
            "adapters.visualization.tabs.weekly_brief.is_local_runtime",
            return_value=False,
        ),
        patch(
            "adapters.visualization.tabs.weekly_brief._render_onboarding_html",
            return_value="",
        ),
        patch.dict(st.session_state, {}, clear=True),
    ):
        _handle_onboarding()

    assert "ob_sample" in button_keys, "ob_sample button missing on first landing"
    # "Add manually" and toggle buttons are gone from the new design
    assert "ob_manual" not in button_keys, "ob_manual must not appear (removed)"
    assert "ob_csv_toggle" not in button_keys, "ob_csv_toggle must not appear (removed)"


def test_csv_uploader_always_visible_when_local_and_no_book() -> None:
    """file_uploader must render immediately (no toggle) when local and no book loaded."""
    import streamlit as st

    from adapters.visualization.tabs.weekly_brief import _handle_onboarding

    uploader_calls: list[int] = []

    def capture_uploader(*args: object, **kwargs: object) -> None:
        uploader_calls.append(1)
        return None

    # Local + no book → uploader renders directly (no toggle needed)
    with (
        patch.object(st, "markdown"),
        patch.object(st, "columns", return_value=[MagicMock(), MagicMock()]),
        patch.object(st, "button", return_value=False),
        patch.object(st, "file_uploader", side_effect=capture_uploader),
        patch(
            "adapters.visualization.tabs.weekly_brief.is_local_runtime",
            return_value=True,
        ),
        patch(
            "adapters.visualization.tabs.weekly_brief._render_onboarding_html",
            return_value="",
        ),
        patch.dict(st.session_state, {}, clear=True),
    ):
        _handle_onboarding()

    assert (
        len(uploader_calls) == 1
    ), "file_uploader must render without toggle when local"


def test_csv_uploader_not_shown_when_not_local() -> None:
    """file_uploader must NOT render in hosted/remote mode (privacy gate)."""
    import streamlit as st

    from adapters.visualization.tabs.weekly_brief import _handle_onboarding

    uploader_calls: list[int] = []

    def capture_uploader(*args: object, **kwargs: object) -> None:
        uploader_calls.append(1)
        return None

    with (
        patch.object(st, "markdown"),
        patch.object(st, "columns", return_value=[MagicMock(), MagicMock()]),
        patch.object(st, "button", return_value=False),
        patch.object(st, "file_uploader", side_effect=capture_uploader),
        patch.object(st, "info"),
        patch(
            "adapters.visualization.tabs.weekly_brief.is_local_runtime",
            return_value=False,
        ),
        patch(
            "adapters.visualization.tabs.weekly_brief._render_onboarding_html",
            return_value="",
        ),
        patch.dict(st.session_state, {}, clear=True),
    ):
        _handle_onboarding()

    assert (
        len(uploader_calls) == 0
    ), "file_uploader must NOT render when not local (privacy gate breach)"


def test_css_buttons_full_width_and_petrol() -> None:
    """CSS description: buttons are full-width, 46px min-height, IBM Plex Sans, petrol."""
    from adapters.visualization.components.styles import GLOBAL_CSS

    # Full-width rule
    assert (
        "width: 100% !important" in GLOBAL_CSS
    ), "button width:100% missing from GLOBAL_CSS"
    assert "min-height: 46px !important" in GLOBAL_CSS, "button min-height:46px missing"
    # Primary petrol fill
    assert "#0F6E80" in GLOBAL_CSS, "petrol #0F6E80 missing from GLOBAL_CSS"
    # File uploader has dashed petrol border and hides size hint small
    assert (
        "stFileUploaderDropzoneInstructions" in GLOBAL_CSS
    ), "file uploader size-hint hide rule missing"
    assert "dashed" in GLOBAL_CSS, "file uploader dashed border missing"
