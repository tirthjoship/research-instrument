"""Domain models for the research instrument.

Pure Python value objects. No pandas, numpy, or external ML/data imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .discipline import Verdict
from .exceptions import InvalidMarketDataError, InvalidPredictionError


@dataclass(frozen=True)
class Signal:
    """Immutable value object representing a market signal at a point in time.

    Attributes:
        symbol: Ticker symbol.
        timestamp: As-of time for the signal (no future data).
        price: Price at timestamp.
        volume: Volume at timestamp.
        open_: Open price (field name avoids 'open' builtin).
        high: High price.
        low: Low price.
    """

    symbol: str
    timestamp: datetime
    price: float
    volume: float
    open_: float
    high: float
    low: float

    def __post_init__(self) -> None:
        if self.price < 0 or self.volume < 0:
            raise InvalidMarketDataError("Price and volume must be non-negative")


@dataclass(frozen=True)
class Sentiment:
    """Immutable value object representing a sentiment signal.

    Attributes:
        source: Source identifier (e.g. 'news', 'twitter', 'reddit').
        timestamp: As-of time (must be <= prediction time).
        sentiment_score: Score in [-1.0, 1.0].
        confidence: Confidence in [0.0, 1.0].
        text_snippet: Optional snippet for audit.
    """

    source: str
    timestamp: datetime
    sentiment_score: float
    confidence: float
    text_snippet: str | None = None

    def __post_init__(self) -> None:
        if not -1.0 <= self.sentiment_score <= 1.0:
            raise InvalidMarketDataError(
                f"Sentiment score must be in [-1, 1], got {self.sentiment_score}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise InvalidPredictionError(
                f"Confidence must be in [0, 1], got {self.confidence}"
            )


@dataclass(frozen=True)
class BacktestResult:
    """Immutable value object representing a single backtest run result.

    Attributes:
        run_id: Unique identifier for the run.
        symbol: Ticker symbol.
        prediction_time: Time at which prediction was made (point-in-time).
        actual_return: Realized return over the evaluation window.
        predicted_return: Model-predicted return.
        model_version: Version of the model used.
    """

    run_id: str
    symbol: str
    prediction_time: datetime
    actual_return: float
    predicted_return: float
    model_version: str

    def __post_init__(self) -> None:
        pass  # Optional: add bounds on returns if desired


class RecommendationGrade(Enum):
    """5-tier grading system for stock recommendations."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    MAY_SELL = "may_sell"
    IMMEDIATE_SELL = "immediate_sell"


@dataclass(frozen=True)
class MultiHorizonPrediction:
    """Predicted returns at 2-day, 5-day, and 10-day horizons."""

    predicted_return_2d: float
    predicted_return_5d: float
    predicted_return_10d: float
    confidence_2d: float
    confidence_5d: float
    confidence_10d: float

    def __post_init__(self) -> None:
        for field_name in ("confidence_2d", "confidence_5d", "confidence_10d"):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise InvalidPredictionError(
                    f"Confidence must be in [0, 1], got {value}"
                )


@dataclass(frozen=True)
class StockRecommendation:
    """A graded stock recommendation for a given week."""

    symbol: str
    week_start: str
    grade: RecommendationGrade
    composite_score: float
    prediction: MultiHorizonPrediction
    horizon_signals: dict[str, str]
    reasoning: str
    sources: list[str]
    sentiment_score: float | None = None
    divergence_score: float | None = None
    divergence_type: str | None = None
    technical_signal: float | None = None
    rsi_14: float | None = None
    macd: float | None = None


@dataclass(frozen=True)
class AccuracyRecord:
    """Historical record comparing predicted vs actual returns."""

    symbol: str
    week_start: str
    predicted_grade: str
    predicted_return_2d: float
    predicted_return_5d: float
    predicted_return_10d: float
    actual_return_2d: float
    actual_return_5d: float
    actual_return_10d: float
    direction_correct_2d: bool
    direction_correct_5d: bool
    direction_correct_10d: bool


@dataclass(frozen=True)
class EvaluationRun:
    """Record of a single evaluation metric from a validation run."""

    run_date: str
    eval_type: str
    horizon: str
    metric_name: str
    metric_value: float
    p_value: float | None = None
    regime: str | None = None
    details: str | None = None


@dataclass(frozen=True)
class WeeklyReport:
    """Aggregated weekly report with recommendations and performance."""

    report_date: str
    market: str
    recommendations: list[StockRecommendation]
    accuracy_vs_last_week: float | None = None
    spy_return_same_period: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    transaction_costs: float | None = None


@dataclass(frozen=True)
class BuzzSignal:
    """A single buzz/sentiment observation from a news or social source."""

    ticker: str
    source: str  # e.g., "reuters_rss", "reddit_wsb"
    mention_count: int
    sentiment_raw: float  # [-1, 1] from keyword or Flan-T5 scorer
    scorer: str  # "keyword" or "flan_t5"
    fetched_at: datetime
    article_hash: str  # dedup key
    article_text: str | None = None  # headline+summary for downstream scoring

    def __post_init__(self) -> None:
        if self.mention_count < 0:
            raise ValueError("mention_count must be >= 0")
        if not -1.0 <= self.sentiment_raw <= 1.0:
            raise ValueError("sentiment_raw must be in [-1, 1]")


@dataclass(frozen=True)
class AttentionPoint:
    """A single attention-intensity observation (search interest, pageviews).

    Distinct from BuzzSignal (discrete events): this is a magnitude at a point
    in time. Scale is source-relative (GT index 0-100, Wikipedia raw views);
    divergence uses scale-free ratios so no normalization is needed.
    """

    ticker: str
    timestamp: datetime
    value: float  # >= 0; source-relative intensity
    source: str  # e.g. "google_trends", "wikipedia"

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("attention value must be >= 0")


@dataclass(frozen=True)
class SourceReliability:
    """Tracks per-source directional accuracy over time."""

    source: str
    ticker: str | None  # None = aggregate across all tickers
    correct_calls: int
    total_calls: int

    def __post_init__(self) -> None:
        if self.correct_calls < 0:
            raise ValueError("correct_calls must be >= 0")
        if self.total_calls < 0:
            raise ValueError("total_calls must be >= 0")
        if self.correct_calls > self.total_calls:
            raise ValueError("correct_calls cannot exceed total_calls")

    @property
    def accuracy(self) -> float:
        if self.total_calls < 10:
            return 0.5
        return self.correct_calls / self.total_calls


_VALID_SIGNAL_TYPES = frozenset(
    {"crash_risk", "negative_sentiment", "technical_breakdown", "stop_loss"}
)
_VALID_URGENCIES = frozenset({"immediate", "this_week", "watch"})


@dataclass(frozen=True)
class Holding:
    """A portfolio holding."""

    symbol: str
    quantity: float
    purchase_price: float
    purchase_date: str  # YYYY-MM-DD
    notes: str = ""

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.purchase_price <= 0:
            raise ValueError("purchase_price must be positive")


@dataclass(frozen=True)
class SellSignal:
    """A sell signal for a held stock."""

    symbol: str
    signal_date: str
    signal_type: str
    urgency: str
    reasoning: str
    confidence: float

    def __post_init__(self) -> None:
        if self.signal_type not in _VALID_SIGNAL_TYPES:
            raise ValueError(
                f"signal_type must be one of {_VALID_SIGNAL_TYPES}, got '{self.signal_type}'"
            )
        if self.urgency not in _VALID_URGENCIES:
            raise ValueError(
                f"urgency must be one of {_VALID_URGENCIES}, got '{self.urgency}'"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")


_VALID_RELATIONSHIP_TYPES = frozenset(
    {"auto_correlation", "supply_chain", "granger_causal"}
)
_VALID_EDGE_SOURCES = frozenset({"computed", "manual_yaml"})


@dataclass(frozen=True)
class CorrelationEdge:
    """A directed relationship between two tickers."""

    leader: str
    follower: str
    correlation: float  # [-1.0, 1.0]
    lag_days: int  # 0-5
    relationship_type: str  # auto_correlation | supply_chain | granger_causal
    source: str  # computed | manual_yaml

    def __post_init__(self) -> None:
        if not -1.0 <= self.correlation <= 1.0:
            raise ValueError("correlation must be in [-1.0, 1.0]")
        if not 0 <= self.lag_days <= 5:
            raise ValueError("lag_days must be in [0, 5]")
        if self.relationship_type not in _VALID_RELATIONSHIP_TYPES:
            raise ValueError(
                f"relationship_type must be one of {_VALID_RELATIONSHIP_TYPES}"
            )
        if self.source not in _VALID_EDGE_SOURCES:
            raise ValueError(f"source must be one of {_VALID_EDGE_SOURCES}")


class EventCategory(Enum):
    """News event categories for causal impact analysis."""

    EARNINGS_SURPRISE = "earnings_surprise"
    TARIFF_TRADE = "tariff_trade"
    FDA_APPROVAL = "fda_approval"
    INTEREST_RATE = "interest_rate"
    ANTITRUST_REGULATION = "antitrust_regulation"
    GEOPOLITICAL = "geopolitical"
    LABOR_LAYOFFS = "labor_layoffs"
    SUPPLY_CHAIN_DISRUPTION = "supply_chain_disruption"
    PRODUCT_LAUNCH = "product_launch"
    MACRO_DATA = "macro_data"
    GOVERNMENT_INVESTMENT = "government_investment"


@dataclass(frozen=True)
class SourceHealth:
    """Per-source ingestion tally. Makes throttling visible, never silent."""

    source: str
    attempts: int = 0
    ok: int = 0
    empty: int = 0
    throttled: int = 0
    failed: int = 0

    def merge(self, other: "SourceHealth") -> "SourceHealth":
        if other.source != self.source:
            raise ValueError("cannot merge SourceHealth across different sources")
        return SourceHealth(
            source=self.source,
            attempts=self.attempts + other.attempts,
            ok=self.ok + other.ok,
            empty=self.empty + other.empty,
            throttled=self.throttled + other.throttled,
            failed=self.failed + other.failed,
        )


@dataclass(frozen=True)
class ClassifiedEvent:
    """A news event classified into a category with direction."""

    headline: str
    event_date: str  # YYYY-MM-DD
    category: EventCategory
    direction: int  # -1, 0, 1 (bearish, neutral, bullish)
    confidence: float  # 0-1
    source: str  # "gdelt", "rss", etc.

    def __post_init__(self) -> None:
        if self.direction not in (-1, 0, 1):
            raise ValueError("direction must be -1, 0, or 1")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True)
class EventSectorImpact:
    """Learned impact of an event category on a sector."""

    category: EventCategory
    sector: str
    magnitude: float  # avg absolute return impact
    half_life_days: float  # exponential decay half-life
    sample_count: int  # number of historical events used to learn this

    def __post_init__(self) -> None:
        if self.half_life_days <= 0:
            raise ValueError("half_life_days must be positive")
        if self.sample_count < 0:
            raise ValueError("sample_count must be non-negative")


@dataclass(frozen=True)
class PositionRisk:
    """Graded risk/discipline assessment for one held position (decision-support,
    not a prediction)."""

    ticker: str
    price: float
    verdict: Verdict
    confidence: float
    trend_health: float | None
    vol_signal: float
    relative_strength: float | None
    downside_to_stop: float
    upside_to_recover: float
    behavior_flags: tuple[str, ...]
    unrealized_pct: float
    account_type: str
    abstained: bool
    why: str
    quantity: float = 0.0
    market_value_cad: float | None = None  # None = FX/price unavailable, fail loud

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise InvalidPredictionError(
                f"Confidence must be in [0, 1], got {self.confidence}"
            )


@dataclass(frozen=True)
class PortfolioRisk:
    """Book-level risk summary across all held positions."""

    n_positions: int
    broken_trend_share: float
    top_concentration: float
    verdict_counts: dict[str, int]


# --- Macro-beta scrubber (Unit A, ADR-052) -------------------------------


@dataclass(frozen=True)
class MacroFactorBeta:
    """Per-factor sensitivity for one holding or the book.

    beta_headline: 252-day window. beta_recent: 63-day window.
    drift = beta_recent - beta_headline (positive = exposure rising).
    """

    factor: str
    beta_headline: float
    beta_recent: float
    drift: float


@dataclass(frozen=True)
class HoldingMacroExposure:
    """One holding's macro betas plus its systematic share (headline R^2)."""

    ticker: str
    weight: float  # fraction of covered book market value
    betas: tuple[MacroFactorBeta, ...]
    r_squared: float


@dataclass(frozen=True)
class MacroBetaFlag:
    """A surfaced CRO flag. value/threshold are heuristic dials, not edges."""

    kind: str  # "SYSTEMATIC_DOMINANT" | "FACTOR_DOMINANCE" | "DRIFT"
    factor: str | None
    message: str
    value: float
    threshold: float


@dataclass(frozen=True)
class BookMacroExposure:
    """Book-level macro exposure summary for the weekly brief."""

    as_of: str
    factors: tuple[str, ...]
    net_beta_by_factor: dict[str, float]  # dollar-weighted Sum w_i * beta_i
    systematic_share: float  # book-level R^2 (macro-explained variance)
    idiosyncratic_share: float  # 1 - systematic_share
    dominant_factor: str | None
    flags: tuple[MacroBetaFlag, ...]
    holdings: tuple[HoldingMacroExposure, ...]
    coverage_holdings: int
    total_holdings: int
    coverage_value_frac: float

    # v8 risk-stats fields — all defaulted so existing constructions stay unchanged
    enb: float = 0.0
    """Effective number of bets (portfolio concentration measure)."""
    pc_variance: tuple[float, ...] = ()
    """Fraction of book variance explained by each principal component."""
    pc_labels: tuple[str, ...] = ()
    """Human-readable labels for each principal component."""
    pc_labels_data_gap: bool = False
    """True when principal-component labels could not be assigned (data gap)."""
    systematic_share_adj: float = 0.0
    """Systematic share adjusted for estimation uncertainty."""
    systematic_share_ci: tuple[float, float] = (0.0, 0.0)
    """90 % bootstrap interval (low, high) for systematic share."""
    beta_ci_by_factor: dict[str, tuple[float, float]] = field(default_factory=dict)
    """90 % bootstrap intervals (low, high) for net beta, keyed by factor."""
    suppressed_factors: tuple[str, ...] = ()
    """Factors whose beta CI straddles zero — not shown as a real exposure."""
    downside_beta: float = 0.0
    """Beta estimated on down-market periods only (proxy for tail sensitivity)."""
    risk_contribution: dict[str, float] = field(default_factory=dict)
    """Fractional contribution to total portfolio variance, keyed by ticker."""
    holdings_meta: tuple[dict[str, object], ...] = ()
    """Per-holding metadata (ticker, name, sector, weight) for display."""
    sector_weights: dict[str, float] = field(default_factory=dict)
    """Aggregate portfolio weight by GICS sector."""
    sector_hhi: float = 0.0
    """Herfindahl-Hirschman Index of sector weights (sector concentration)."""
    sector_gaps: tuple[str, ...] = ()
    """Sectors with zero exposure relative to a reference benchmark."""
    vif_by_factor: dict[str, float] = field(default_factory=dict)
    """Variance Inflation Factor for each factor (multicollinearity diagnostic)."""
    diversification_ratio: float = 1.0
    """Ratio of weighted-average volatility to portfolio volatility."""
    sys_share_history: tuple[tuple[str, float], ...] = ()
    """Time series of (date_str, systematic_share) for trend display."""
