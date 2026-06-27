from __future__ import annotations

from unittest.mock import patch

import streamlit as st

from adapters.visualization.components.onboarding import (
    render_landing_door_html,
    render_sample_banner_html,
)
from adapters.visualization.components.styles import GLOBAL_CSS
from adapters.visualization.tabs.weekly_brief import _handle_onboarding


class _StreamlitCtx:
    def __enter__(self) -> "_StreamlitCtx":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


def test_door_local_shows_privacy_copy() -> None:
    """Local: privacy copy present, heading present, no dead HTML buttons."""
    html = render_landing_door_html(local=True)
    assert "stays on your machine" in html.lower()
    assert "Load a book to begin" in html
    assert "<button" not in html


def test_door_hosted_hides_privacy_and_upload() -> None:
    html = render_landing_door_html(local=False)
    assert "stays on your machine" not in html.lower()
    assert "isn't running local-only" in html
    assert "Load a book to begin" in html
    assert "<button" not in html


def test_door_no_dead_html_buttons_local() -> None:
    html = render_landing_door_html(local=True)
    assert "<button" not in html


def test_door_no_dead_html_buttons_hosted() -> None:
    html = render_landing_door_html(local=False)
    assert "<button" not in html


def test_privacy_copy_never_shown_when_not_local() -> None:
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


def test_sample_banner_has_ob_class() -> None:
    html = render_sample_banner_html()
    assert "ob-sample-banner" in html
    assert "Sample book" in html
    assert "Active book" not in html


def test_sample_book_loaded_on_first_landing() -> None:
    """_handle_onboarding loads sample book and inline uploader when local."""
    uploader_labels: list[str] = []
    session_state: dict[str, object] = {}

    def capture_uploader(label: str, **kwargs: object) -> None:
        uploader_labels.append(label)
        return None

    with (
        patch.object(st, "markdown"),
        patch.object(st, "container", return_value=_StreamlitCtx()),
        patch.object(st, "file_uploader", side_effect=capture_uploader),
        patch(
            "adapters.visualization.tabs.weekly_brief.holdings_upload_enabled",
            return_value=True,
        ),
        patch(
            "adapters.visualization.tabs.weekly_brief.load_sample_book",
            return_value=[],
        ),
        patch("streamlit.session_state", session_state),
    ):
        _handle_onboarding()

    assert "book" in session_state
    assert session_state.get("is_sample_book") is True
    assert uploader_labels == ["Upload your holdings"]


def test_user_holdings_still_shows_sample_banner_upload() -> None:
    """Uploaded holdings use user book data but keep the sample-book banner + upload CTA."""
    uploader_labels: list[str] = []
    session_state: dict[str, object] = {"book": [], "is_sample_book": False}

    def capture_uploader(label: str, **kwargs: object) -> None:
        uploader_labels.append(label)
        return None

    with (
        patch.object(st, "markdown"),
        patch.object(st, "container", return_value=_StreamlitCtx()),
        patch.object(st, "file_uploader", side_effect=capture_uploader),
        patch(
            "adapters.visualization.tabs.weekly_brief.holdings_upload_enabled",
            return_value=True,
        ),
        patch("streamlit.session_state", session_state),
    ):
        _handle_onboarding()

    assert uploader_labels == ["Upload your holdings"]


def test_csv_uploader_hidden_when_not_local() -> None:
    uploader_calls: list[int] = []
    session_state: dict[str, object] = {}

    def capture_uploader(*_args: object, **_kwargs: object) -> None:
        uploader_calls.append(1)
        return None

    with (
        patch.object(st, "markdown"),
        patch.object(st, "container", return_value=_StreamlitCtx()),
        patch.object(st, "file_uploader", side_effect=capture_uploader),
        patch(
            "adapters.visualization.tabs.weekly_brief.holdings_upload_enabled",
            return_value=False,
        ),
        patch(
            "adapters.visualization.tabs.weekly_brief.load_sample_book",
            return_value=[],
        ),
        patch("streamlit.session_state", session_state),
    ):
        _handle_onboarding()

    assert len(uploader_calls) == 0


def test_css_onboarding_row_and_upload_tooltip() -> None:
    assert "ob-sample-banner" in GLOBAL_CSS
    assert 'aria-label="Upload your holdings"' in GLOBAL_CSS
    assert "--ob-csv-upload-tip" in GLOBAL_CSS
    assert "book value (cad)" in GLOBAL_CSS
    assert "button *" in GLOBAL_CSS
