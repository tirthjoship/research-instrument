from __future__ import annotations

from adapters.visualization.components.onboarding import render_landing_door_html


def test_door_local_shows_privacy_and_upload() -> None:
    html = render_landing_door_html(local=True)
    assert "stays on your machine" in html.lower()
    assert "Upload holdings CSV" in html
    assert "Explore sample book" in html


def test_door_hosted_hides_privacy_and_upload() -> None:
    html = render_landing_door_html(local=False)
    assert "stays on your machine" not in html.lower()  # no false promise
    assert "Upload holdings CSV" not in html  # upload hidden
    assert "isn't running local-only" in html  # honest notice
    assert "Explore sample book" in html  # sample still ok
