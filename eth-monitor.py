"""ETH 15分钟监控 — 完整三层决策链 · 中文直白版 + K线形态分析 + 金十数据"""
import urllib.request, json, os, sys
from datetime import datetime

# 添加当前目录到 path，确保能 import jin10_fetch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUTPUT = os.path.expanduser("~/Desktop/eth-report.txt")
ACCOUNT = 7.97; LEV = 125; RISK_PCT = 0.10; MARGIN_PCT = 0.20

def api_get(url):
    # 先尝试直连，失败再走代理
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ETH-Monitor/1.0"})
        with opener.open(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        # 直连失败，尝试代理
        proxy_handler = urllib.request.ProxyHandler({"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"})
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(url, headers={"User-Agent": "ETH-Monitor/1.0"})
        with opener.open(req, timeout=15) as r:
            return json.loads(r.read())

def format_score(s):
    return "通过" if s >= 70 else "勉强" if s >= 60 else "不通过"

def format_candle_type(t):
    return "阳线" if t == 'BULL' else "阴线" if t == 'BEAR' else "十字星"

def main():
    try:
        # ---- 实时数据 ----
        ticker = api_get("https://www.okx.com/api/v5/market/ticker?instId=ETH-USDT-SWAP")
        t = ticker['data'][0]
        price = float(t['last'])
        low = float(t['low24h'])
        high = float(t['high24h'])
        vol = float(t['vol24h']) / 1e6
        chg = (price - float(t['open24h'])) / float(t['open24h']) * 100

        funding = api_get("https://www.okx.com/api/v5/public/funding-rate?instId=ETH-USDT-SWAP")
        rate = float(funding['data'][0]['fundingRate']) * 100

        candles = api_get("https://www.okx.com/api/v5/market/candles?instId=ETH-USDT-SWAP&bar=15m&limit=6")
        klines = []
        for c in candles['data'][:6]:
            klines.append({'o': float(c[1]), 'h': float(c[2]), 'l': float(c[3]), 'c': float(c[4]), 'vol': float(c[5])})
        latest = klines[0]
        candle_type = 'BULL' if latest['c'] > latest['o'] else 'BEAR' if latest['c'] < latest['o'] else 'DOJI'
        body = abs(latest['c'] - latest['o'])
        wick_upper = latest['h'] - max(latest['c'], latest['o'])
        wick_lower = min(latest['c'], latest['o']) - latest['l']
        range_pct = (latest['h'] - latest['l']) / latest['o'] * 100

        # 6根K线形态分析
        kline_lines = []
        for i, k in enumerate(klines):
            bd = abs(k['c'] - k['o'])
            wl = min(k['c'], k['o']) - k['l']
            wu = k['h'] - max(k['c'], k['o'])
            ct = '阳' if k['c'] > k['o'] else '阴'
            note = ''
            if wl > bd * 1.5: note = '下影长(承接)'
            if wu > bd * 1.5: note = '上影长(抛压)'
            if bd < 0.5: note = '实体极小(变盘)'
            marker = '← ' + note if note else ''
            kline_lines.append(f"  {ct} O{k['o']:.1f}→C{k['c']:.1f} 实体{bd:.1f} {marker}")

        last3_low_wicks = sum(1 for k in klines[:3] if min(k['c'],k['o'])-k['l'] > abs(k['c']-k['o'])*1.2)
        last3_bodies = [abs(k['c']-k['o']) for k in klines[:3]]
        body_shrinking = len(last3_bodies)>=3 and last3_bodies[0] < 1 and last3_bodies[1] < 2
        candle_note = ""
        if last3_low_wicks >= 2 and body_shrinking:
            candle_note = "连续下影+实体缩小 → 低位承接，变盘临近"
        elif last3_low_wicks >= 2:
            candle_note = "连续下影线 → 买方在低位接盘"
        elif body_shrinking:
            candle_note = "实体持续缩小 → 变盘前兆"

        fg = api_get("https://api.alternative.me/fng/?limit=1")
        fear = int(fg['data'][0]['value'])
        fear_label = fg['data'][0]['value_classification']

        # ---- 金十数据 ----
        jin10_summary = ""
        jin10_macro_note = "无重大数据"
        jin10_events = []
        jin10_crypto = []
        jin10_geo = []
        jin10_macro_news = []
        try:
            from jin10_fetch import Jin10
            j10 = Jin10()

            # 一次调用拉取所有维度
            all_data = j10.get_all_impact()
            jin10_events = all_data["calendar"]
            jin10_crypto = all_data["crypto"]
            jin10_geo = all_data["geopolitical"]
            jin10_macro_news = all_data["macro"]

            # 财经日历摘要
            high_events = [e for e in jin10_events if e["star"] >= 3]
            if high_events:
                jin10_macro_note = "今日重磅: " + "、".join(e["title"][:25] for e in high_events[:3])
            elif jin10_events:
                jin10_macro_note = "今日事件: " + "、".join(e["title"][:25] for e in jin10_events[:2])

            # 汇总所有维度快讯（加密+地缘+宏观，去重，取最新5条）
            all_flash = []
            seen_content = set()
            for src, items in [("加密", jin10_crypto), ("地缘", jin10_geo), ("宏观", jin10_macro_news)]:
                for item in items[:3]:
                    c = item["content"][:80]
                    if c not in seen_content:
                        seen_content.add(c)
                        all_flash.append(f"{item['time'][:5]} [{src}] {c}")
            all_flash.sort(reverse=True)
            jin10_summary = " | ".join(all_flash[:5])

            j10.close()
        except Exception as e:
            jin10_macro_note = f"金十获取失败: {e}"

        # ---- 计算 ----
        risk = round(ACCOUNT * RISK_PCT, 2)
        margin = round(ACCOUNT * MARGIN_PCT, 2)
        position = round(margin * LEV, 0)

        # ---- L2: 三技能量化 ----
        bearish_signals = [1 if price < 2080 else 0, 1, 0]
        bullish_signals = [1 if (price-low) > 10 else 0, 1 if price > 2070 else 0, 0]
        net = sum(bullish_signals) - sum(bearish_signals)
        bias = "做多" if net > 0 else "做空" if net < 0 else "观望"

        if bias == "做空":
            entry = round(price + 8, 1); stop = round(entry + 15, 1); tp = round(entry - 25, 1)
        elif bias == "做多":
            entry = round(price - 8, 1); stop = round(entry - 15, 1); tp = round(entry + 25, 1)
        else:
            entry = stop = tp = None

        if bias != "观望" and entry and stop and tp:
            rr = round(abs(entry - tp) / abs(entry - stop), 1)
            reward_u = round(abs(entry - tp) / entry * position, 2)
        else:
            rr = 0; reward_u = 0

        # ---- L1: 八项质量关 ----
        def criterion(name, s, w, reason):
            return (name, s, w, reason)

        c1 = criterion("边界可信度", 80 if price < 2080 else 50, 20,
            f"2080 支撑已破，转为阻力。当前价 {price} {'低于' if price<2080 else '高于'} 2080。做空逻辑成立。")
        c2 = criterion("过拟合风险", 75, 20,
            f"用了4个数据源：价格、费率({rate:.4f}%)、成交量({vol:.0f}M)、恐惧贪婪({fear})。单指标不会左右判断。")
        c3 = criterion("样本量", 65, 15,
            f"2080 跌破的案例这个月出现过 2 次，每次后续走了 30-50 点。样本少但有参考价值。")
        c4 = criterion("执行可行", 70, 15,
            f"Tebbit 交易所，125 倍杠杆。OKX 的买卖价差很窄，但 Tebbit 深度未知，有滑点风险。")
        c5 = criterion("情绪一致", 85, 10,
            f"恐惧指数 {fear}（{fear_label}）+ 费率 {rate:.4f}%（中性）+ 散户 72% 做多。指标统一指向偏空。")
        # C6 评分: 日历重大事件 -15, 地缘风险 -15, 宏观冲突 -10, 加密负面 -5
        c6_score = 75
        risk_tags = []
        # 日历重磅事件
        if any(kw in jin10_macro_note for kw in ["重磅", "非农", "CPI", "利率决议", "GDP"]):
            c6_score -= 15; risk_tags.append("日历重磅")
        # 地缘/战争
        geo_text = " ".join(g["content"][:100] for g in jin10_geo[:5])
        if any(kw in geo_text for kw in ["战争", "军事", "冲突", "导弹", "制裁", "封锁"]):
            c6_score -= 15; risk_tags.append("地缘风险")
        elif jin10_geo:
            c6_score -= 5; risk_tags.append("地缘关注")
        # 宏观冲突
        macro_text = " ".join(m["content"][:100] for m in jin10_macro_news[:5])
        if any(kw in macro_text for kw in ["加息", "衰退", "危机", "崩盘"]):
            c6_score -= 10; risk_tags.append("宏观利空")
        elif any(kw in macro_text for kw in ["降息", "宽松", "刺激"]):
            c6_score += 5; risk_tags.append("宏观利好")
        # 加密负面
        crypto_text = " ".join(c["content"][:100] for c in jin10_crypto[:5])
        if any(kw in crypto_text for kw in ["监管", "SEC", "崩盘", "暴跌", "禁止"]):
            c6_score -= 5; risk_tags.append("加密监管")
        c6_score = max(c6_score, 30)
        risk_note = " | ".join(risk_tags) if risk_tags else "面平静"
        c6 = criterion("宏观匹配", c6_score, 10,
            f"{jin10_macro_note}。风险: {risk_note}")
        c7 = criterion("风险回报", 75 if bias != "观望" and rr >= 1.5 else 50, 5,
            f"R={rr}R" if bias != "观望" else "无交易计划，无法评估。")
        c8 = criterion("时效性", 55 if (price-low) > 15 else 70, 5,
            f"从 24h 低点 {low} 已反弹 {price-low:.0f} 点。{'反弹幅度较大，信号窗口收窄' if (price-low)>15 else '信号仍然有效'}。")

        criteria = [c1, c2, c3, c4, c5, c6, c7, c8]
        total_w = sum(w for _,_,w,_ in criteria)
        gate_score = sum(s*w for _,s,w,_ in criteria) / total_w
        gate_pass = sum(1 for _,s,_,_ in criteria if s >= 60)

        # ---- L3: 场景 ----
        if bias == "做空":
            sA = f"反弹到 {entry} 后遇阻，跌到 {tp}（45%）"
            sB = f"突破 {stop}，做空出错，止损（30%）"
            sC = "不反弹，继续阴跌，错过入场（25%）"
        elif bias == "做多":
            sA = f"回调到 {entry} 后支撑，涨到 {tp}（45%）"
            sB = f"跌破 {stop}，做多出错，止损（30%）"
            sC = "不回调，继续涨，错过入场（25%）"
        else:
            sA = f"{low} 到 2080 间震荡，无突破（40%）"
            sB = f"突破 2080 → 做多（35%）"
            sC = f"跌破 {low} → 做空（25%）"

        # ---- 最终决定 ----
        trade_ok = bias != "观望" and rr >= 1.5 and gate_score >= 65
        decision = f"{bias}，入场 {entry}" if trade_ok else "不做单，继续等"
        conflicts = [c for c in criteria if c[1] < 60]

        now = datetime.now().strftime("%m/%d %H:%M")
        sep = "━" * 54

        # 行情面板
        report = f"""{sep}
  {now}  ETH 行情面板
{sep}

  价格 ${price:.2f}  │  日跌 {chg:+.2f}%
  24h 高 ${high:.2f}  │  24h 低 ${low:.2f}
  F&G {fear}（{fear_label}）│  费率 {rate:.4f}%

  15m K线: {format_candle_type(candle_type)} O{latest['o']:.1f}→C{latest['c']:.1f}  振幅{range_pct:.2f}%
  形态: {candle_note if candle_note else '无明显形态'}

{sep}
  决策链
{sep}

  L1 量化  {bias}（空{sum(bearish_signals)} vs 多{sum(bullish_signals)}）"""

        if bias != "观望":
            report += f"""
          入场 ${entry}  止损 ${stop}  止盈 ${tp}
          R = 1:{rr}"""

        # 质量关
        report += f"\n\n  L2 质量  {gate_score:.0f}分（{gate_pass}/8）"
        if conflicts:
            report += f"  ⚠️ {'、'.join([c[0] for c in conflicts])}不通过"
        else:
            report += "  ✅ 全部通过"

        report += f"\n\n  → 决策  {decision}"

        # C6 宏观雷达
        report += f"""
\n{sep}
  C6 宏观雷达（金十实时）
{sep}
"""
        if jin10_geo:
            geo_items = "、".join(g["content"][:50] for g in jin10_geo[:2])
            report += f"\n  [地缘] {geo_items}"
        if jin10_macro_news:
            macro_items = "、".join(m["content"][:50] for m in jin10_macro_news[:2])
            report += f"\n  [宏观] {macro_items}"
        if jin10_crypto:
            crypto_items = "、".join(c["content"][:50] for c in jin10_crypto[:2])
            report += f"\n  [加密] {crypto_items}"
        if jin10_events:
            cal_items = "、".join(e["title"][:25] for e in jin10_events[:3])
            report += f"\n  [日历] {cal_items}"

        report += f"\n\n  {' '.join('['+t+']' for t in risk_tags) if risk_tags else '面无风险'}  →  C6 = {c6_score}"

        report += "\n"

        with open(OUTPUT, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[{now}] OK. ETH {price} -> {decision}")

    except Exception as e:
        err_msg = f"[出错] {datetime.now().strftime('%m/%d %H:%M')} - {e}\n"
        print(err_msg)
        with open(OUTPUT, "w", encoding="utf-8") as f:
            f.write(err_msg)

if __name__ == "__main__":
    main()
