from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class WebhookPayload(BaseModel):
    """Validated market signal received from TradingView or another upstream producer."""

    model_config = ConfigDict(extra="allow")

    symbol: str = Field(..., min_length=1)
    timeframe: str = Field(..., min_length=1)
    action: Literal["BUY", "SELL"]
    price: float = Field(..., gt=0)

    drawdown_pct: float = Field(default=0.0, ge=0.0)
    strategy_rank: Literal["TOP", "MID", "LOW", "UNKNOWN"] = "UNKNOWN"
    position_size: float = Field(default=1.0, gt=0)

    # Optional upstream risk levels.
    tv_sl: Optional[float] = Field(default=None, gt=0)
    tv_tp: Optional[float] = Field(default=None, gt=0)
    timestamp: Optional[str] = None

    # Optional upstream market context. TradingView/Pine can populate these directly.
    htf_bias: Literal["BULLISH", "BEARISH", "NEUTRAL"] = "NEUTRAL"
    htf_alignment: Optional[bool] = None
    price_zone: Literal["PREMIUM", "DISCOUNT", "EQUILIBRIUM", "UNKNOWN"] = "UNKNOWN"
    bos: bool = False
    choch: bool = False
    liquidity_sweep: bool = False
    order_block: bool = False
    fvg_imbalance: bool = False
    inducements: bool = False
    displacement: bool = False
    sweep_confirmed: bool = False
    liquidity_approaching: bool = False

    # Optional liquidity levels.
    pdh: Optional[float] = Field(default=None, gt=0)
    pdl: Optional[float] = Field(default=None, gt=0)
    eqh: Optional[float] = Field(default=None, gt=0)
    eql: Optional[float] = Field(default=None, gt=0)
    sweep_level: Optional[float] = Field(default=None, gt=0)

    # Optional news decision supplied by a trusted upstream calendar integration.
    news_clear: Optional[bool] = None
    news_reason: Optional[str] = None

    # Free-form context for future TradingView fields.
    extra: Dict[str, Any] = Field(default_factory=dict)


class SMCConditions(BaseModel):
    """Structured record of the SMC conditions detected for a signal."""

    liquidity_sweep: bool = False
    order_block: bool = False
    fvg_imbalance: bool = False
    bos: bool = False
    choch: bool = False
    inducements: bool = False
    displacement: bool = False
    sweep_confirmed: bool = False
    liquidity_approaching: bool = False


class TradeAnalysis(BaseModel):
    """Final explainable analysis result emitted by the decision pipeline."""

    symbol: str
    action: Literal["BUY", "SELL"]
    entry_price: float
    sl_price: float
    tp_price: float
    tp2_price: Optional[float] = None
    rr_ratio: float

    confidence_score: float
    trade_quality: str
    position_size: float
    system_state: str = "NORMAL"
    equity_state: str = "NORMAL"
    drawdown_pct: float = 0.0

    htf_alignment: bool
    trend_alignment: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    session: str
    risk_level: Literal["LOW", "NORMAL", "HIGH", "AGGRESSIVE"] = "LOW"
    position_reasoning: str = ""

    smc_conditions: SMCConditions
    reasoning: List[str] = Field(default_factory=list)
    strategies_used: List[str] = Field(default_factory=list)
    bias: str = "NEUTRAL"
    price_zone: str = "UNKNOWN"
    strategy_rank: str = "UNKNOWN"
    decision_trace: Optional[dict] = None

    news_clear: bool
    news_reason: str = "No critical news window active."

    is_valid: bool = True
    invalidation_reason: Optional[str] = None

    def validate_trade(self) -> None:
        """Apply final hard validation rules before an alert is sent."""
        if not self.news_clear:
            self.is_valid = False
            self.invalidation_reason = f"Blocked: {self.news_reason}"
            return

        if self.trade_quality == "LOW":
            self.is_valid = False
            self.invalidation_reason = "Blocked: Trade quality rated LOW."
            return

        if self.rr_ratio < 1.5:
            self.is_valid = False
            self.invalidation_reason = (
                f"Blocked: insufficient risk-to-reward ({self.rr_ratio} < 1.5)."
            )
            return

        if not self.htf_alignment:
            self.is_valid = False
            self.invalidation_reason = "Blocked: lower timeframe contradicts HTF bias."
            return

        if self.action == "BUY" and not self.tp_price > self.entry_price:
            self.is_valid = False
            self.invalidation_reason = "Blocked: BUY target is not above entry."
            return

        if self.action == "SELL" and not self.tp_price < self.entry_price:
            self.is_valid = False
            self.invalidation_reason = "Blocked: SELL target is not below entry."
            return

        if self.action == "BUY" and not self.sl_price < self.entry_price:
            self.is_valid = False
            self.invalidation_reason = "Blocked: BUY stop loss is not below entry."
            return

        if self.action == "SELL" and not self.sl_price > self.entry_price:
            self.is_valid = False
            self.invalidation_reason = "Blocked: SELL stop loss is not above entry."
            return
