"""CDP full-page dashboard screenshotter.

Launches Chrome headless, navigates to a Streamlit dashboard, optionally clicks
a tab, then captures a full-page PNG via the Chrome DevTools Protocol (CDP).

Usage::

    python scripts/screenshot_dashboard.py --port 8531 --tab 0 --out /tmp/baseline_home.png

The script uses a *separate* Chrome remote-debugging port (default 9222) so it
does not interfere with the Streamlit server port.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from typing import Any, cast

import requests
import websocket  # type: ignore[import-not-found]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("screenshot_dashboard")

# ──────────────────────────────────────────────
# CDP helpers
# ──────────────────────────────────────────────

_cdp_id = 0


def _next_id() -> int:
    global _cdp_id
    _cdp_id += 1
    return _cdp_id


def _send(
    ws: websocket.WebSocket, method: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Send a CDP command and return the matching response."""
    cmd_id = _next_id()
    payload = {"id": cmd_id, "method": method, "params": params or {}}
    ws.send(json.dumps(payload))
    log.debug("CDP → %s (id=%d)", method, cmd_id)

    # Read frames until we get the response for this command id.
    deadline = time.time() + 30
    while time.time() < deadline:
        raw = ws.recv()
        frame = json.loads(raw)
        if frame.get("id") == cmd_id:
            if "error" in frame:
                raise RuntimeError(f"CDP error for {method}: {frame['error']}")
            log.debug("CDP ← %s ok", method)
            return cast(dict[str, Any], frame.get("result", {}))
    raise TimeoutError(f"CDP response timeout for {method} (id={cmd_id})")


# ──────────────────────────────────────────────
# Chrome lifecycle
# ──────────────────────────────────────────────


def _launch_chrome(debug_port: int, user_data_dir: str) -> subprocess.Popen[bytes]:
    """Start headless Chrome with remote debugging."""
    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not os.path.exists(chrome_bin):
        # Fallback for CI / other platforms
        chrome_bin = (
            shutil.which("google-chrome")
            or shutil.which("chromium-browser")
            or "google-chrome"
        )

    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        f"--remote-debugging-port={debug_port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={user_data_dir}",
        "about:blank",
    ]
    log.info("Launching Chrome: port=%d", debug_port)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc


def _wait_for_devtools(debug_port: int, timeout: int = 15) -> str:
    """Poll /json until Chrome is ready; return the websocket URL for the page target."""
    url = f"http://localhost:{debug_port}/json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=2)
            targets = resp.json()
            for t in targets:
                if t.get("type") == "page":
                    ws_url: str = t["webSocketDebuggerUrl"]
                    log.info("DevTools ready: %s", ws_url)
                    return ws_url
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(
        f"Chrome DevTools did not become ready on port {debug_port} within {timeout}s"
    )


# ──────────────────────────────────────────────
# Streamlit-aware wait
# ──────────────────────────────────────────────


def _wait_for_tabs(
    ws: websocket.WebSocket, expected_count: int = 6, timeout: int = 60
) -> None:
    """Poll until tab buttons are present in the DOM."""
    deadline = time.time() + timeout
    log.info("Waiting for Streamlit tabs to render (up to %ds)…", timeout)
    while time.time() < deadline:
        result = _send(
            ws,
            "Runtime.evaluate",
            {
                "expression": "document.querySelectorAll('button[role=\"tab\"]').length",
                "returnByValue": True,
            },
        )
        count = result.get("result", {}).get("value", 0)
        log.debug("Tab buttons found: %d", count)
        if count >= expected_count:
            log.info("Tabs ready (%d buttons)", count)
            return
        time.sleep(1)
    raise TimeoutError(
        f"Streamlit tabs did not appear within {timeout}s (found {count} buttons, expected {expected_count})"
    )


# ──────────────────────────────────────────────
# Main screenshot routine
# ──────────────────────────────────────────────


def capture(
    streamlit_port: int,
    tab_index: int,
    out_path: str,
    debug_port: int = 9222,
) -> None:
    """Full pipeline: launch Chrome → navigate → click tab → screenshot."""
    user_data_dir = tempfile.mkdtemp(prefix="chrome_cdp_")
    proc: subprocess.Popen[bytes] | None = None

    try:
        proc = _launch_chrome(debug_port, user_data_dir)

        ws_url = _wait_for_devtools(debug_port)
        ws = websocket.create_connection(ws_url, timeout=30)

        try:
            # Enable Page domain
            _send(ws, "Page.enable")

            # Navigate to Streamlit
            streamlit_url = f"http://localhost:{streamlit_port}"
            log.info("Navigating to %s", streamlit_url)
            _send(ws, "Page.navigate", {"url": streamlit_url})

            # Wait for Streamlit SPA to finish initial render
            _wait_for_tabs(ws)

            # Click requested tab (0-indexed)
            log.info("Clicking tab index %d", tab_index)
            _send(
                ws,
                "Runtime.evaluate",
                {
                    "expression": f"document.querySelectorAll('button[role=\"tab\"]')[{tab_index}].click()",
                    "returnByValue": True,
                },
            )

            # Allow the tab content to re-render
            log.info("Waiting 3s for tab re-render…")
            time.sleep(3)

            # Force ancestor containers to full height so layout is complete
            force_layout_js = """
(function() {
    var selectors = [
        '[data-testid="stMain"]',
        '[data-testid="stApp"]',
        '.stApp',
        '#root',
    ];
    selectors.forEach(function(sel) {
        var el = document.querySelector(sel);
        if (el) {
            el.style.overflow = 'visible';
            el.style.height = 'auto';
        }
    });
    var container = document.querySelector('[data-testid="stMainBlockContainer"]');
    return container ? container.scrollHeight : document.body.scrollHeight;
})()
""".strip()

            result = _send(
                ws,
                "Runtime.evaluate",
                {"expression": force_layout_js, "returnByValue": True},
            )
            measured_height = result.get("result", {}).get("value", 1200)
            measured_height = max(measured_height, 1200)
            log.info("Measured scrollHeight: %dpx", measured_height)

            # Override device metrics to capture full height
            _send(
                ws,
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": 1280,
                    "height": measured_height,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )

            # Small pause to let layout reflow at new viewport size
            time.sleep(1)

            # Capture full-page screenshot
            log.info("Capturing screenshot…")
            screenshot_result = _send(
                ws,
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": True},
            )
            png_data = screenshot_result.get("data", "")
            if not png_data:
                raise RuntimeError("Page.captureScreenshot returned empty data")

            png_bytes = base64.b64decode(png_data)
            if len(png_bytes) < 10_000:
                raise RuntimeError(
                    f"Screenshot suspiciously small ({len(png_bytes)} bytes) — "
                    "Streamlit may not have rendered."
                )

            with open(out_path, "wb") as fh:
                fh.write(png_bytes)

            log.info(
                "Saved %s (%.1f KB, height≈%dpx)",
                out_path,
                len(png_bytes) / 1024,
                measured_height,
            )

        finally:
            ws.close()

    finally:
        if proc is not None:
            log.info("Terminating Chrome (pid=%d)", proc.pid)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(user_data_dir, ignore_errors=True)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CDP full-page screenshot of a Streamlit dashboard tab.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8531,
        help="Streamlit server port (default: 8531)",
    )
    parser.add_argument(
        "--tab",
        type=int,
        default=0,
        help="0-indexed tab to click before screenshot (default: 0)",
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output PNG file path",
    )
    parser.add_argument(
        "--debug-port",
        type=int,
        default=9222,
        help="Chrome remote-debugging port (default: 9222, must differ from --port)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.debug_port == args.port:
        raise ValueError("--debug-port must differ from --port")
    capture(
        streamlit_port=args.port,
        tab_index=args.tab,
        out_path=args.out,
        debug_port=args.debug_port,
    )


if __name__ == "__main__":
    main()
