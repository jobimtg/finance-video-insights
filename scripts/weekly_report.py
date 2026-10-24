"""週報摘要（2026-10-21 經使用者同意：每日完整 PDF 照常放網站、不推 LINE；週五 21:00 另出 5–9 頁週報摘要，LINE 每週只推一則）
用法：python weekly_report.py 20261023 [輸出資料夾]
讀取本週一～週五各集的 drafts/<日期>/report.json（每日報告的計算結果），彙整成週報 PDF，不另外抓數據。
內容：本週重點、各集一覽與完整版連結、多集重複點名個股、播出後漲跌排行、驗證統計、族群表現、下週事件、資料來源與聲明。
週五那集在週五還沒有播出後交易日，播出後漲跌與驗證標「下週更新」。
樣式沿用定版產生器（render_report.py）的字型、色碼與表格；週報版面本身為 2026-10-21 新增，需經使用者核准樣本。
"""
import datetime as dt, json, re, sys, urllib.parse
from collections import Counter, defaultdict
from pathlib import Path
from playwright.sync_api import sync_playwright
from render_report import CSS, VERIFY_ORDER, e, pct, colr, n, movers_svg

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://jobimtg.github.io/finance-video-insights"
WD = "一二三四五六日"


def md(d): return f"{d.month}/{d.day}"


def load_week(fri):
    mon = fri - dt.timedelta(days=4)
    eps = []
    for i in range(5):
        d = mon + dt.timedelta(days=i); k = d.strftime("%Y%m%d")
        epf = ROOT / "episodes" / k / "episode.json"
        if not epf.exists():
            eps.append({"date": d, "key": k, "missing": True}); continue
        E = json.loads(epf.read_text(encoding="utf-8"))
        rp = ROOT / "drafts" / k / "report.json"
        R = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else None
        pdf = f"錢線百分百_{k}_統整報告.pdf"
        published = (ROOT / "docs" / "reports" / pdf).exists()
        eps.append({"date": d, "key": k, "E": E, "R": R, "published": published,
                    "url": f"{BASE}/reports/{urllib.parse.quote(pdf)}" if published else None})
    return mon, eps


def same_day(R):
    ep = R["episode"]
    return ep["video_date_short"] == ep["latest_date_short"]


def build(fri, out_dir):
    mon, eps = load_week(fri)
    have = [x for x in eps if not x.get("missing")]
    built = [x for x in have if x["R"]]
    # 每一集的核心個股（含播出後資料是否已有）
    rows = []
    for x in built:
        pending = same_day(x["R"])
        for s in x["R"]["stocks"]:
            if s["stance"] == "背景":
                continue
            rows.append({**s, "ep": md(x["date"]), "pending": pending or s["since_video_pct"] is None})
    # 沒有 report.json 的集數（例如週五當天尚未產出）只用 episode.json
    for x in have:
        if not x["R"]:
            for s in x["E"]["stocks"]:
                if s["stance"] != "背景":
                    rows.append({**s, "ep": md(x["date"]), "pending": True, "since_video_pct": None, "latest": None, "verify": "待觀察"})
    latest_R = built[-1]["R"] if built else None
    # 加權指數：收集各集 taiex 卡片
    tx = {}
    for x in built:
        for k in x["R"]["taiex"]:
            lab = k["label"].split(" ")[0]
            tx[lab] = (k["close"], k["chg"])
    tx_rows = sorted(((k, v) for k, v in tx.items() if (int(k.split("/")[0]), int(k.split("/")[1])) <= (fri.month, fri.day)),
                     key=lambda kv: tuple(int(v) for v in kv[0].split("/")))
    # 多集重複點名
    by_code = defaultdict(list)
    for r in rows:
        by_code[r["code"]].append(r)
    multi = sorted([v for v in by_code.values() if len({r["ep"] for r in v}) >= 2], key=lambda v: (-len(v), v[0]["code"]))
    # 播出後漲跌（不含待更新）
    mv = sorted([r for r in rows if not r["pending"]], key=lambda r: -r["since_video_pct"])
    for r in mv:
        r["_label_name"] = f'{r["name"]}（{r["ep"]}）'
    disp = [{"name": r["_label_name"], "code": r["code"], "since_video_pct": r["since_video_pct"]} for r in mv]
    # 驗證統計
    vt = {x["key"]: Counter(s["verify"] for s in (x["R"]["stocks"] if x["R"] else []) if s["stance"] != "背景") for x in have}
    # 族群表現（本週所有已有數據的核心觀點）
    g = defaultdict(list)
    for r in mv:
        g[r["group"].split("/")[0]].append(r["since_video_pct"])
    grow = sorted(((k, sum(v) / len(v), len(v)) for k, v in g.items() if len(v) >= 3), key=lambda t: -t[1])
    if len(grow) > 12:
        grow = grow[:6] + grow[-6:]   # 只列最強與最弱各 6 個族群
    # 下週事件：合併各集事件，去掉日期已過者
    seen, events = set(), []
    for x in have:
        for ev in x["E"].get("events", []):
            m = re.match(r"(\d{1,2})/(\d{1,2})", ev["date"])
            if m:
                d = dt.date(fri.year, int(m.group(1)), int(m.group(2)))
                if d <= fri or d > fri + dt.timedelta(days=21):
                    continue
            elif x["date"] < fri - dt.timedelta(days=1):   # 沒有明確日期的事件只取週四、週五兩集
                continue
            key = ev["event"]
            if key in seen:
                continue
            seen.add(key); events.append({**ev, "src": md(x["date"])})
    # 本週重點（自動彙整）
    hl = []
    if tx_rows:
        first, last = tx_rows[0], tx_rows[-1]
        hl.append(f"加權指數：{first[0]} 收 {first[1][0]:,.0f}，{last[0]} 收 {last[1][0]:,.0f}（{last[1][0]-first[1][0]:+,.0f} 點）。")
    hl.append(f"本週 {len(have)} 集、有操作觀點 {len(rows)} 檔次（{len(by_code)} 檔），其中 {len(multi)} 檔被兩集以上點名。")
    if mv:
        hl.append(f"播出後漲幅最大 {mv[0]['name']}（{mv[0]['ep']}）{mv[0]['since_video_pct']:+.1f}%，跌幅最大 {mv[-1]['name']}（{mv[-1]['ep']}）{mv[-1]['since_video_pct']:+.1f}%。")
    pend = [x for x in have if not x["R"] or same_day(x["R"])]
    if pend:
        hl.append("、".join(md(x["date"]) for x in pend) + " 那集尚無播出後交易日，播出後漲跌與驗證於下週更新。")
    miss = [md(x["date"]) for x in eps if x.get("missing")]
    if miss:
        hl.append("本週缺集：" + "、".join(miss) + "（當天沒有完整版影片，例如停播或休市）。")
    data_line = (f"數據截至 {latest_R['episode']['latest_date_short']} 收盤（沿用各集每日報告的計算結果）" if latest_R else "本週尚無已產出的每日報告")
    # ---- HTML ----
    ep_rows = ""
    for x in eps:
        if x.get("missing"):
            ep_rows += f'<tr><td>{md(x["date"])}（{WD[x["date"].weekday()]}）</td><td colspan="4" class="mu">無資料</td></tr>'; continue
        E, R = x["E"], x["R"]
        core_n = len([s for s in E["stocks"] if s["stance"] != "背景"])
        hl1 = e(R["highlights"][1]) if R and len(R["highlights"]) > 1 else '<span class="mu">尚未產出</span>'
        link = f'<a href="{x["url"]}">完整版 PDF</a>' if x["url"] else '<span class="mu">尚未發布</span>'
        ep_rows += f'<tr><td>{md(x["date"])}（{WD[x["date"].weekday()]}）</td><td>{e("、".join(E.get("guests", [])))}</td><td class="r">{core_n}</td><td>{hl1}</td><td>{link}</td></tr>'
    multi_rows = ""
    for v in multi:
        s0 = v[-1]
        views = "<br>".join(f'<b>{e(r["ep"])}</b> {e(r["stance"])}｜{e(r.get("level_desc") or "")}' for r in v)
        chg = "<br>".join(f'{e(r["ep"])}：' + ('下週更新' if r["pending"] else f'<span style="color:{colr(r["since_video_pct"])}">{pct(r["since_video_pct"])}</span>') for r in v)
        last = next((r["latest"] for r in reversed(v) if r.get("latest") is not None), None)
        multi_rows += f'<tr><td><b>{e(s0["name"])}</b><br><span class="cd">{e(s0["code"])}</span><br><span class="mu">{e(s0["group"])}</span></td><td class="tx">{views}</td><td class="r">{n(last)}</td><td class="r tx">{chg}</td></tr>'
    vrows = ""
    for x in have:
        c = vt[x["key"]]
        state = "下週更新" if (not x["R"] or same_day(x["R"])) else ""
        vrows += f'<tr><td>{md(x["date"])}</td>' + "".join(f'<td class="r">{c.get(k, 0) if not state else "—"}</td>' for k in VERIFY_ORDER) + f'<td class="mu">{state}</td></tr>'
    ev_rows = "".join(f'<tr><td>{e(x["date"])}</td><td>{e(x["event"])}</td><td>{e(x["note"])}</td><td class="mu">{e(x["src"])}</td></tr>' for x in events)
    tx_html = "".join(f'<tr><td>{e(k)}</td><td class="r">{c:,.0f}</td><td class="r" style="color:{colr(ch)};font-weight:700">{ch:+,.0f}</td></tr>' for k, (c, ch) in tx_rows)
    g_html = "".join(f'<tr><td>{e(k)}</td><td class="r">{c}</td><td class="r" style="color:{colr(a)};font-weight:700">{a:+.1f}%</td></tr>' for k, a, c in grow)
    hl_html = "<br>\n".join(f"{i}. {e(t)}" for i, t in enumerate(hl, 1))
    top, bot = disp[:10], disp[-10:] if len(disp) >= 20 else disp[len(disp)//2:]
    movers = movers_svg(top, bot, "各集影片當日").replace("漲幅前 8", f"漲幅前 {len(top)}").replace("跌幅前 8", f"跌幅前 {len(bot)}") if disp else '<div class="mu">本週尚無播出後數據。</div>'
    sources = (latest_R["sources_text"] if latest_R else "")
    title_rng = f"{md(mon)}–{md(fri)}"
    H = f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><style>{CSS}
.wk td.tx {{ font-size:6.9pt; }} a {{ color:#1f3a5f; }}</style></head><body>
<h1>錢線百分百 週報 {e(title_rng)}</h1>
<div class="sub">涵蓋本週一～週五各集（台灣 21:00–23:30 播出）｜{e(data_line)}<br>每集完整版（全部個股與欄位）見下方連結；本週報為摘要，不刪減任何每日報告內容。</div>
<div class="box"><b>本週重點</b><br>
{hl_html}</div>
<h2>本週各集一覽</h2>
<table><tr><th>播出日</th><th>來賓</th><th class="r">檔數</th><th>族群重點</th><th>完整版</th></tr>{ep_rows}</table>
<div class="two">
<div><h2>加權指數</h2><table><tr><th>日期</th><th class="r">收盤</th><th class="r">漲跌</th></tr>{tx_html}</table></div>
<div><h2>觀點驗證（2 日）</h2><table><tr><th>集</th>{"".join(f'<th class="r">{k}</th>' for k in VERIFY_ORDER)}<th></th></tr>{vrows}</table>
<div class="legend">5 日、20 日驗證由每日自動更新補上，結果見各集完整版。</div></div>
</div>
<h2>下週事件</h2>
<table><tr><th>日期</th><th>事件</th><th>節目看點</th><th>出處</th></tr>{ev_rows}</table>
<div class="pb"></div>
<h2>播出後漲跌排行（各集影片當日 → 最新收盤）</h2>
<div class="legend">紅漲綠跌；同一檔在不同集出現時分開計算，括號為播出日。尚無播出後交易日的集數不列入。</div>
{movers}
<h2>族群表現（3 檔次以上；族群多時列最強、最弱各 6 個）</h2>
<table><tr><th>族群</th><th class="r">檔次</th><th class="r">平均</th></tr>{g_html}</table>
<div class="pb"></div>
<h2>多集重複點名個股（{len(multi)} 檔）</h2>
<div class="legend">兩集以上被列為有操作觀點的個股；觀點與價位驗證細節見各集完整版。</div>
<table class="st wk"><colgroup><col style="width:24mm"><col style="width:98mm"><col style="width:20mm"><col style="width:30mm"></colgroup>
<thead><tr><th>個股</th><th>各集觀點｜操作重點</th><th class="r">最新收盤</th><th class="r">各集播出後</th></tr></thead><tbody>{multi_rows}</tbody></table>
<h2>資料來源與聲明</h2>
<div class="legend">本週報彙整各集每日報告的計算結果。{e(sources)}<br>觀點為節目內容改寫摘要，非逐字引用。本報告不構成投資建議，亦不含任何個人持股或個人資料。</div>
</body></html>'''
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"錢線百分百_週報_{mon.strftime('%Y%m%d')}-{fri.strftime('%Y%m%d')}"
    (out_dir / f"{name}.html").write_text(H, encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(); pg.set_content(H, wait_until="load")
        pg.pdf(path=str(out_dir / f"{name}.pdf"), prefer_css_page_size=True, print_background=True); b.close()
    summary = {"title": f"錢線百分百 週報 {title_rng}", "highlights": hl, "taiex": [{"label": k, "close": c, "chg": ch} for k, (c, ch) in tx_rows],
               "top": [{"name": r["name"], "code": r["code"], "ep": r["ep"], "pct": r["since_video_pct"]} for r in mv[:3]],
               "bottom": [{"name": r["name"], "code": r["code"], "ep": r["ep"], "pct": r["since_video_pct"]} for r in mv[-3:][::-1]],
               "multi": len(multi), "episodes": len(have), "pdf": f"{name}.pdf"}
    (out_dir / "weekly.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return out_dir / f"{name}.pdf"


if __name__ == "__main__":
    fri = dt.date.fromisoformat(f"{sys.argv[1][:4]}-{sys.argv[1][4:6]}-{sys.argv[1][6:]}")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "drafts" / f"weekly_{sys.argv[1]}"
    print(build(fri, out))
