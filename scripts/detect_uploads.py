"""每小時偵測新影片：只記錄完整版上傳時間（溫哥華時間），不推送 LINE。"""
import json, re, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parent.parent
VAN = ZoneInfo("America/Vancouver")
CH = "UC_ObC9O0ZQ2FhW6u9_iFlZA"
import time
for i in range(5):   # YouTube RSS 偶爾回 404／5xx，間隔重試
    r = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={CH}",
                     headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/128.0 Safari/537.36"}, timeout=30)
    if r.status_code == 200 and "<entry>" in r.text:
        break
    time.sleep(20 * (i + 1))
r.encoding = "utf-8"
t = r.text
p = ROOT / "data" / "uploads.json"
log = json.loads(p.read_text()) if p.exists() else {}
now = dt.datetime.now(VAN).strftime("%Y-%m-%d %H:%M")
new = []
for e in re.findall(r"<entry>(.*?)</entry>", t, re.S):
    title = re.search(r"<title>([^<]+)</title>", e).group(1)
    m = re.search(r"(\d{8})\s*完整版\s*[\(（](上|中|下|全)集[\)）]", title)   # 2026-10-26 經使用者同意：「完整版(全集)」視為完整一集
    if not m:
        continue
    vid = re.search(r"<yt:videoId>([^<]+)</yt:videoId>", e).group(1)
    pub = dt.datetime.fromisoformat(re.search(r"<published>([^<]+)</published>", e).group(1)).astimezone(VAN).strftime("%Y-%m-%d %H:%M")
    day = log.setdefault(m.group(1), {})
    if m.group(2) not in day:
        day[m.group(2)] = {"video_id": vid, "published_vancouver": pub, "first_seen_vancouver": now}
        new.append(f"{m.group(1)} {m.group(2)}集（上傳 {pub}）")
p.parent.mkdir(exist_ok=True)
p.write_text(json.dumps(dict(sorted(log.items(), reverse=True)), ensure_ascii=False, indent=1))
done = [k for k, v in log.items() if len(v) >= 3 or "全" in v]
entries = len(re.findall(r"<entry>", t))
print(f"::notice title=新影片偵測 {now}（RSS {r.status_code}，{entries} 支）::新增 {len(new)} 支：{'、'.join(new) or '無'}%0A三集到齊：{'、'.join(sorted(done, reverse=True)[:3]) or '無'}")
