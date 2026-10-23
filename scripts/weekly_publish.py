"""週報發布：python weekly_publish.py 20261023 [--send-line]
把 drafts/weekly_<週五>/ 的週報 PDF 複製到 docs/weekly（GitHub Pages），需要時推送一則 LINE Flex 卡片（同一週只推一次）。
2026-10-21 經使用者同意：每日報告不推 LINE，LINE 每週只推這一則。
"""
import json, os, shutil, sys, datetime as dt, urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://jobimtg.github.io/finance-video-insights"
VAN = ZoneInfo("America/Vancouver")
UP, DN, NEU, NAVY = "#d64545", "#1a9e5c", "#8a8984", "#1f3a5f"
BANNED = ("持有", "我的持股", "成本價", "帳號", "@gmail")


def c(x): return NEU if not x else (UP if x > 0 else DN)


def flex(W, url):
    def mrow(s):
        return {"type": "box", "layout": "horizontal", "contents": [
            {"type": "text", "text": f"{s['name']}（{s['ep']}）", "size": "xs", "flex": 6, "wrap": False},
            {"type": "text", "text": f"{s['pct']:+.1f}%", "size": "xs", "weight": "bold", "align": "end", "flex": 3, "color": c(s["pct"])}]}
    t = W["taiex"]
    sep = {"type": "separator", "margin": "md"}
    body = []
    if t:
        body.append({"type": "text", "text": f"加權 {t[0]['label']} {t[0]['close']:,.0f} → {t[-1]['label']} {t[-1]['close']:,.0f}（{t[-1]['close']-t[0]['close']:+,.0f}）",
                     "size": "xs", "weight": "bold", "color": c(t[-1]['close'] - t[0]['close']), "wrap": True})
    body += [sep, {"type": "text", "text": "本週重點", "size": "sm", "weight": "bold", "color": NAVY, "margin": "md"}]
    body += [{"type": "text", "text": f"{i}. {h}", "size": "xs", "wrap": True, "color": "#333333"} for i, h in enumerate(W["highlights"][1:4], 1)]
    if W["top"]:
        body += [sep, {"type": "box", "layout": "horizontal", "spacing": "lg", "margin": "md", "contents": [
            {"type": "box", "layout": "vertical", "flex": 1, "contents": [{"type": "text", "text": "漲幅前 3", "size": "xxs", "weight": "bold", "color": UP}, *[mrow(s) for s in W["top"]]]},
            {"type": "box", "layout": "vertical", "flex": 1, "contents": [{"type": "text", "text": "跌幅前 3", "size": "xxs", "weight": "bold", "color": DN}, *[mrow(s) for s in W["bottom"]]]}]}]
    bubble = {"type": "bubble", "size": "mega",
              "header": {"type": "box", "layout": "vertical", "backgroundColor": NAVY, "paddingAll": "14px", "contents": [
                  {"type": "text", "text": W["title"], "color": "#ffffff", "weight": "bold", "size": "md"},
                  {"type": "text", "text": f"本週 {W['episodes']} 集｜多集點名 {W['multi']} 檔", "color": "#dfe6ef", "size": "xxs"}]},
              "body": {"type": "box", "layout": "vertical", "spacing": "xs", "paddingAll": "14px", "contents": body},
              "footer": {"type": "box", "layout": "vertical", "paddingAll": "12px", "contents": [
                  {"type": "button", "style": "primary", "color": NAVY, "height": "sm", "action": {"type": "uri", "label": "開啟週報 PDF", "uri": url}}]}}
    return {"type": "flex", "altText": W["title"], "contents": bubble}


def main(fri, send_line):
    d = ROOT / "drafts" / f"weekly_{fri}"
    W = json.loads((d / "weekly.json").read_text(encoding="utf-8"))
    pdf = d / W["pdf"]
    pages = len(PdfReader(str(pdf)).pages)
    text = (d / W["pdf"].replace(".pdf", ".html")).read_text(encoding="utf-8")
    bad = [w for w in BANNED if w in text]
    if not 5 <= pages <= 9 or bad:
        print(f"::error title=週報未發布::頁數 {pages}（需 5–9）；疑似個資字樣 {bad}"); return 1
    dst = ROOT / "docs" / "weekly"; dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(pdf, dst / W["pdf"])
    url = f"{BASE}/weekly/{urllib.parse.quote(W['pdf'])}"
    print(f"::notice title=週報已發布::{W['title']}｜{pages} 頁")
    if not send_line:
        return 0
    logp = ROOT / "data" / "push_log.json"
    log = json.loads(logp.read_text()) if logp.exists() else {}
    key = f"W{fri}"
    if key in log and os.environ.get("FORCE_PUSH") != "true":
        print(f"::notice title=LINE 未推送::{key} 已於 {log[key]} 推送過"); return 0
    r = requests.post("https://api.line.me/v2/bot/message/push",
                      headers={"Authorization": f"Bearer {os.environ['LINE_CHANNEL_ACCESS_TOKEN']}", "Content-Type": "application/json"},
                      json={"to": os.environ["LINE_USER_ID"], "messages": [flex(W, url)]}, timeout=30)
    if r.status_code != 200:
        print(f"::error title=LINE 推送失敗::HTTP {r.status_code} {r.text[:200]}"); return 1
    log[key] = dt.datetime.now(VAN).strftime("%Y-%m-%d %H:%M")
    logp.parent.mkdir(exist_ok=True); logp.write_text(json.dumps(log, ensure_ascii=False, indent=1))
    print(f"::notice title=LINE 已推送::{key}（溫哥華 {log[key]}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], "--send-line" in sys.argv))
