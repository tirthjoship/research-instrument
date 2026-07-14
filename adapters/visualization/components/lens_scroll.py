"""Smooth-scroll shim for nav-bean anchors (Risk tab, Trust tab).

Nav beans are `<a class="<selector-class>" href="#some-id">` anchors. Native
hash-anchor clicks inside `st.markdown(unsafe_allow_html=True)` do NOT scroll
in Streamlit — the click mutates the URL hash, Streamlit treats it as a state
change and reruns, blanking the target instead of scrolling to it (verified
live via CDP on the Risk tab: `#safe` sat 897px down before the click and
vanished after).

This component intercepts the bean click client-side, `preventDefault`s the
disruptive hash navigation, and `scrollIntoView`s the matching section
heading. Delivered as a Streamlit v2 custom component (no iframe), so
`parentElement.ownerDocument` is the main document directly — same pattern
as `tab_loading.py`.

Parameterized by CSS selector + expected link count so each tab mounts its
own instance against its own anchors (e.g. Risk: `a.ri-lens`/3, Trust:
`a.tr-nav`/5) without cross-tab interference.
"""

from __future__ import annotations

import streamlit as st


def build_lens_scroll_js(selector: str = "a.ri-lens", count: int = 3) -> str:
    """ES module: wire each anchor matching *selector* to smooth-scroll to its href target."""
    return f"""
export default function({{ parentElement }}) {{
  const doc = parentElement.ownerDocument;
  function wire() {{
    const links = doc.querySelectorAll('{selector}');
    links.forEach((a) => {{
      if (a.dataset.lensWired) return;
      a.dataset.lensWired = '1';
      a.addEventListener('click', (e) => {{
        const href = a.getAttribute('href') || '';
        if (!href.startsWith('#')) return;
        const target = doc.getElementById(href.slice(1));
        if (target) {{
          e.preventDefault();
          target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }}
      }});
    }});
    return links.length;
  }}
  let tries = 0;
  const arm = setInterval(() => {{
    const n = wire();
    if (n >= {count} || ++tries > 40) clearInterval(arm);
  }}, 150);
}}
"""


def render_lens_scroll(
    selector: str = "a.ri-lens", count: int = 3, component_name: str = "scr_lens_scroll"
) -> None:
    """Mount the smooth-scroll shim (zero-height v2 component)."""
    component = st.components.v2.component(
        name=component_name,
        html="<div></div>",
        js=build_lens_scroll_js(selector, count),
    )
    component()
