"""Lens-nav smooth-scroll shim for the Risk tab.

The Risk-tab lens beans are `<a class="ri-lens" href="#safe|#do|#teach">` anchors.
Native hash-anchor clicks inside `st.markdown(unsafe_allow_html=True)` do NOT scroll
in Streamlit — the click mutates the URL hash, Streamlit treats it as a state change
and reruns, blanking the target instead of scrolling to it (verified live via CDP:
`#safe` sat 897px down before the click and vanished after).

This component intercepts the bean click client-side, `preventDefault`s the disruptive
hash navigation, and `scrollIntoView`s the matching section heading. Delivered as a
Streamlit v2 custom component (no iframe), so `parentElement.ownerDocument` is the main
document directly — same pattern as `tab_loading.py`.
"""

from __future__ import annotations

import streamlit as st

# Number of lens beans to wire (Am I safe? / What do I do? / Teach me).
_LENS_COUNT = 3


def build_lens_scroll_js() -> str:
    """ES module: wire each `.ri-lens` anchor to smooth-scroll to its href target."""
    return f"""
export default function({{ parentElement }}) {{
  const doc = parentElement.ownerDocument;
  function wire() {{
    const links = doc.querySelectorAll('a.ri-lens');
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
    if (n >= {_LENS_COUNT} || ++tries > 40) clearInterval(arm);
  }}, 150);
}}
"""


def render_lens_scroll() -> None:
    """Mount the lens-scroll shim (zero-height v2 component)."""
    component = st.components.v2.component(
        name="scr_lens_scroll",
        html="<div></div>",
        js=build_lens_scroll_js(),
    )
    component()
