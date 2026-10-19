"""自動初檢（Agent 5、6、7 的機器可檢查部分）：python scripts/check_report.py 20261012
完整的 Agent 1–8 檢查仍由獨立 subagent 進行；這裡只做可程式化的項目。
"""
import json, re, sys
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ["view", "level_desc", "video_close", "latest", "since_video_pct", "pe", "yield", "rev_yoy",
          "inst_total", "hi52", "lo52", "off_hi52_pct", "verify"]


def main(ep):
    d = ROOT / "drafts" / ep
    R = json.loads((d / "report.json").read_text(encoding="utf-8"))
    pdf = next(d.glob("*.pdf"))
    issues, notes = [], []
    core = [s for s in R["stocks"] if s["stance"] != "背景"]
    # Agent 5：欄位完整（查無也算有標示，但要列出來給人看）
    for s in core:
        missing = [f for f in FIELDS if s.get(f) in (None, "") and not (s["is_etf"] and f in ("pe", "yield", "rev_yoy"))]
        if missing:
            notes.append(f"{s['code']}{s['name']} 查無：{'、'.join(missing)}")
        if "同上" in s["view"]:
            issues.append(f"{s['code']} 觀點寫「同上」")
    # 關鍵價位：節目價位與數據參考列（2026-10-18 定案）
    for s in core:
        ref = s.get("level_ref")
        if not ref:
            notes.append(f"{s['code']}{s['name']} 數據參考：查無（股價資料不足）")
        elif not ref.startswith("數據參考：") or ref.count("｜") != 3:
            issues.append(f"{s['code']} 數據參考列格式不符：{ref}")
        for c in s["level_checks"]:
            if c.startswith("節目：") and "查無" in c:
                notes.append(f"{s['code']}{s['name']} 節目價位換算查無：{c}")
            if c.startswith("節目：") and any(w in c for w in ("線 ≈", "線（")) and ("未達" in c or "已站上" in c):
                issues.append(f"{s['code']} 均線價位應寫「目前在其下／目前高於」：{c}")
    for s in R["stocks"]:
        if s["stance"] == "背景" and s.get("level_ref"):
            issues.append(f"附錄個股 {s['code']} 不應有數據參考列")
    if "非節目觀點" not in R["table_note"]:
        issues.append("表格說明沒有標示數據參考非節目觀點")
    for s in core:
        if "／" in s.get("group", ""):
            issues.append(f"{s['code']} 族群使用全形斜線，族群平均會漏算：{s['group']}")
    if R["episode"].get("video_date_short") == R["episode"].get("latest_date_short"):
        issues.append("最新收盤日與影片日相同，播出後漲跌全部為 0，請等下一個交易日收盤後再產出")
    for g in R["segments"]:
        if not 2 <= len(g["codes"]) <= 10:
            issues.append(f"分段「{g['title']}」有 {len(g['codes'])} 檔，應為 2–10 檔")
    seg_codes = [c for g in R["segments"] for c in g["codes"]]
    lost = [s["code"] for s in core if s["code"] not in seg_codes]
    if lost:
        issues.append(f"個股沒有放進分段：{lost}")
    if "本益比與殖利率為" not in R["table_note"]:
        issues.append("表格說明沒有標示本益比與殖利率日期")
    # Agent 6：頁數
    n = len(PdfReader(str(pdf)).pages)
    if not 5 <= n <= 9:
        issues.append(f"頁數 {n}，不在 5–9 頁")
    # Agent 7：隱私與聲明
    html = next(d.glob("*.html")).read_text(encoding="utf-8")
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", html):
        issues.append("內容含 email 格式文字")
    for w in ("持股", "成本價", "我的帳戶"):
        if w in re.sub(r"不含任何個人持股或個人資料", "", html):
            notes.append(f"出現「{w}」字樣，請人工確認不是個人資料")
    if "本報告不構成投資建議" not in html:
        issues.append("缺少免責聲明")
    if "主管機關名單比對" not in html:
        issues.append("缺少主管機關名單比對說明列")
    res = {"pages": n, "stocks": len(core), "issues": issues, "notes": notes, "pass": not issues}
    (d / "checks.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"::notice title=自動初檢 {ep}（{'通過' if not issues else '未通過'}）::" +
          "%0A".join([f"頁數 {n}、個股 {len(core)} 檔"] + [f"問題：{x}" for x in issues] + [f"備註：{x}" for x in notes[:30]]))
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
