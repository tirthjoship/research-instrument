from __future__ import annotations

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
