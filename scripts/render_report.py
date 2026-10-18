"""財經影片統整 PDF 定版產生器（版面定案 2026-10-14；2026-10-17 經使用者同意加入主管機關名單標記；不得任意更改樣式）
用法：python render_report.py report.json 輸出.pdf
需要：playwright（Chromium）、Noto Sans CJK TC 字型
"""
import json, html, sys
from collections import Counter
from playwright.sync_api import sync_playwright

UP, DN, NEU = "#d64545", "#1a9e5c", "#8a8984"          # 紅漲、綠跌、持平灰
VERIFY_ORDER = ("方向一致", "方向相反", "出現拉回", "未拉回", "待觀察")
VS = {"方向一致": ("一致", "ok"), "方向相反": ("相反", "bad"), "出現拉回": ("已拉回", "warn"),
      "未拉回": ("未拉回", "info"), "待觀察": ("觀察", "na")}

def e(x): return html.escape(str(x))
def pct(x): return "—" if x is None else f"{x:+.1f}%"
def colr(x): return NEU if x is None or x == 0 else (UP if x > 0 else DN)
def n(x): return "查無" if x is None else f"{x:,.2f}".rstrip("0").rstrip(".")

def movers_svg(top, bot, base_label, w=560, rowh=16):
    rows = [("h", "漲幅前 8")] + [("s", s) for s in top] + [("gap", None), ("h", "跌幅前 8")] + [("s", s) for s in bot]
    lab, valw = 104, 46
    mid = lab + (w - lab - valw) / 2; half = (w - lab - valw) / 2 - 2
    mx = max(abs(s["since_video_pct"]) for s in top + bot) or 1
    h = rowh * len(rows) + 16
    o = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="Noto Sans CJK TC" font-size="10">']
    y = 4
    for kind, s in rows:
        if kind == "h":
            o.append(f'<text x="0" y="{y+11}" font-weight="700" fill="#1f3a5f">{e(s)}</text>')
        elif kind == "s":
            p = s["since_video_pct"]; bw = abs(p) / mx * half; x = mid if p >= 0 else mid - bw
            o.append(f'<text x="{lab-4}" y="{y+11}" text-anchor="end" fill="#333">{e(s["name"])} {s["code"]}</text>')
            o.append(f'<rect x="{x:.1f}" y="{y+3}" width="{max(bw,1):.1f}" height="{rowh-6}" rx="2" fill="{colr(p)}"/>')
            o.append(f'<text x="{w-2}" y="{y+11}" text-anchor="end" font-weight="700" fill="#333">{p:+.1f}%</text>')
        y += rowh
    o.append(f'<line x1="{mid}" y1="4" x2="{mid}" y2="{h-14}" stroke="#bbb"/>')
    o.append(f'<text x="{mid}" y="{h-3}" text-anchor="middle" fill="#666">0%｜{e(base_label)} 收盤為基準</text></svg>')
    return "".join(o)

ALERT_STYLE = {"異常推介": ("⚠異常推介", "a-rec"), "注意股": ("注意股", "a-att"), "處置股": ("處置股", "a-dis")}

def alert_tags(code, A):
    if not A or not A.get("lists"):
        return ""
    return "".join(f'<br><span class="tag {ALERT_STYLE[k][1]}">{ALERT_STYLE[k][0]}</span>'
                   for k in ("異常推介", "注意股", "處置股") if code in A["lists"].get(k, []))

def alert_note(R, core):
    A = R.get("alerts")
    if not A or not A.get("checked_date"):
        return "主管機關名單比對：本集未比對。"
    names = {s["code"]: s["name"] for s in core}
    parts = []
    for k in ("異常推介", "注意股", "處置股"):
        hit = [c for c in A["lists"].get(k, []) if c in names]
        parts.append(f"{k} {len(hit)} 檔" + (f"（{'、'.join(names[c] + ' ' + c for c in hit)}）" if hit else ""))
    return f"主管機關名單比對（截至 {A['checked_date']}，證交所、櫃買中心公告）：" + "；".join(parts) + "。"

def row(s, d5, d20, A=None):
    p = s["since_video_pct"]; etf = s["is_etf"]
    pe = "不適用" if etf else (f'{s["pe"]:.1f}' if s["pe"] else "查無")
    yl = "不適用" if etf else (f'{s["yield"]:.2f}%' if s["yield"] is not None else "查無")
    rv = "不適用" if etf else (f'{s["rev_yoy"]:+.1f}%' if s["rev_yoy"] is not None else "查無")
    inst = f'{s["inst_total"]:+,.0f}' if s["inst_total"] is not None else "查無"
    tp = f'{e(s["target_src"])}<br>{s["target"]}<br>({pct(s["target_upside_pct"])})' if s["target"] else '<span class="mu">未提及</span>'
    checks = "；".join(s["level_checks"])
    vt, vc = VS.get(s["verify"], (s["verify"], "na"))
    v5 = s.get("verify5_done") or f"待{d5}"
    v20 = s.get("verify20_done") or f"待{d20}"
    return f'''<tr>
<td class="nm"><b>{e(s["name"])}</b><br><span class="cd">{s["code"]}</span><br><span class="tag">{e(s["stance"])}</span>{alert_tags(s["code"], A)}</td>
<td class="tx">{e(s["view"])}</td>
<td class="tx">{e(s["level_desc"])}{f'<div class="ck">{e(checks)}</div>' if checks else ''}</td>
<td class="r">{n(s["video_close"])}<br>→ {n(s["latest"])}<br><b style="color:{colr(p)}">{pct(p)}</b></td>
<td class="r">{pe}<br><span class="mu">{yl}</span></td>
<td class="r">{rv}</td>
<td class="r">{inst}</td>
<td class="r">{n(s["hi52"])}<br><span class="mu">{n(s["lo52"])}</span><br>{pct(s["off_hi52_pct"])}</td>
<td class="r">{tp}</td>
<td class="vv"><b class="v-{vc}">{vt}</b><br><span class="mu">{e(v5)}</span><br><span class="mu">{e(v20)}</span></td></tr>'''

CSS = """
@page { size: A4; margin: 10mm 9mm; }
body { font-family:"Noto Sans CJK TC",sans-serif; color:#1b1b1a; font-size:9pt; line-height:1.45; margin:0; }
h1 { font-size:15pt; margin:0 0 1.5mm; }
h2 { font-size:10.5pt; margin:4mm 0 1.5mm; padding-bottom:.8mm; border-bottom:1.5px solid #1f3a5f; color:#1f3a5f; break-after:avoid; }
.sub { color:#555; font-size:8pt; }
.kpis { display:grid; grid-template-columns:repeat(3,1fr); gap:2mm; margin:2.5mm 0; }
.kpi { background:#f3f2ee; border-radius:2mm; padding:1.8mm; } .kpi .l { font-size:7.3pt; color:#555; } .kpi .v { font-size:11pt; font-weight:700; }
.box { background:#f7f6f2; border-left:3px solid #1f3a5f; padding:2mm 3mm; margin:2mm 0; }
table { width:100%; border-collapse:collapse; font-size:7.6pt; }
td,th { border-bottom:1px solid #e3e1da; padding:.9mm 1mm; text-align:left; vertical-align:top; }
th { background:#1f3a5f; color:#fff; font-weight:700; white-space:nowrap; }
thead { display:table-header-group; } tr { break-inside:avoid; }
.r { text-align:right; white-space:nowrap; }
.seg { break-after:avoid; page-break-after:avoid; } .seg td { background:#e8eef6; color:#1f3a5f; font-weight:700; font-size:8pt; }
.st { width:100%; border-collapse:collapse; table-layout:fixed; }
.st th { background:#1f3a5f; color:#fff; font-weight:700; padding:1mm; text-align:left; font-size:6.9pt; vertical-align:bottom; }
.st td { border-bottom:1px solid #e3e1da; padding:1mm; vertical-align:top; }
.nm b { font-size:8.2pt; } .cd { color:#777; font-size:6.6pt; }
.tag { display:inline-block; margin-top:.4mm; font-size:6.5pt; padding:0 1mm; border-radius:1mm; background:#e8eef6; color:#1f3a5f; font-weight:700; white-space:nowrap; }
.tx { font-size:6.9pt; } .ck { color:#7a5a00; margin-top:.5mm; } .mu { color:#888; font-size:6.6pt; }
.vv { font-size:6.9pt; } .v-ok { color:#0b7a3b; } .v-bad { color:#b02a2a; } .v-warn { color:#a26a00; } .v-info,.v-na { color:#555; }
.a-rec { background:#fbe3e3; color:#b02a2a; } .a-att { background:#fdf0d5; color:#a26a00; } .a-dis { background:#b02a2a; color:#fff; }
.legend { font-size:7.2pt; color:#555; } .pb { break-before:page; }
.two { display:grid; grid-template-columns:1fr 1fr; gap:3mm; }
"""
COLS = ('<colgroup><col style="width:15mm"><col style="width:44mm"><col style="width:36mm"><col style="width:17mm">'
        '<col style="width:13mm"><col style="width:12mm"><col style="width:13mm"><col style="width:15mm"><col style="width:13mm"><col style="width:14mm"></colgroup>')

def build_html(R):
    ep, S = R["episode"], R["stocks"]
    by = {s["code"]: s for s in S}
    core = [s for s in S if s["stance"] != "背景"]
    bg = [s for s in S if s["stance"] == "背景"]
    vc = Counter(s["verify"] for s in core)
    mv = sorted([s for s in core if s["since_video_pct"] is not None], key=lambda s: -s["since_video_pct"])
    groups = {}
    for s in core:
        if s["since_video_pct"] is not None:
            groups.setdefault(s["group"].split("/")[0], []).append(s["since_video_pct"])
    grow = sorted(((g, sum(v)/len(v), len(v)) for g, v in groups.items() if len(v) >= 2), key=lambda x: -x[1])
    d5, d20 = R["verify_dates"]["d5"], R["verify_dates"]["d20"]
    vd, ld, rm = ep["video_date_short"], ep["latest_date_short"], ep["revenue_month_label"]
    head = (f'<thead><tr><th>個股<br>觀點</th><th>觀察觀點</th><th>操作重點<br>關鍵價位驗證</th>'
            f'<th class="r">{vd} 收<br>→{ld} 收<br>播出後</th><th class="r">本益比<br>殖利率</th><th class="r">{rm}營收<br>年增</th>'
            f'<th class="r">法人<br>(張)</th><th class="r">52週高<br>52週低<br>距高</th><th class="r">分析師<br>目標價</th><th>2日<br>5日<br>20日</th></tr></thead>')
    body = ""
    for seg in R["segments"]:
        rows = "".join(row(by[c], d5, d20, R.get("alerts")) for c in seg["codes"] if c in by)
        body += f'<tr class="seg"><td colspan="10">{e(seg["title"])}</td></tr>' + rows
    kpis = "".join(f'<div class="kpi"><div class="l">加權指數 {e(k["label"])}</div><div class="v">{k["close"]:,.0f}</div>'
                   f'<div style="color:{colr(k["chg"])};font-size:8pt;font-weight:700">{k["chg"]:+,.0f}</div></div>' for k in R["taiex"])
    hl = "<br>\n".join(f'{i}. {e(t)}' for i, t in enumerate(R["highlights"], 1))
    macro = "".join(f'<tr><td>{e(m["name"])}</td><td>{e(m["latest"])}</td><td>{e(m["alert"])}</td><td>{e(m["status"])}</td></tr>' for m in R["macro"])
    events = "".join(f'<tr><td>{e(x["date"])}</td><td>{e(x["event"])}</td><td>{e(x["note"])}</td></tr>' for x in R["events"])
    bg_rows = "".join(f'<tr><td>{e(s["name"])} {s["code"]}</td><td>{e(s["view"])}</td><td class="r">{n(s["latest"])}</td>'
                      f'<td class="r" style="color:{colr(s["since_video_pct"])}">{pct(s["since_video_pct"])}</td></tr>' for s in bg)
    return f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<h1>{e(ep["show"])} {e(vd)} 個股統整</h1>
<div class="sub">{e(ep["air_line"])}<br>{e(ep["data_line"])}</div>
<div class="kpis">{kpis}</div>
<div class="box"><b>三個重點</b><br>
{hl}</div>
<h2>總經儀表</h2>
<table><tr><th>指標</th><th>最新</th><th>影片警戒</th><th>狀態</th></tr>{macro}</table>
<div class="legend">{e(R["macro_note"])}</div>
<h2>接下來的事件</h2>
<table><tr><th>日期</th><th>事件</th><th>影片看點</th></tr>{events}</table>
<div class="pb"></div>
<h2>播出後漲跌（{e(vd)} → {e(ld)}）</h2>
<div class="legend">紅漲綠跌（台股慣例），數字附正負號；只列有操作觀點的 {len(core)} 檔中漲跌幅最大者。</div>
{movers_svg(mv[:8], mv[-8:], vd)}
<div class="two">
<div><h2>觀點驗證（2 日）</h2>
<table><tr><th>狀態</th><th class="r">檔數</th></tr>
{"".join(f'<tr><td>{k}</td><td class="r">{vc.get(k,0)}</td></tr>' for k in VERIFY_ORDER)}</table>
<div class="legend">5 日驗證於 {e(d5)}、20 日驗證於 {e(d20)} 收盤後更新。方向一致＝偏多後漲、偏空或不追高後跌；未拉回＝建議等拉回但續漲。</div></div>
<div><h2>族群平均</h2>
<table><tr><th>族群</th><th class="r">檔</th><th class="r">平均</th></tr>{"".join(f'<tr><td>{e(g)}</td><td class="r">{c}</td><td class="r" style="color:{colr(a)};font-weight:700">{a:+.1f}%</td></tr>' for g,a,c in grow)}</table></div>
</div>
<div class="pb"></div>
<h2>個股總表（{len(core)} 檔，依族群分段）</h2>
<div class="legend">{e(R["table_note"])}</div>
<table class="st">{COLS}{head}<tbody>{body}</tbody></table>
<div class="legend" style="margin-top:1.5mm">{e(alert_note(R, core))}</div>
<h2>附錄：背景與比較用個股</h2>
<table><tr><th>個股</th><th>影片中角色</th><th class="r">最新</th><th class="r">播出後</th></tr>{bg_rows}</table>
<h2>資料來源</h2>
<div class="legend">{e(R["sources_text"])}<br>觀點為節目內容改寫摘要，非逐字引用。本報告不構成投資建議，亦不含任何個人持股或個人資料。</div>
</body></html>'''

def render(report_json, out_pdf):
    R = json.load(open(report_json, encoding="utf-8"))
    H = build_html(R)
    open(out_pdf.replace(".pdf", ".html"), "w", encoding="utf-8").write(H)
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.set_content(H, wait_until="load")
        pg.pdf(path=out_pdf, prefer_css_page_size=True, print_background=True); b.close()

if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2])
