"""列出今天（台灣日期）已到第 5 或第 20 個交易日、但驗證還沒補上的已發布集數。
輸出：空白分隔的播出日 YYYYMMDD，給「驗證自動更新」排程使用。
"""
import json, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


def due(today=None):
    today = today or dt.datetime.now(ZoneInfo("Asia/Taipei")).date()
    out = []
    for pdf in sorted((ROOT / "docs" / "reports").glob("錢線百分百_*_統整報告.pdf")):
        ep = pdf.name.split("_")[1]
        rj = ROOT / "drafts" / ep / "report.json"
        if not rj.exists():
            continue
        core = [s for s in json.loads(rj.read_text(encoding="utf-8"))["stocks"] if s["stance"] != "背景"]
        if not core or "_dates" not in core[0]:
            continue
        d5, d20 = (dt.date.fromisoformat(core[0]["_dates"][k]) for k in ("d5", "d20"))
        v5 = any(s.get("verify5_done") for s in core)
        v20 = any(s.get("verify20_done") for s in core)
        if (d5 <= today and not v5) or (d20 <= today and not v20):
            out.append(ep)
    return out


if __name__ == "__main__":
    print(" ".join(due()))
