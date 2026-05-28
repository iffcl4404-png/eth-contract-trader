"""
Alpha Skills → 旧系统桥接层（eth-contract-trader）
趋势/宏观/信号/风控 全接入
"""
import json, os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))

# ============================================================
# 1. macro-regime-detector — 宏观体制检测
# ============================================================

MACRO_REGIMES = {
    "INFLATION_BOOM":    {"bias": "风险偏好", "eth": "偏多", "note": "通胀上升+增长强→商品/加密受益"},
    "STAGFLATION":       {"bias": "避险",     "eth": "偏空", "note": "通胀高+增长弱→现金为王"},
    "GOLDILOCKS":        {"bias": "风险偏好", "eth": "偏多", "note": "通胀低+增长稳→最佳环境"},
    "DEFLATION_BUST":    {"bias": "避险",     "eth": "偏空", "note": "通缩+衰退→避险资产"},
    "REFLEXIVITY_BOOM":  {"bias": "风险偏好", "eth": "偏多", "note": "流动性泛滥→资产泡沫"},
    "LIQUIDITY_CRISIS":  {"bias": "避险",     "eth": "强烈偏空", "note": "流动性枯竭→全线崩盘"},
    "NEUTRAL":           {"bias": "中性",     "eth": "中性", "note": "无明显体制特征"},
}

def detect_macro_regime(pce_data=None, fed_stance=None, oil_trend=None, dollar_trend=None):
    """
    Detect structural macro regime from available signals.
    Adapted from macro-regime-detector: cross-asset ratio analysis.
    """
    score = {"INFLATION_BOOM": 0, "STAGFLATION": 0, "GOLDILOCKS": 0,
             "DEFLATION_BUST": 0, "REFLEXIVITY_BOOM": 0, "LIQUIDITY_CRISIS": 0}

    # PCE inflation signal (from Jin10)
    if pce_data and "3.3" in str(pce_data):
        score["STAGFLATION"] += 3
        score["INFLATION_BOOM"] += 1
    elif pce_data and "2.0" in str(pce_data):
        score["GOLDILOCKS"] += 3

    # Fed stance
    if fed_stance == "hawkish":
        score["STAGFLATION"] += 2
        score["LIQUIDITY_CRISIS"] += 1
    elif fed_stance == "dovish":
        score["REFLEXIVITY_BOOM"] += 2
        score["GOLDILOCKS"] += 1
    else:
        score["NEUTRAL"] = 1  # default

    # Oil trend
    if oil_trend == "rising":
        score["STAGFLATION"] += 2
    elif oil_trend == "falling":
        score["GOLDILOCKS"] += 2

    # Dollar trend
    if dollar_trend == "rising":
        score["LIQUIDITY_CRISIS"] += 2
    elif dollar_trend == "falling":
        score["REFLEXIVITY_BOOM"] += 2

    # Determine dominant regime
    if max(score.values()) == 0:
        dominant = "NEUTRAL"
    else:
        dominant = max(score, key=score.get)

    regime = MACRO_REGIMES.get(dominant, MACRO_REGIMES["NEUTRAL"])
    return {
        "regime": dominant,
        "bias": regime["bias"],
        "eth_outlook": regime["eth"],
        "note": regime["note"],
        "scores": {k: v for k, v in score.items() if v > 0}
    }


# ============================================================
# 2. market-breadth-analyzer — 市场广度
# ============================================================

def assess_breadth(price_vs_ma20, price_vs_ma50, funding_rate, fg_index):
    """
    Simplified breadth assessment for ETH context.
    Adapted from market-breadth-analyzer: 0-100 composite score.
    """
    score = 50  # neutral

    # Price vs moving averages (proxy for participation)
    if price_vs_ma20 == "above" and price_vs_ma50 == "above":
        score += 20
    elif price_vs_ma20 == "below" and price_vs_ma50 == "below":
        score -= 20
    else:
        score -= 5

    # Funding rate (proxy for market participation)
    if funding_rate > 0.01:
        score += 10  # strong participation
    elif funding_rate < 0:
        score -= 15  # weak participation

    # Fear & Greed
    if fg_index < 25:
        score += 10  # extreme fear = contrarian bullish
    elif fg_index > 75:
        score -= 10  # extreme greed = contrarian bearish

    score = max(0, min(100, score))

    if score >= 70:
        health = "HEALTHY"
    elif score >= 50:
        health = "MODERATE"
    elif score >= 30:
        health = "WEAK"
    else:
        health = "CRITICAL"

    return {"score": score, "health": health}


# ============================================================
# 3. market-top-detector — 顶部检测
# ============================================================

def detect_top_risk(price, high_7d, low_7d, dist_days, funding_rate):
    """
    Adapted O'Neil/Minervini top probability for ETH.
    Returns 0-100 top risk score.
    """
    risk = 0

    # Price vs 7d range
    range_7d = high_7d - low_7d
    if range_7d > 0:
        position_in_range = (price - low_7d) / range_7d
        if position_in_range > 0.8:
            risk += 25  # near top of range
        elif position_in_range < 0.2:
            risk -= 15  # near bottom

    # Distribution-like behavior (simplified)
    if dist_days >= 3:
        risk += 30
    elif dist_days >= 1:
        risk += 15

    # Funding rate extreme
    if funding_rate > 0.05:
        risk += 20  # overly bullish = top signal
    elif funding_rate < -0.02:
        risk -= 20

    risk = max(0, min(100, risk))

    if risk >= 70:
        level = "HIGH_TOP_RISK"
    elif risk >= 50:
        level = "ELEVATED"
    elif risk >= 30:
        level = "MODERATE"
    else:
        level = "LOW"

    return {"top_risk": risk, "level": level}


# ============================================================
# 4. institutional-flow-tracker — 机构资金流
# ============================================================

def estimate_institutional_flow(oi_change_24h, funding_rate, vol_24h, price_change):
    """
    Proxy for institutional flow using on-chain/perps data.
    Adapted from institutional-flow-tracker (13F → ETH perps signals).
    """
    signals = []

    # OI change
    if oi_change_24h > 0.05:
        signals.append("机构加仓")
    elif oi_change_24h < -0.05:
        signals.append("机构减仓")
    else:
        signals.append("持仓平稳")

    # Volume + price divergence
    if vol_24h > 1e6 and price_change > 0:
        signals.append("放量上涨→买盘强劲")
    elif vol_24h > 1e6 and price_change < 0:
        signals.append("放量下跌→抛压沉重")

    # Funding rate clue
    if funding_rate > 0.03:
        signals.append("多头拥挤→潜在逼空")
    elif funding_rate < -0.01:
        signals.append("空头拥挤→潜在逼多")

    direction = "bullish" if sum(1 for s in signals if "买" in s or "逼空" in s or "加仓" in s) > \
                            sum(1 for s in signals if "抛" in s or "逼多" in s or "减仓" in s) else "bearish"

    return {"signals": signals, "direction": direction}


# ============================================================
# 5. theme-detector — 市场主题
# ============================================================

def detect_themes(crypto_items, macro_items, geo_items):
    """
    Detect dominant market themes from recent news.
    """
    themes = {}

    all_text = " ".join(item["content"][:150] for items in [crypto_items, macro_items, geo_items]
                        for item in items[:5] if items)

    theme_keywords = {
        "加息预期": ["加息", "利率", "更高利率", "紧缩"],
        "降息预期": ["降息", "宽松", "刺激", "降息"],
        "地缘冲突": ["战争", "冲突", "制裁", "导弹", "军事"],
        "和谈进展": ["和谈", "停火", "协议", "外交"],
        "监管收紧": ["SEC", "监管", "调查", "禁止"],
        "机构入场": ["ETF", "机构", "基金", "买入"],
        "避险情绪": ["避险", "崩盘", "暴跌", "恐慌"],
        "风险偏好": ["新高", "突破", "暴涨", "牛市"],
    }

    for theme, keywords in theme_keywords.items():
        count = sum(1 for kw in keywords if kw in all_text)
        if count > 0:
            themes[theme] = count

    dominant = sorted(themes.items(), key=lambda x: x[1], reverse=True)
    return {"dominant_themes": dominant[:4], "theme_count": len(themes)}


# ============================================================
# 6. portfolio-manager — 持仓分析
# ============================================================

def portfolio_health(account, total_pnl, win_rate, total_trades, max_drawdown=0):
    """Simplified portfolio health check for ETH trader."""
    health_score = 50

    if total_pnl > 0:
        health_score += min(20, int(total_pnl / account * 100))
    else:
        health_score -= min(30, int(abs(total_pnl) / account * 100))

    if win_rate >= 60:
        health_score += 15
    elif win_rate >= 40:
        health_score += 5
    else:
        health_score -= 10

    if total_trades >= 10:
        health_score += 10  # experienced
    elif total_trades < 3:
        health_score -= 10  # inexperienced

    if max_drawdown > account * 0.3:
        health_score -= 20  # severe drawdown

    health_score = max(0, min(100, health_score))

    if health_score >= 70:
        grade = "A"
    elif health_score >= 55:
        grade = "B"
    elif health_score >= 40:
        grade = "C"
    else:
        grade = "D"

    return {
        "health_score": health_score,
        "grade": grade,
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "max_drawdown": max_drawdown
    }


# ============================================================
# 7. market-environment-analysis — 综合市场环境
# ============================================================

def market_environment(eth_price, eth_chg_24h, fg_index, macro_regime, top_risk, breadth):
    """
    Synthesize all signals into a unified market environment assessment.
    """
    signals = []

    # Price trend
    if eth_chg_24h < -5:
        signals.append(("恐慌抛售", -15))
    elif eth_chg_24h < -1:
        signals.append(("偏弱下行", -5))
    elif eth_chg_24h > 5:
        signals.append(("强势上涨", 15))
    elif eth_chg_24h > 1:
        signals.append(("温和上行", 5))
    else:
        signals.append(("横盘震荡", 0))

    # Fear & Greed
    if fg_index < 25:
        signals.append(("极度恐惧", 10))  # contrarian
    elif fg_index > 75:
        signals.append(("极度贪婪", -10))

    # Macro regime
    if macro_regime:
        if macro_regime["eth_outlook"] == "偏多":
            signals.append((f"宏观:{macro_regime['regime']}", 10))
        elif macro_regime["eth_outlook"] in ("偏空", "强烈偏空"):
            signals.append((f"宏观:{macro_regime['regime']}", -10))
        else:
            signals.append((f"宏观:{macro_regime['regime']}", 0))

    # Top risk
    if top_risk and top_risk["level"] == "HIGH_TOP_RISK":
        signals.append(("顶部风险高", -15))

    # Breadth
    if breadth:
        if breadth["health"] in ("HEALTHY",):
            signals.append((f"广度:{breadth['health']}", 10))
        elif breadth["health"] in ("CRITICAL",):
            signals.append((f"广度:{breadth['health']}", -15))

    total_score = sum(s[1] for s in signals)
    if total_score >= 15:
        env = "BULLISH_ENVIRONMENT"
    elif total_score >= 0:
        env = "NEUTRAL_ENVIRONMENT"
    elif total_score >= -15:
        env = "BEARISH_ENVIRONMENT"
    else:
        env = "CRISIS_ENVIRONMENT"

    return {
        "environment": env,
        "total_score": total_score,
        "signals": [s[0] for s in signals],
        "recommendation": {
            "BULLISH_ENVIRONMENT": "做多为主，空单谨慎",
            "NEUTRAL_ENVIRONMENT": "多空均可，以信号为准",
            "BEARISH_ENVIRONMENT": "做空为主，多单谨慎",
            "CRISIS_ENVIRONMENT": "减仓观望，控制风险"
        }.get(env, "观望")
    }


# ============================================================
# 8. edge-signal-aggregator (long-form)
# ============================================================

def aggregate_long_signals(c1_c8_score, c6_score, macro_regime, breadth, top_risk, env):
    """
    Long-form signal aggregation for the old system.
    Weights: C1-C8 (40%), C6 (30%), Macro (15%), Breadth (10%), Top Risk (5%)
    """
    signals = {}

    # C1-C8 quality (weight: 40%)
    c1_c8_norm = c1_c8_score  # already 0-100
    signals["C1-C8"] = {"score": c1_c8_norm, "weight": 40}

    # C6 macro (weight: 25%)
    signals["C6"] = {"score": c6_score, "weight": 25}

    # Macro regime (weight: 15%)
    regime_scores = {"GOLDILOCKS": 85, "INFLATION_BOOM": 60, "REFLEXIVITY_BOOM": 70,
                     "STAGFLATION": 35, "LIQUIDITY_CRISIS": 15, "DEFLATION_BUST": 20, "NEUTRAL": 50}
    macro_score = regime_scores.get(macro_regime.get("regime", "NEUTRAL") if macro_regime else "NEUTRAL", 50)
    signals["宏观体制"] = {"score": macro_score, "weight": 15}

    # Breadth (weight: 10%)
    breadth_score = breadth["score"] if breadth else 50
    signals["市场广度"] = {"score": breadth_score, "weight": 10}

    # Top risk (weight: 10%)
    if top_risk:
        top_score = 100 - top_risk["top_risk"]  # invert
    else:
        top_score = 50
    signals["顶部风险"] = {"score": top_score, "weight": 10}

    # Weighted conviction
    total_w = sum(v["weight"] for v in signals.values())
    conviction = sum(v["score"] * v["weight"] / total_w for v in signals.values())

    return {
        "conviction": round(conviction, 1),
        "sources": signals,
        "env": env.get("environment", "UNKNOWN") if env else "UNKNOWN"
    }
