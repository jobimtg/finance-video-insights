"""產出單集報告草稿：python scripts/build_report.py 20261012
讀 episodes/<日期>/episode.json（Claude 從逐字稿整理的觀點），抓最新公開數據，
輸出 drafts/<日期>/report.json、PDF、Flex 卡片 JSON 與自動檢查結果。
"""
import json, sys, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
import sources as S
from render_report import render

ROOT = Path(__file__).resolve().parent.parent
VAN, TPE = ZoneInfo("America/Vancouver"), ZoneInfo("Asia/Taipei")
WEEK = "一二三四五六日"
log = []


def md(d):
    return f"{d.month}/{d.day}" if d else "—"


def mmdd(d):
    return f"{d.month:02d}/{d.day:02d}" if d else "—"


def trading_days_after(start, n, holidays):
    d, k = start, 0
    while k < n:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            k += 1
    return d


def judge(stance, chg):
    if chg is None or chg == 0:
        return "待觀察"   # 持平：規則未定義上漲或下跌，暫列待觀察（待使用者確認）
    if stance == "偏多":
        return "方向一致" if chg > 0 else "方向相反"
    if stance in ("偏空", "不追高"):
        return "方向相反" if chg > 0 else "方向一致"
    if stance == "拉回布局":
        return "未拉回" if chg > 0 else "出現拉回"
    return "待觀察"


def level_checks(levels, latest):
    out = []
    for lv in levels:
        v, k = lv.get("value"), lv.get("kind", "info")
        if isinstance(v, (int, float)) and latest:
            if k == "resistance":
                out.append(f"{lv['label']} {v:g}：" + ("已站上" if latest >= v else f"未達（差 {(v / latest - 1) * 100:.1f}%）"))
                continue
            if k == "support":
                out.append(f"{lv['label']} {v:g}：" + ("目前在其下" if latest < v else f"目前高於 {(latest / v - 1) * 100:.1f}%"))
                continue
        out.append(f"{lv['label']} {v}")
    return out or ["價位驗證：查無"]   # 節目沒提到具體價位時標「查無」，不留白


def main(ep_date):
    E = json.loads((ROOT / "episodes" / ep_date / "episode.json").read_text(encoding="utf-8"))
    air = dt.date.fromisoformat(E["air_date"])
    hist_start = (air - dt.timedelta(days=400)).isoformat()

    # ---- 公開數據 ----
    tw_close, tw_val, tw_rev = S.twse_close(), S.twse_valuation(), S.twse_revenue()
    try:
        tp_close = S.tpex_close()
    except Exception as e:
        tp_close = {}; log.append(f"櫃買行情讀取失敗，改用 FinMind 收盤：{e}")
    tp_val, tp_rev, tp_inst = S.tpex_valuation(), S.tpex_revenue(), S.tpex_institutional()
    holidays = S.twse_holidays()

    taiex = S.fm_prices("TAIEX", (air - dt.timedelta(days=10)).isoformat())
    tx = {p["date"]: p for p in taiex}
    latest_day = max(tx)
    next_day = min((d for d in tx if d > air), default=None)

    stocks, val_dates, inst_dates, rev_months = [], set(), set(), set()
    for s in E["stocks"]:
        c, mk = s["code"], s["market"]
        etf = c.startswith("00")
        px = S.fm_prices(c, hist_start)
        by = {p["date"]: p for p in px}
        video_close = by[air]["close"] if air in by else None
        cl = (tw_close if mk == "TWSE" else tp_close).get(c, {})
        latest, ldate = cl.get("close"), cl.get("date")
        if latest is None and px:
            latest, ldate = px[-1]["close"], px[-1]["date"]; log.append(f"{c} 最新收盤改用 FinMind")
        yr = [p for p in px if p["date"] >= (ldate or latest_day) - dt.timedelta(days=365)]   # 含起日，與表格說明一致
        hi52 = max(p["high"] for p in yr) if yr else None
        lo52 = min(p["low"] for p in yr) if yr else None
        if latest and hi52 and latest > hi52:
            hi52 = latest
        val = (tw_val if mk == "TWSE" else tp_val).get(c, {})
        rev = (tw_rev if mk == "TWSE" else tp_rev).get(c, {})
        if mk == "TWSE":
            inst_net, idate = S.fm_institutional(c, (latest_day - dt.timedelta(days=10)).isoformat())
        else:
            ti = tp_inst.get(c, {}); inst_net, idate = ti.get("net"), ti.get("date")
        if not etf:
            if val.get("date"): val_dates.add(val["date"])
            if rev.get("month"): rev_months.add(rev["month"])
        if idate: inst_dates.add(idate)
        pct = round((latest / video_close - 1) * 100, 2) if latest and video_close else None

        def chg_at(n):
            d = trading_days_after(air, n, holidays)
            return d, (round((by[d]["close"] / video_close - 1) * 100, 2) if d in by and video_close else None)

        d2, c2 = chg_at(2)
        d5, c5 = chg_at(5)
        d20, c20 = chg_at(20)
        tgt = s.get("target") or {}
        stocks.append({
            "code": c, "name": s["name"], "group": s["group"], "market": mk,
            "guest": s.get("guest", ""), "ts": s.get("ts", ""),
            "stance": s["stance"], "view": s["view"], "level_desc": s.get("level_desc", ""),
            "level_checks": level_checks(s.get("levels", []), latest),
            "video_close": video_close, "latest": latest, "latest_date": ldate.isoformat() if ldate else None,
            "since_video_pct": pct,
            "pe": None if etf else val.get("pe"), "yield": None if etf else val.get("yield"),
            "rev_yoy": None if etf else rev.get("yoy"), "inst_total": inst_net,
            "hi52": hi52, "lo52": lo52, "off_hi52_pct": round((latest / hi52 - 1) * 100, 1) if latest and hi52 else None,
            "target": tgt.get("price"), "target_src": tgt.get("src"),
            "target_upside_pct": round((tgt["price"] / latest - 1) * 100, 1) if tgt.get("price") and latest else None,
            "verify": judge(s["stance"], c2 if c2 is not None else None) if (d2 <= latest_day) else "待觀察",
            "verify5_done": judge(s["stance"], c5) if d5 <= latest_day and c5 is not None else None,
            "verify20_done": judge(s["stance"], c20) if d20 <= latest_day and c20 is not None else None,
            "is_etf": etf,
            "_dates": {"d2": d2.isoformat(), "d5": d5.isoformat(), "d20": d20.isoformat()},
        })

    d5 = trading_days_after(air, 5, holidays); d20 = trading_days_after(air, 20, holidays)

    # ---- 主管機關名單 ----
    alerts = None
    try:
        rec, att_tw, dis_tw = S.twse_lists()
        att_tp, dis_tp = S.tpex_lists()
        today_tw = latest_day   # 名單以最新交易日的公告為準，與其他數據同日
        alerts = {"checked_date": md(today_tw), "lists": {
            "異常推介": sorted(set(rec)),
            "注意股": sorted(set(att_tw + att_tp)),
            "處置股": sorted({c for c, p in dis_tw + dis_tp if S.in_disposal(p, today_tw)})}}
    except Exception as e:
        log.append(f"主管機關名單抓取失敗，本集未比對：{e}")

    # ---- 總經 ----
    macro, notes = [], []
    tot = S.fm_total_institutional((latest_day - dt.timedelta(days=10)).isoformat())
    for m in E.get("macro", []):
        src = m.get("source", "text")
        row = {"name": m["name"], "alert": m.get("alert", ""), "latest": m.get("latest", "—"), "status": m.get("status", "—")}
        if src.startswith("FRED:"):
            v, d = S.fred_latest(src[5:])
            if v is None:
                row["latest"], row["status"] = "查無", "—"
            else:
                row["latest"] = f"{v:.2f}{m.get('unit', '')}（{md(d)}）"
                hit = (v >= m["threshold"]) if m.get("cmp", "above") == "above" else (v <= m["threshold"])
                row["status"] = m.get("hit_label", "已達") if hit else m.get("miss_label", "未達")
        elif src == "inst_total" and tot:
            last = max(tot); t = tot[last]
            fi = t.get("Foreign_Investor", 0) + t.get("Foreign_Dealer_Self", 0); it = t.get("Investment_Trust", 0)
            row["latest"] = f"{fi:+,.1f} 億／{it:+,.1f} 億（{md(dt.date.fromisoformat(last))}）"
            row["status"] = "外資賣超" if fi < 0 else "外資買超"
        elif src == "taiex":
            v = tx[latest_day]["close"]
            row["latest"] = f"{v:,.0f}（{md(latest_day)}）"
            hit = v >= m["threshold"]
            row["status"] = m.get("hit_label", "已站上") if hit else m.get("miss_label", "未達")
        macro.append(row)
    brent, bd = S.fred_latest("DCOILBRENTEU")
    fred_dates = []
    for m in E.get("macro", []):
        if m.get("source", "").startswith("FRED:"):
            v, d = S.fred_latest(m["source"][5:])
            if d: fred_dates.append(f"{m['name']}至 {md(d)}")
    note = (f"FRED 數據有發布時差（{'、'.join(fred_dates)}）；" if fred_dates else "") + E.get("macro_note", "")
    if brent is not None:
        note += f"FRED 布蘭特為 Dated 現貨（{md(bd)} 為 {brent:.2f}），與節目引用的期貨不同。"
    note = note or "美債與匯率來源 FRED，比台股晚 1–2 個交易日。"

    # ---- 三個重點 ----
    core = [x for x in stocks if x["stance"] != "背景" and x["since_video_pct"] is not None]
    if E.get("highlights"):
        highlights = E["highlights"]
    else:
        a0, a1 = tx[air]["close"] if air in tx else None, tx[latest_day]["close"]
        groups = {}
        for x in core:
            groups.setdefault(x["group"].split("/")[0], []).append(x["since_video_pct"])
        g = sorted(((k, sum(v) / len(v)) for k, v in groups.items() if len(v) >= 2), key=lambda t: -t[1])
        top = max(core, key=lambda x: x["since_video_pct"]); bot = min(core, key=lambda x: x["since_video_pct"])
        ev = "、".join(f"{e['event']}（{e['date']}）" for e in E.get("events", [])[:3])
        highlights = [
            f"大盤：影片當日收 {a0:,.0f}，{md(latest_day)} 收 {a1:,.0f}（{a1 - a0:+,.0f} 點）。" if a0 else f"大盤：{md(latest_day)} 收 {a1:,.0f}。",
            (f"族群：{g[0][0]}平均 {g[0][1]:+.1f}% 最強、{g[-1][0]}平均 {g[-1][1]:+.1f}% 最弱；" if g else "族群：")
            + f"個股漲幅最大 {top['name']} {top['since_video_pct']:+.1f}%、跌幅最大 {bot['name']} {bot['since_video_pct']:+.1f}%。",
            f"事件：{ev}。" if ev else "事件：本集未提及。"]

    taiex_cards = []
    for lab, d in ((f"{md(air)} 影片當日", air), (md(next_day), next_day), (md(latest_day), latest_day)):
        if d in tx:
            taiex_cards.append({"label": lab, "close": tx[d]["close"], "chg": tx[d]["spread"] or 0})
    vd = max(val_dates) if val_dates else None
    idt = max(inst_dates) if inst_dates else None
    rm = max(rev_months) if rev_months else None
    lat = max(dt.date.fromisoformat(x["latest_date"]) for x in stocks if x["latest_date"])
    air_dt = dt.datetime(air.year, air.month, air.day, 21, 0, tzinfo=TPE).astimezone(VAN)
    R = {
        "episode": {
            "show": E.get("show", "錢線百分百"),
            "video_date_short": md(air), "latest_date_short": md(lat),
            "revenue_month_label": f"{rm}月" if rm else "",
            "air_line": f"台灣 {air.isoformat()}（週{WEEK[air.weekday()]}）21:00–23:30 播出｜溫哥華同日 {air_dt:%H:%M}–{(air_dt + dt.timedelta(minutes=150)):%H:%M}｜來賓：{'、'.join(E.get('guests', []))}",
            "data_line": f"數據截至 {lat.isoformat()} 收盤（本益比與殖利率為 {md(vd)}，法人為 {md(idt)}，營收為 {rm} 月）",
        },
        "taiex": taiex_cards,
        "highlights": highlights,
        "macro": macro, "macro_note": note,
        "events": E.get("events", []),
        "verify_dates": {"d5": md(d5), "d20": md(d20)},
        "table_note": f"本益比與殖利率為 {md(vd)}；法人為 {md(idt)}；營收為 {rm} 月年增；52 週為 {(lat - dt.timedelta(days=365)):%Y/%m/%d} 起。",
        "segments": E["segments"],
        "sources_text": ("價格：臺灣證券交易所、證券櫃檯買賣中心 OpenAPI（政府資料開放授權條款－第1版）｜"
                         "估值與營收：證交所 BWIBBU、t187ap05_L，櫃買本益比與月營收｜"
                         "法人：上市個股與大盤為 FinMind，上櫃為櫃買三大法人｜近一年高低與影片當日收盤：FinMind｜"
                         "主管機關名單：證交所異常推介、注意、處置股，櫃買注意、處置股｜"
                         "總經：FRED（Federal Reserve Bank of St. Louis）DGS30、DGS10、DEXTAUS、DCOILBRENTEU。"
                         "This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis."),
        "stocks": stocks,
    }
    if alerts:
        R["alerts"] = alerts
    out = ROOT / "drafts" / ep_date
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    pdf = out / f"錢線百分百_{ep_date}_統整報告.pdf"
    render(str(out / "report.json"), str(pdf))
    (out / "build_log.json").write_text(json.dumps({"built_at_vancouver": dt.datetime.now(VAN).strftime("%Y-%m-%d %H:%M"),
                                                    "notes": log}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("built", pdf, "notes:", log)


if __name__ == "__main__":
    main(sys.argv[1])
