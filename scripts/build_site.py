"""報告網站產生器：python scripts/build_site.py
從 docs/reports 已發布的 PDF，對應 drafts/<日期>/report.json，重建 GitHub Pages 首頁。
版面（2026-10-18 定案）：最新一集儀表板＋往期報告卡片牆＋個股索引（搜尋＋族群／觀點／驗證篩選），
配色採報紙風（米粉底、深棕字、藍綠強調），深色模式跟隨裝置設定自動切換。不開放搜尋引擎索引（noindex＋robots.txt 全部禁止，2026-10-18 改）。
只用報告中已公開的計算結果，不含任何個人資料。
"""
import json, html, datetime as dt, urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://jobimtg.github.io/finance-video-insights"
VAN = ZoneInfo("America/Vancouver")
WEEK = "一二三四五六日"
DESC = "錢線百分百節目個股觀點的改寫摘要，搭配證交所、櫃買中心等公開市場數據與播出後 2／5／20 日驗證。不構成投資建議。"


def e(x):
    return html.escape(str(x))


def episodes():
    out = []
    for pdf in sorted((ROOT / "docs" / "reports").glob("錢線百分百_*_統整報告.pdf"), reverse=True):
        ep = pdf.name.split("_")[1]
        rj = ROOT / "drafts" / ep / "report.json"
        if not rj.exists():
            continue
        R = json.loads(rj.read_text(encoding="utf-8"))
        air = dt.date(int(ep[:4]), int(ep[4:6]), int(ep[6:]))
        core = [s for s in R["stocks"] if s["stance"] != "背景"]
        segs = [g["title"] for g in R["segments"]]
        A = R.get("alerts") or {}
        codes = {s["code"] for s in R["stocks"]}
        out.append({
            "ep": ep, "date": f"{air.month:02d}/{air.day:02d}", "wd": WEEK[air.weekday()], "ym": f"{air.year} 年 {air.month} 月",
            "pdf": "reports/" + urllib.parse.quote(pdf.name),
            "topic": "、".join(segs[:2]) + (f" 等 {len(segs)} 個族群" if len(segs) > 2 else ""),
            "data_line": R["episode"]["data_line"], "air_line": R["episode"]["air_line"],
            "taiex": R["taiex"], "highlights": R["highlights"], "verify_dates": R["verify_dates"],
            "alerts": {k: sorted(c for c in v if c in codes) for k, v in (A.get("lists") or {}).items()} if A.get("checked_date") else None,
            "alerts_date": A.get("checked_date"),
            "v5": any(s.get("verify5_done") for s in core), "v20": any(s.get("verify20_done") for s in core),
            "stocks": [{k: s.get(k) for k in ("code", "name", "group", "stance", "view", "level_desc", "level_checks", "level_ref",
                                               "since_video_pct", "verify", "verify5_done", "verify20_done", "latest", "latest_date")}
                       for s in core],
        })
    return out


CSS = """
:root{--bg:#fff1e5;--card:#fff9f3;--ink:#33302e;--mu:#6f6a65;--acc:#0d7680;--line:#e6d6c6;--hd:#33302e;--hdtx:#fff1e5;
--up:#c0392b;--dn:#1e8449;--btn:#33302e;--btntx:#fff1e5;--chip:#f2dfce}
@media (prefers-color-scheme:dark){:root{--bg:#1d1a18;--card:#262220;--ink:#f2e6da;--mu:#b3a89d;--acc:#4fb3bf;--line:#3b3531;
--hd:#141210;--hdtx:#f2e6da;--up:#ff6b5e;--dn:#3fbf7f;--btn:#f2dfce;--btntx:#1d1a18;--chip:#3b3531}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Noto Sans TC","Noto Sans CJK TC","PingFang TC","Microsoft JhengHei",sans-serif;line-height:1.55}
a{color:inherit}
header{background:var(--hd);color:var(--hdtx);padding:20px 24px 0}
.hrow{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;max-width:1100px;margin:0 auto}
h1{font-size:26px;margin:0;letter-spacing:.5px}.tag{font-size:12px;opacity:.8}
nav{max-width:1100px;margin:10px auto 0;display:flex;gap:4px}
nav button{background:none;border:0;color:var(--hdtx);font:inherit;font-size:15px;padding:10px 12px 12px;cursor:pointer;opacity:.75;border-bottom:3px solid transparent}
nav button[aria-selected=true]{opacity:1;font-weight:700;border-bottom-color:var(--acc)}
main{max-width:1100px;margin:0 auto;padding:22px 24px 8px}
section[hidden]{display:none}
h2{font-size:20px;margin:0 0 2px}h3{font-size:15px;margin:22px 0 10px;border-top:3px solid var(--ink);padding-top:6px}
.mu{color:var(--mu)}.sm{font-size:12px}.n{font-variant-numeric:tabular-nums}
.cd{background:var(--card);border:1px solid var(--line)}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:12px}
.kpi{padding:10px 12px}.kpi .v{font-size:22px;font-weight:700}.kpi .c{font-weight:700}
.grid2{display:grid;grid-template-columns:1.25fr 1fr;gap:14px;margin-top:14px}
.pad{padding:14px}
.bar{display:flex;align-items:center;gap:8px;font-size:13px;margin:5px 0}.bar .nm{width:72px;text-align:right;flex:none}
.bar .tr{flex:1;height:12px}.bar .f{height:12px}.bar .p{width:56px;text-align:right;font-weight:700;flex:none}
.hl p{font-size:14px;margin:8px 0}.hl b{color:var(--acc);margin-right:6px}
.btn{display:block;text-align:center;background:var(--btn);color:var(--btntx);padding:11px;margin-top:12px;font-weight:700;text-decoration:none}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.card{display:block;text-decoration:none;color:inherit}.card .top{padding:10px 12px;border-bottom:1px solid var(--line)}
.card .d{font-size:22px;font-weight:700;color:var(--acc)}.card .body{padding:10px 12px}
.card .row{display:flex;justify-content:space-between;font-size:13px}
.badge{display:inline-block;font-size:11px;padding:1px 6px;margin:6px 4px 0 0;background:var(--chip)}
.badge.ok{background:var(--acc);color:#fff}
.month{font-size:14px;font-weight:700;margin:18px 0 8px}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.filters input,.filters select{font:inherit;font-size:14px;padding:8px 10px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.filters input{flex:1;min-width:200px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:9px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;color:var(--mu);font-weight:700}tbody tr.s{cursor:pointer}tbody tr.s:hover{background:var(--chip)}
td.r,th.r{text-align:right}
.det td{background:var(--bg);font-size:13px}.det .ep{margin:4px 0 10px;padding-left:10px;border-left:3px solid var(--acc)}
.ck{color:#8a6400}.rf{color:var(--mu);font-size:12px}
@media (prefers-color-scheme:dark){.ck{color:#e0b44c}}
footer{max-width:1100px;margin:24px auto 0;padding:12px 24px 30px;border-top:1px solid var(--line);font-size:12px;color:var(--mu)}
@media (max-width:720px){header{padding:14px 14px 0}h1{font-size:21px}.tag{display:none}main{padding:16px 14px 8px}
.grid2{grid-template-columns:1fr}.kpis{gap:8px}.kpi .v{font-size:17px}.kpi{padding:8px}nav button{padding:8px 8px 10px;font-size:14px}
.hide-m{display:none}footer{padding:12px 14px 24px}}
"""

JS = r"""
const D=JSON.parse(document.getElementById('d').textContent);
const $=s=>document.querySelector(s);const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const col=x=>x>0?'var(--up)':x<0?'var(--dn)':'var(--mu)';const pc=x=>x==null?'—':(x>0?'+':'')+x.toFixed(1)+'%';
function tab(t){document.querySelectorAll('nav button').forEach(b=>b.setAttribute('aria-selected',b.dataset.t===t));
 document.querySelectorAll('main>section').forEach(s=>s.hidden=s.id!==t);}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{history.replaceState(null,'','#'+b.dataset.t);tab(b.dataset.t)});
tab(['latest','archive','index'].includes(location.hash.slice(1))?location.hash.slice(1):'latest');
// 個股索引：彙整各集提到的個股
const M={};D.forEach(ep=>ep.stocks.forEach(s=>{(M[s.code]=M[s.code]||{code:s.code,name:s.name,group:s.group,list:[]}).list.push({ep,s})}));
const rows=Object.values(M);const uniq=a=>[...new Set(a)].sort();
const fill=(id,vals)=>{$(id).innerHTML+=vals.map(v=>`<option>${esc(v)}</option>`).join('')};
fill('#fg',uniq(rows.map(r=>r.group.split('/')[0])));fill('#fs',uniq(rows.flatMap(r=>r.list.map(x=>x.s.stance))));
fill('#fv',uniq(rows.flatMap(r=>r.list.map(x=>x.s.verify))));
function draw(){const q=$('#q').value.trim().toLowerCase(),g=$('#fg').value,st=$('#fs').value,v=$('#fv').value;
 const hit=rows.filter(r=>(!q||r.code.includes(q)||r.name.toLowerCase().includes(q))&&(!g||r.group.split('/')[0]===g)
   &&(!st||r.list.some(x=>x.s.stance===st))&&(!v||r.list.some(x=>x.s.verify===v)));
 $('#cnt').textContent=`共 ${hit.length} 檔`;
 $('#tb').innerHTML=hit.map(r=>{const x=r.list[0];return `<tr class="s" data-c="${r.code}"><td><b>${esc(r.name)}</b> <span class="mu sm">${r.code}</span></td>
  <td class="hide-m">${esc(r.group)}</td><td>${esc(x.s.stance)}</td><td class="r hide-m">${r.list.length}</td>
  <td class="r n" style="color:${col(x.s.since_video_pct)}">${pc(x.s.since_video_pct)}</td><td>${esc(x.s.verify)}</td></tr>
  <tr class="det" id="d${r.code}" hidden><td colspan="6">${r.list.map(({ep,s})=>`<div class="ep"><b>${ep.date}（週${ep.wd}）｜${esc(s.stance)}</b>
  <span class="n" style="color:${col(s.since_video_pct)}"> 播出後 ${pc(s.since_video_pct)}</span><div>${esc(s.view)}</div>
  <div class="mu">操作重點：${esc(s.level_desc||'—')}</div><div class="ck">${esc((s.level_checks||[]).join('；'))}</div>
  ${s.level_ref?`<div class="rf">${esc(s.level_ref)}（非節目觀點）</div>`:''}
  <div class="sm">驗證：2 日 ${esc(s.verify)}｜5 日 ${esc(s.verify5_done||'待'+ep.verify_dates.d5)}｜20 日 ${esc(s.verify20_done||'待'+ep.verify_dates.d20)}｜<a href="${ep.pdf}">PDF</a></div></div>`).join('')}</td></tr>`}).join('');
 document.querySelectorAll('tr.s').forEach(t=>t.onclick=()=>{const d=$('#d'+t.dataset.c);d.hidden=!d.hidden});}
['#q','#fg','#fs','#fv'].forEach(id=>$(id).addEventListener('input',draw));draw();
"""


def build():
    E = episodes()
    now = dt.datetime.now(VAN).strftime("%Y-%m-%d %H:%M")
    docs = ROOT / "docs"
    if not E:
        return
    L = E[0]
    core = [s for s in L["stocks"] if s["since_video_pct"] is not None]
    mv = sorted(core, key=lambda s: -s["since_video_pct"])
    sel = mv[:5] + mv[-5:]
    mx = max(abs(s["since_video_pct"]) for s in sel) or 1
    col = lambda x: "var(--up)" if x > 0 else ("var(--dn)" if x < 0 else "var(--mu)")
    kp = "".join(f'<div class="cd kpi"><div class="mu sm">加權 {e(k["label"])}</div><div class="v n">{k["close"]:,.0f}</div>'
                 f'<div class="c n" style="color:{col(k["chg"])}">{k["chg"]:+,.0f}</div></div>' for k in L["taiex"])
    bars = "".join(f'<div class="bar"><span class="nm">{e(s["name"])}</span><div class="tr"><div class="f" style="width:{abs(s["since_video_pct"]) / mx * 100:.0f}%;background:{col(s["since_video_pct"])}"></div></div>'
                   f'<span class="p n" style="color:{col(s["since_video_pct"])}">{s["since_video_pct"]:+.1f}%</span></div>' for s in sel)
    hl = "".join(f"<p><b>{i}</b>{e(h)}</p>" for i, h in enumerate(L["highlights"], 1))
    from collections import Counter
    vc = Counter(s["verify"] for s in L["stocks"])
    al = ""
    if L["alerts"]:
        al = f'<p class="sm mu">主管機關名單（{e(L["alerts_date"])}）：' + "、".join(f'{k} {len(v)} 檔' for k, v in L["alerts"].items()) + "</p>"
    vstate = lambda x: ("<span class='badge ok'>20 日驗證已更新</span>" if x["v20"] else "") + \
                       ("<span class='badge ok'>5 日驗證已更新</span>" if x["v5"] else f"<span class='badge'>5 日驗證 待{e(x['verify_dates']['d5'])}</span>") + \
                       ("" if x["v20"] else f"<span class='badge'>20 日 待{e(x['verify_dates']['d20'])}</span>")
    cards, ym = "", None
    for x in E:
        if x["ym"] != ym:
            ym = x["ym"]; cards += ("</div>" if cards else "") + f'<div class="month">{e(ym)}</div><div class="cards">'
        xm = sorted([s for s in x["stocks"] if s["since_video_pct"] is not None], key=lambda s: -s["since_video_pct"])[:3]
        cards += (f'<a class="cd card" href="{x["pdf"]}"><div class="top"><span class="mu sm">週{x["wd"]}</span><div class="d n">{x["date"]}</div></div>'
                  f'<div class="body"><div style="font-weight:700;font-size:14px;margin-bottom:6px">{e(x["topic"])}</div>'
                  + "".join(f'<div class="row"><span>{e(s["name"])}</span><b class="n" style="color:{col(s["since_video_pct"])}">{s["since_video_pct"]:+.1f}%</b></div>' for s in xm)
                  + f'<div class="mu sm" style="margin-top:6px">{len(x["stocks"])} 檔個股</div>{vstate(x)}</div></a>')
    cards += "</div>"
    data = json.dumps(E, ensure_ascii=False).replace("</", "<\\/")
    page = f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>財經影片統整｜錢線百分百個股觀點與數據追蹤</title>
<meta name="description" content="{e(DESC)}"><meta name="robots" content="noindex,nofollow">
<meta property="og:type" content="website"><meta property="og:title" content="財經影片統整｜錢線百分百個股觀點與數據追蹤">
<meta property="og:description" content="{e(DESC)}"><meta property="og:url" content="{BASE}/"><meta name="theme-color" content="#33302e">
<style>{CSS}</style></head><body>
<header><div class="hrow"><h1>財經影片統整</h1><span class="tag">錢線百分百｜節目觀點改寫摘要＋公開市場數據</span></div>
<nav role="tablist"><button role="tab" data-t="latest">最新一集</button><button role="tab" data-t="archive">往期報告</button><button role="tab" data-t="index">個股索引</button></nav></header>
<main>
<section id="latest"><h2>錢線百分百 {L["date"]}（週{L["wd"]}）個股統整</h2>
<div class="mu sm">{e(L["air_line"])}<br>{e(L["data_line"])}</div>
<div class="kpis">{kp}</div>
<div class="grid2"><div class="cd pad"><b>播出後漲跌　前 5／後 5</b>{bars}</div>
<div class="cd pad hl"><b style="color:var(--ink)">三個重點</b>{hl}
<p class="sm mu">2 日驗證：一致 {vc.get("方向一致", 0)}・相反 {vc.get("方向相反", 0)}・已拉回 {vc.get("出現拉回", 0)}・未拉回 {vc.get("未拉回", 0)}・待觀察 {vc.get("待觀察", 0)}<br>{vstate(L)}</p>{al}
<a class="btn" href="{L["pdf"]}">開啟完整 PDF</a></div></div></section>
<section id="archive" hidden><h2>往期報告</h2><div class="mu sm">點卡片開啟 PDF；5 日、20 日驗證到期後會自動更新標籤。</div>{cards}</section>
<section id="index" hidden><h2>個股索引</h2><div class="mu sm" style="margin-bottom:10px">彙整各集提到的個股，點一列展開歷次觀點與驗證。</div>
<div class="filters"><input id="q" type="search" placeholder="輸入代號或名稱，例如 2330" aria-label="搜尋個股">
<select id="fg" aria-label="族群"><option value="">全部族群</option></select><select id="fs" aria-label="觀點"><option value="">全部觀點</option></select>
<select id="fv" aria-label="驗證結果"><option value="">全部驗證結果</option></select></div>
<div class="mu sm" id="cnt"></div>
<table><thead><tr><th>個股</th><th class="hide-m">族群</th><th>最新觀點</th><th class="r hide-m">提及次數</th><th class="r">播出後</th><th>2 日驗證</th></tr></thead><tbody id="tb"></tbody></table></section>
</main>
<footer>觀點為節目內容改寫摘要，非逐字引用。本網站不構成投資建議，亦不含任何個人持股或個人資料。<br>
資料來源：臺灣證券交易所、證券櫃檯買賣中心 OpenAPI（政府資料開放授權條款－第1版）、FinMind、FRED（Federal Reserve Bank of St. Louis）。灰字「數據參考」為公開股價計算，非節目觀點。<br>
網站更新：{now}（溫哥華時間）</footer>
<script type="application/json" id="d">{data}</script><script>{JS}</script></body></html>'''
    (docs / "index.html").write_text(page, encoding="utf-8")
    (docs / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")   # 2026-10-18 定案：不開放搜尋引擎索引
    (docs / "sitemap.xml").unlink(missing_ok=True)
    (docs / ".nojekyll").write_text("")
    print("site built:", len(E), "episodes")


if __name__ == "__main__":
    build()
