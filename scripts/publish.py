"""發布：python scripts/publish.py 20261012 [--send-line]
把 drafts/<日期> 的 PDF 複製到 docs/reports（GitHub Pages），更新 docs/index.html，
需要時推送 LINE Flex 卡片給 LINE_USER_ID（同一集只推一次）。
"""
import json, os, shutil, sys, datetime as dt, urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
import flex

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://jobimtg.github.io/finance-video-insights"
VAN = ZoneInfo("America/Vancouver")


def main(ep, send_line):
    d = ROOT / "drafts" / ep
    checks = json.loads((d / "checks.json").read_text(encoding="utf-8"))
    if not checks["pass"]:
        print("::error title=未發布::自動初檢未通過，不發布"); return 1
    name = f"錢線百分百_{ep}_統整報告.pdf"
    dst = ROOT / "docs" / "reports"; dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(d / name, dst / name)
    items = sorted((p.name for p in dst.glob("*.pdf")), reverse=True)
    lis = "".join(f'<li><a href="reports/{urllib.parse.quote(n)}">{n.replace(".pdf", "")}</a></li>' for n in items)
    (ROOT / "docs" / "index.html").write_text(
        f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>財經影片統整</title><style>body{{font-family:sans-serif;max-width:640px;margin:24px auto;padding:0 16px}}</style></head>'
        f'<body><h1>財經影片統整</h1><p>節目觀點改寫摘要與公開市場數據，不構成投資建議。</p><ul>{lis}</ul></body></html>', encoding="utf-8")
    (ROOT / "docs" / ".nojekyll").write_text("")
    url = f"{BASE}/reports/{urllib.parse.quote(name)}"
    print("published", url)
    if not send_line:
        return 0
    logp = ROOT / "data" / "push_log.json"
    log = json.loads(logp.read_text()) if logp.exists() else {}
    if ep in log and os.environ.get("FORCE_PUSH") != "true":
        print(f"::notice title=LINE 未推送::{ep} 已於 {log[ep]} 推送過"); return 0
    R = json.loads((d / "report.json").read_text(encoding="utf-8"))
    air = dt.date(int(ep[:4]), int(ep[4:6]), int(ep[6:]))
    msg = flex.build(R, url, f"{air.month}/{air.day}")
    r = requests.post("https://api.line.me/v2/bot/message/push",
                      headers={"Authorization": f"Bearer {os.environ['LINE_CHANNEL_ACCESS_TOKEN']}", "Content-Type": "application/json"},
                      json={"to": os.environ["LINE_USER_ID"], "messages": [msg]}, timeout=30)
    if r.status_code != 200:
        print(f"::error title=LINE 推送失敗::HTTP {r.status_code} {r.text[:200]}"); return 1
    log[ep] = dt.datetime.now(VAN).strftime("%Y-%m-%d %H:%M")
    logp.parent.mkdir(exist_ok=True); logp.write_text(json.dumps(log, ensure_ascii=False, indent=1))
    print(f"::notice title=LINE 已推送::{ep}（溫哥華 {log[ep]}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], "--send-line" in sys.argv))
