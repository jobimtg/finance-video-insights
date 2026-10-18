"""每小時偵測新影片：只記錄完整版上傳時間（溫哥華時間），不推送 LINE。"""
import json, re, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parent.parent
VAN = ZoneInfo("America/Vancouver")
CH = "UC_ObC9O0ZQ2FhW6u9_iFlZA"
t = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={CH}", timeout=30).text
p = ROOT / "data" / "uploads.json"
log = json.loads(p.read_text()) if p.exists() else {}
now = dt.datetime.now(VAN).strftime("%Y-%m-%d %H:%M")
new = []
for e in re.findall(r"<entry>(.*?)</entry>", t, re.S):
    title = re.search(r"<title>([^<]+)</title>", e).group(1)
    m = re.search(r"(\d{8})完整版\((上|中|下)集\)", title)
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
done = [k for k, v in log.items() if len(v) == 3]
print(f"::notice title=新影片偵測 {now}::新增 {len(new)} 支：{'、'.join(new) or '無'}%0A三集到齊：{'、'.join(sorted(done, reverse=True)[:3]) or '無'}")
