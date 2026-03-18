from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

class WebhookPayload(BaseModel):
    """Payload received from TradingView via Webhook."""
    symbol: str = Field(..., description="Trading pair symbol (e.g., XAUUSD)")
    timeframe: str = Field(..., description="Chart timeframe")
    action: Literal["BUY", "SELL"]
    drawdown_pct: float = Field(0.0, description="Current drawdown percentage")
    strategy_rank: Literal["TOP", "MID", "LOW", "UNKNOWN"] = Field("UNKNOWN", description="V8 Strategy intelligence rank")
    price: float = Field(..., description="Current market price at signal generation")
    position_size: float = Field(default=1.0)
    # Optional fields from TV that we will validate against our internal engines
    tv_sl: Optional[float] = None
    tv_tp: Optional[float] = None
    timestamp: Optional[str] = None

class SMCConditions(BaseModel):
    """Track exactly which SMC elements were detected."""
    liquidity_sweep: bool = False
    order_block: bool = False
    fvg_imbalance: bool = False
    bos: bool = False
    choch: bool = False
    inducements: bool = False
    displacement: bool = False  # Track if there was strong momentum after structure break
    sweep_confirmed: bool = False # Track if sweep had reaction
    liquidity_approaching: bool = False # Track if price is proactively drawing to a specific pool

class TradeAnalysis(BaseModel):
    """Comprehensive analysis result after processing through all engines."""
    symbol: str
    action: Literal["BUY", "SELL"]
    entry_price: float
    
    # Target and Risk Output
    sl_price: float
    tp_price: float
    tp2_price: Optional[float] = None
    rr_ratio: float
    
    # Meta
    confidence_score: float
    trade_quality: str
    position_size: float
    system_state: str = "NORMAL"
    equity_state: str = "NORMAL"
    drawdown_pct: float = 0.0
    
    # Analysis Details
    htf_alignment: bool
    trend_alignment: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    session: str
    risk_level: Literal["LOW", "NORMAL", "HIGH", "AGGRESSIVE"] = "LOW"
    position_reasoning: str = ""
    
    # Explainability Data
    smc_conditions: SMCConditions
    reasoning: List[str]
    strategies_used: List[str]
    bias: str = "NEUTRAL"
    price_zone: str = "UNKNOWN"
    strategy_rank: str = "UNKNOWN"
    decision_trace: Optional[dict] = None
    
    # News filter metadata
    news_clear: bool
    news_reason: str = "No critical news windows active."
    
    # Signal Validation
    is_valid: bool = True
    invalidation_reason: Optional[str] = None

    def validate_trade(self) -> None:
        """Validates the trade and sets rejection flags if constraints are violated."""
        if not self.news_clear:
            self.is_valid = False
            self.invalidation_reason = f"Blocked: {self.news_reason}"
            return
            
        if self.trade_quality == "LOW":
            self.is_valid = False
            self.invalidation_reason = "Blocked: Trade Quality rated LOW."
            return
            
        if self.rr_ratio < 1.5:
            self.is_valid = False
            self.invalidation_reason = f"Blocked: Insufficient Risk-To-Reward ({self.rr_ratio} < 1.5)."
            return
            
        if not self.htf_alignment:
            self.is_valid = False
            self.invalidation_reason = "Blocked: LTF contradicts HTF Bias."
            return
