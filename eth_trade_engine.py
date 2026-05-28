"""ETH 合约完整决策引擎 — 融合 Alpha Skills 五技能核心逻辑
  edge-strategy-reviewer (C1-C8) + position-sizer + scenario-analyzer
  + technical-analyst + signal-postmortem
"""
import json, os, time
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

TZ = timezone(timedelta(hours=8))
TRADE_LOG = os.path.expanduser("~/trades.json")

# ============================================================
# 1. position-sizer: Fixed Fractional (适配 125x 空单)
# ============================================================

@dataclass
class PositionResult:
    account: float
    entry: float
    stop: float
    take_profit: float
    risk_pct: float
    leverage: int
    margin: float
    position_size: float
    risk_usd: float
    reward_usd: float
    rr: float

def position_sizer(account, entry, stop, tp, risk_pct=0.10, leverage=125, margin_pct=0.20):
    """Fixed fractional position sizing for ETH short.
    Borrowed from position-sizer skill: risk_pct of account at risk per trade.
    """
    risk_usd = round(account * risk_pct, 2)
    margin = round(account * margin_pct, 2)
    position_size = round(margin * leverage, 0)
    stop_distance = abs(entry - stop)
    tp_distance = abs(entry - tp)
    reward_usd = round(tp_distance * (position_size / entry), 2)
    rr = round(tp_distance / stop_distance, 1) if stop_distance > 0 else 0

    return PositionResult(
        account=account, entry=entry, stop=stop, take_profit=tp,
        risk_pct=risk_pct, leverage=leverage, margin=margin,
        position_size=position_size, risk_usd=risk_usd,
        reward_usd=reward_usd, rr=rr
    )


# ============================================================
# 2. edge-strategy-reviewer: 8 维度自审 (enhanced from skill)
# ============================================================

REVIEW_CRITERIA = {
    "C1": {"name": "边界可信度", "weight": 20, "desc": "支撑/阻力/费率有无技术依据"},
    "C2": {"name": "过拟合风险", "weight": 20, "desc": "多维度交叉印证"},
    "C3": {"name": "样本量",     "weight": 15, "desc": "信号模式历史出现次数"},
    "C4": {"name": "执行可行",   "weight": 15, "desc": "滑点/手续费/流动性"},
    "C5": {"name": "情绪一致",   "weight": 10, "desc": "恐惧贪婪+费率+多空比"},
    "C6": {"name": "宏观匹配",   "weight": 10, "desc": "重大数据/事件冲突"},
    "C7": {"name": "风险回报",   "weight": 5,  "desc": "R倍数 ≥ 1.5"},
    "C8": {"name": "时效性",     "weight": 5,  "desc": "信号是否过期"},
}

def review_verdict(score):
    """Borrowed from edge-strategy-reviewer verdict logic"""
    if score >= 70: return "PASS ✅"
    elif score >= 60: return "REVISE ⚠️"
    else: return "REJECT ❌"


# ============================================================
# 3. scenario-analyzer: 3 场景概率 (adapted for 15m TF)
# ============================================================

def build_scenarios(price, bias, entry, stop, tp, low, high):
    """Build 3 probabilistic scenarios. Adapted from scenario-analyzer skill."""
    if bias == "做空":
        return {
            "A_主力": f"反弹至 {entry} 后遇阻，跌到 {tp}（概率 45%）",
            "B_止损": f"突破 {stop}，做空失败止损（概率 30%）",
            "C_踏空": f"不反弹直接阴跌，错过入场（概率 25%）",
        }
    elif bias == "做多":
        return {
            "A_主力": f"回调至 {entry} 后支撑，涨到 {tp}（概率 45%）",
            "B_止损": f"跌破 {stop}，做多失败止损（概率 30%）",
            "C_踏空": f"不回调直接涨，错过入场（概率 25%）",
        }
    else:
        return {
            "A_震荡": f"{low} 到 {high} 间震荡无突破（概率 40%）",
            "B_上破": f"突破 {high} → 做多（概率 35%）",
            "C_下破": f"跌破 {low} → 做空（概率 25%）",
        }


# ============================================================
# 4. technical-analyst: K线形态 + 趋势判断 (adapted from weekly to 15m)
# ============================================================

def analyze_kline_patterns(klines):
    """K-line pattern analysis. Adapted from technical-analyst skill."""
    latest = klines[0]
    body = abs(latest['c'] - latest['o'])
    wick_upper = latest['h'] - max(latest['c'], latest['o'])
    wick_lower = min(latest['c'], latest['o']) - latest['l']
    range_pct = (latest['h'] - latest['l']) / latest['o'] * 100 if latest['o'] > 0 else 0

    # Pattern detection across 6 candles
    patterns = []
    for k in klines:
        bd = abs(k['c'] - k['o'])
        wl = min(k['c'], k['o']) - k['l']
        wu = k['h'] - max(k['c'], k['o'])
        if wl > bd * 1.5: patterns.append("下影长(承接)")
        if wu > bd * 1.5: patterns.append("上影长(抛压)")
        if bd < 0.5: patterns.append("缩体(变盘)")

    # Trend assessment
    mid_price = (latest['h'] + latest['l']) / 2
    if latest['c'] > mid_price: trend_bias = "偏多"
    elif latest['c'] < mid_price: trend_bias = "偏空"
    else: trend_bias = "中性"

    # Multi-candle signals
    last3_low_wicks = sum(1 for k in klines[:3] if min(k['c'],k['o'])-k['l'] > abs(k['c']-k['o'])*1.2)
    last3_bodies = [abs(k['c']-k['o']) for k in klines[:3]]
    body_shrinking = len(last3_bodies)>=3 and all(b < 2 for b in last3_bodies)

    signal = ""
    if last3_low_wicks >= 2 and body_shrinking:
        signal = "低位承接 + 变盘临近 → 可能反转向上"
    elif last3_low_wicks >= 2:
        signal = "连续下影 → 买方低位接盘"
    elif body_shrinking:
        signal = "实体持续缩小 → 变盘前兆"

    return {
        "body": body, "wick_upper": wick_upper, "wick_lower": wick_lower,
        "range_pct": range_pct, "trend_bias": trend_bias,
        "patterns": list(set(patterns)), "signal": signal
    }


# ============================================================
# 5. signal-postmortem: 交易复盘 (adapted for ETH)
# ============================================================

@dataclass
class TradeRecord:
    trade_id: str
    opened_at: str
    closed_at: str
    direction: str        # LONG / SHORT
    entry_price: float
    exit_price: float
    stop_price: float
    tp_price: float
    pnl_points: float
    pnl_usd: float
    pnl_pct: float        # % of account
    outcome: str           # TP / FP / MISSED / STOPPED
    notes: str = ""

def classify_outcome(direction, entry, exit_px, stop, tp):
    """Classify trade outcome. Borrowed from signal-postmortem."""
    if direction == "short":
        won = exit_px < entry
        stopped = exit_px >= stop
        hit_tp = exit_px <= tp
    else:
        won = exit_px > entry
        stopped = exit_px <= stop
        hit_tp = exit_px >= tp

    if stopped: return "STOPPED"
    if hit_tp: return "TP ✅"
    if won: return "TP ✅ (partial)"
    return "FP ❌"

def record_trade(account, direction, entry, exit_px, stop, tp, notes=""):
    """Record a closed trade to the journal."""
    pnl_points = (entry - exit_px) if direction == "short" else (exit_px - entry)
    pnl_usd = round(pnl_points * (account * 0.20 * 125 / entry), 2)
    pnl_pct = round(pnl_usd / account * 100, 1) if account > 0 else 0
    outcome = classify_outcome(direction, entry, exit_px, stop, tp)

    trade = TradeRecord(
        trade_id=datetime.now(TZ).strftime("%Y%m%d_%H%M%S"),
        opened_at=datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
        closed_at=datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
        direction=direction, entry_price=entry, exit_price=exit_px,
        stop_price=stop, tp_price=tp,
        pnl_points=pnl_points, pnl_usd=pnl_usd, pnl_pct=pnl_pct,
        outcome=outcome, notes=notes
    )

    # Save to journal
    trades = []
    if os.path.exists(TRADE_LOG):
        try:
            with open(TRADE_LOG, "r", encoding="utf-8") as f:
                trades = json.load(f)
        except: pass

    trades.append(trade.__dict__)
    os.makedirs(os.path.dirname(TRADE_LOG) if os.path.dirname(TRADE_LOG) else ".", exist_ok=True)
    with open(TRADE_LOG, "w", encoding="utf-8") as f:
        json.dump(trades, f, ensure_ascii=False, indent=2)

    return trade


def get_trade_stats():
    """Get cumulative trade statistics."""
    if not os.path.exists(TRADE_LOG):
        return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0,
                "total_pnl": 0, "avg_win": 0, "avg_loss": 0}

    with open(TRADE_LOG, "r", encoding="utf-8") as f:
        trades = json.load(f)

    wins = [t for t in trades if t["outcome"].startswith("TP")]
    losses = [t for t in trades if t["outcome"] in ("FP ❌", "STOPPED")]
    total_pnl = sum(t["pnl_usd"] for t in trades)

    return {
        "total": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins)/len(trades)*100, 1) if trades else 0,
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(sum(t["pnl_usd"] for t in wins)/len(wins), 2) if wins else 0,
        "avg_loss": round(sum(t["pnl_usd"] for t in losses)/len(losses), 2) if losses else 0,
    }


# ============================================================
# 集成测试
# ============================================================
if __name__ == "__main__":
    # Position sizer test
    ps = position_sizer(account=10.12, entry=1984, stop=2005, tp=1965)
    print("=== position-sizer ===")
    print(f"保证金: {ps.margin}U | 仓位: {ps.position_size}张 | R={ps.rr}R")
    print(f"风险: {ps.risk_usd}U | 潜在收益: {ps.reward_usd}U")

    # Review test
    print(f"\n=== edge-strategy-reviewer ===")
    for cid, c in REVIEW_CRITERIA.items():
        print(f"  {cid} {c['name']} (w{c['weight']}): {c['desc']}")

    # Scenario test
    print(f"\n=== scenario-analyzer ===")
    for k, v in build_scenarios(1993, "做空", 2001, 2016, 1976, 1965, 2080).items():
        print(f"  {k}: {v}")

    # Stats test
    print(f"\n=== signal-postmortem stats ===")
    print(json.dumps(get_trade_stats(), ensure_ascii=False, indent=2))
