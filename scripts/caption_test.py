"""字幕抓取測試：在 GitHub Actions 上嘗試多種方式取得「完整版」影片的字幕。
只統計結果（成功與否、字幕段數、字數），不輸出字幕內容。結果以 notice 註記輸出。
"""
import json, os, re, subprocess, time, glob
import requests

CHANNEL_ID = "UC_ObC9O0ZQ2FhW6u9_iFlZA"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept-Language": "zh-TW,zh;q=0.9"}
COOKIES = {"CONSENT": "YES+", "SOCS": "CAI"}
LANGS = ("zh-TW", "zh-Hant", "zh")
results = []


def add(method, ok, detail, n=None):
    results.append({"method": method, "ok": ok, "detail": str(detail)[:150], "segments": n})


def latest_full_video():
    t = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}", headers=UA, timeout=30).text
    entries = re.findall(r"<yt:videoId>([^<]+)</yt:videoId>\s*<yt:channelId>[^<]+</yt:channelId>\s*<title>([^<]+)</title>", t)
    full = [(v, ti) for v, ti in entries if "完整版" in ti]
    return full[0] if full else (None, None)


def count_json3(text):
    try:
        ev = json.loads(text).get("events", [])
        segs = [e for e in ev if e.get("segs")]
        chars = sum(len("".join(s.get("utf8", "") for s in e["segs"])) for e in segs)
        return len(segs), chars
    except Exception:
        return 0, 0


def fetch_track(base_url, method):
    url = base_url + ("&" if "?" in base_url else "?") + "fmt=json3"
    r = requests.get(url, headers=UA, cookies=COOKIES, timeout=30)
    n, chars = count_json3(r.text) if r.status_code == 200 else (0, 0)
    add(method, n > 0, f"HTTP {r.status_code}，{n} 段、{chars} 字" + ("" if n else f"，回應長度 {len(r.text)}"), n)


def pick_track(tracks):
    for lang in LANGS:
        for t in tracks:
            if t.get("languageCode", "").startswith(lang) and t.get("kind") != "asr":
                return t
    return tracks[0] if tracks else None


vid, title = latest_full_video()
if not vid:
    add("RSS", False, "找不到完整版影片")
else:
    add("RSS", True, f"測試影片 {vid}")

    # 方式 1：yt-dlp 只下載字幕
    try:
        out = subprocess.run(["yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs",
                              "--sub-langs", "zh-TW,zh-Hant,zh.*", "--sub-format", "json3",
                              "-o", "/tmp/cap/%(id)s.%(ext)s", f"https://www.youtube.com/watch?v={vid}"],
                             capture_output=True, text=True, timeout=180)
        files = glob.glob("/tmp/cap/*.json3")
        if files:
            n, chars = count_json3(open(files[0], encoding="utf-8").read())
            add("1 yt-dlp", n > 0, f"{os.path.basename(files[0]).split('.',1)[1]}，{n} 段、{chars} 字", n)
        else:
            err = (out.stderr or out.stdout).strip().splitlines()
            add("1 yt-dlp", False, err[-1] if err else "沒有字幕檔")
    except Exception as e:
        add("1 yt-dlp", False, f"{type(e).__name__}: {e}")

    # 方式 2：觀看頁 HTML → captionTracks → 字幕網址
    try:
        r = requests.get(f"https://www.youtube.com/watch?v={vid}&hl=zh-TW", headers=UA, cookies=COOKIES, timeout=30)
        m = re.search(r'"captionTracks":(\[.*?\])', r.text)
        if not m:
            reason = re.search(r'"reason":"([^"]{0,80})', r.text)
            add("2 觀看頁", False, f"HTTP {r.status_code}，頁面沒有字幕清單" + (f"（{reason.group(1)}）" if reason else ""))
        else:
            tracks = json.loads(m.group(1).encode().decode("unicode_escape"))
            t = pick_track(tracks)
            fetch_track(t["baseUrl"].replace("\\u0026", "&"), f"2 觀看頁（{t.get('languageCode')}）")
    except Exception as e:
        add("2 觀看頁", False, f"{type(e).__name__}: {e}")

    # 方式 3：YouTube 內部 player API（不同用戶端）
    for cname, cver in [("WEB", "2.20250101.00.00"), ("ANDROID", "19.09.37"), ("TVHTML5_SIMPLY_EMBEDDED_PLAYER", "2.0")]:
        try:
            body = {"context": {"client": {"clientName": cname, "clientVersion": cver, "hl": "zh-TW"}}, "videoId": vid}
            r = requests.post("https://www.youtube.com/youtubei/v1/player?prettyPrint=false", json=body, headers=UA, cookies=COOKIES, timeout=30)
            d = r.json()
            tracks = d.get("captions", {}).get("playerCaptionsTracklistRenderer", {}).get("captionTracks", [])
            if not tracks:
                st = d.get("playabilityStatus", {})
                add(f"3 player API {cname}", False, f"HTTP {r.status_code}，{st.get('status')}：{st.get('reason', '沒有字幕清單')}")
            else:
                t = pick_track(tracks)
                fetch_track(t["baseUrl"], f"3 player API {cname}（{t.get('languageCode')}）")
        except Exception as e:
            add(f"3 player API {cname}", False, f"{type(e).__name__}: {e}")

    # 方式 4：舊版 timedtext 網址
    for host in ["https://www.youtube.com/api/timedtext", "https://video.google.com/timedtext"]:
        for lang in ("zh-TW", "zh-Hant"):
            try:
                r = requests.get(host, params={"v": vid, "lang": lang, "fmt": "json3"}, headers=UA, timeout=30)
                n, chars = count_json3(r.text) if r.text.strip() else (0, 0)
                add(f"4 timedtext {host.split('/')[2]} {lang}", n > 0, f"HTTP {r.status_code}，{n} 段、{chars} 字，回應長度 {len(r.text)}", n)
            except Exception as e:
                add(f"4 timedtext {host.split('/')[2]} {lang}", False, f"{type(e).__name__}: {e}")

ok = [r for r in results if r["ok"] and r["method"] != "RSS"]
body = "%0A".join(f"{'OK' if r['ok'] else 'NG'}|{r['method']}|{r['detail']}" for r in results)
print(f"::notice title=字幕測試（成功 {len(ok)} 種）::{body}")
print(json.dumps(results, ensure_ascii=False, indent=1))
