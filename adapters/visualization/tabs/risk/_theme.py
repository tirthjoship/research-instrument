"""Shared colour constants and strip helpers."""

from __future__ import annotations

from adapters.visualization.components.evidence_chip import render_evidence_chip_by_key
from domain.evidence_registry import get_evidence

# ── colour constants (mirror risk-v8.html :root) ───────────────────────────
_OK = "#15803d"
_OK_L = "#e7f4ec"
_AMBER = "#b45309"
_AMBER_L = "#fbf0dc"
_AMBER_B = "#ecdcb6"
_G0 = "#E2E8F0"
_G1 = "#94A3B8"
_G2 = "#475569"
_INK = "#0f1c1f"
_MUT = "#5b7178"
_FAINT = "#94a8ad"
_LINE = "#dde7e9"
_CARD = "#ffffff"
_PETROL = "#0F6E80"
_PETROL_L = "#e6f1f3"
_PETROL_D = "#0a5260"

_FLAG_MEANING = {
    "SYSTEMATIC_DOMINANT": (
        "Most of the book's movement is one market-wide bet, not stock picking.",
        "Adding 'one more name' will not diversify this — only a different asset class or hedge changes it.",
    ),
    "FACTOR_DOMINANCE": (
        "One macro factor (e.g. the market or rates) explains an outsized share of risk.",
        "Check whether you MEANT to make that macro bet; trim names that all load on it if not.",
    ),
    "DRIFT": (
        "The book's factor mix moved materially since the last review.",
        "Re-read the latest weekly brief and confirm the new tilt is intentional.",
    ),
}

_FACTOR_DISPLAY_NAMES: dict[str, str] = {
    "SPY": "Market",
    "SMB": "Size",
    "HML": "Value",
    "MOM": "Momentum",
    "RMW": "Profitability",
    "CMA": "Investment",
    "TLT": "Rates 10Y",
    "UUP": "US Dollar",
    "XLE": "Energy",
}

_FACTOR_GLOSSARY_TERMS: dict[str, str] = {
    "SPY": "Market (SPY)",
    "SMB": "Size (SMB)",
    "HML": "Value (HML)",
    "MOM": "Momentum (MOM)",
    "RMW": "Profitability (RMW)",
    "CMA": "Investment (CMA)",
    "TLT": "Rates (TLT)",
    "UUP": "US Dollar (UUP)",
    "XLE": "Energy (XLE)",
}

# ── Shared scale parameters for the beta strip (0..100 %) ──────────────────
_BETA_DOMAIN_LO = -0.5
_BETA_DOMAIN_HI = 2.0
_BETA_DOMAIN_RANGE = _BETA_DOMAIN_HI - _BETA_DOMAIN_LO
_SHARE_FLAG_PCT = 60.0  # 60% flag line on the systematic-share strip

__all__ = [
    "_OK",
    "_OK_L",
    "_AMBER",
    "_AMBER_L",
    "_AMBER_B",
    "_G0",
    "_G1",
    "_G2",
    "_INK",
    "_MUT",
    "_FAINT",
    "_LINE",
    "_CARD",
    "_PETROL",
    "_PETROL_L",
    "_PETROL_D",
    "_FLAG_MEANING",
    "_FACTOR_DISPLAY_NAMES",
    "_FACTOR_GLOSSARY_TERMS",
    "_BETA_DOMAIN_LO",
    "_BETA_DOMAIN_HI",
    "_BETA_DOMAIN_RANGE",
    "_SHARE_FLAG_PCT",
    "_strip_pct",
    "_metric_evidence",
    "_band_text",
]


# ---------------------------------------------------------------------------
# Helper: clamp + map a value to 0..100% on a [lo, hi] strip
# ---------------------------------------------------------------------------


def _strip_pct(value: float, lo: float, hi: float) -> float:
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0))


# ---------------------------------------------------------------------------
# Helper: inline evidence chip for a registry metric key
# ---------------------------------------------------------------------------


def _metric_evidence(key: str, *, margin_top: int = 7) -> str:
    """Return an inline evidence chip for *key*, wrapped for vertical spacing.

    Renders the registry-backed chip (label + verdict badge + ADR + hover tooltip
    carrying meaning / healthy band / caveat).  Returns ``""`` for an unregistered
    key so callers can splice it unconditionally.
    """
    chip = render_evidence_chip_by_key(key)
    if not chip:
        return ""
    return f'<div style="margin-top:{margin_top}px">{chip}</div>'


def _band_text(key: str) -> str:
    """Return the registry healthy-band string for *key* (empty if none)."""
    entry = get_evidence(key)
    if entry is None or entry.healthy_band is None:
        return ""
    return entry.healthy_band


# ===========================================================================
# Section composers — each returns an HTML string
# ===========================================================================
