"""直連測試：確認 GitHub Actions 能否連到各資料來源（只讀取，不推送任何訊息）。

結果寫進 GitHub Actions 的執行摘要與 results/connectivity.json（artifact，不進 repo）。
金鑰只從環境變數讀取，任何金鑰值與帳號資訊都不會輸出。
"""
import json, os, re, time, datetime as dt
from zoneinfo import ZoneInfo
import requests

VAN = ZoneInfo("America/Vancouver")
UA = {"User-Agent": "finance-video-insights connectivity test"}
CHANNEL_ID = "UC_ObC9O0ZQ2FhW6u9_iFlZA"
results = []


def probe(group, name, url, *, headers=None, params=None, expect="json", count=None, note=""):
    t0 = time.time()
    row = {"group": group, "name": name, "url": url.split("?")[0], "ok": False,
           "status": None, "ms": None, "records": None, "detail": note}
    try:
        r = requests.get(url, headers={**UA, **(headers or {})}, params=params, timeout=30)
        row["status"] = r.status_code
        row["ms"] = int((time.time() - t0) * 1000)
        if r.status_code != 200:
            row["detail"] = (note + " " + r.text[:120].replace("\n", " ")).strip()
        elif expect == "json":
            data = r.json()
            row["records"] = count(data) if count else (len(data) if isinstance(data, list) else None)
            row["ok"] = True
        else:
            row["records"] = count(r.text) if count else len(r.text)
            row["ok"] = True
        row["_body"] = r.text if row["ok"] else None
    except Exception as e:  # 連線錯誤、逾時、非 JSON
        row["ms"] = int((time.time() - t0) * 1000)
        row["detail"] = f"{note} {type(e).__name__}: {str(e)[:120]}".strip()
    results.append(row)
    return row


# 1. 證交所 OpenAPI（政府資料開放授權條款）
T = "https://openapi.twse.com.tw/v1"
for path, name in [("/exchangeReport/STOCK_DAY_ALL", "上市個股日成交"),
                   ("/exchangeReport/BWIBBU_ALL", "上市本益比殖利率"),
                   ("/opendata/t187ap05_L", "上市月營收"),
                   ("/exchangeReport/MI_INDEX", "大盤統計"),
                   ("/exchangeReport/FMSRFK_ALL", "上市個股月成交（月高低）"),
                   ("/Announcement/BFZFZU_T", "投資理財節目異常推介個股"),
                   ("/announcement/notice", "上市注意股"),
                   ("/announcement/punish", "上市處置股")]:
    probe("證交所 OpenAPI", name, T + path)

# 2. 櫃買中心 OpenAPI
P = "https://www.tpex.org.tw/openapi/v1"
for path, name in [("/tpex_mainboard_daily_close_quotes", "上櫃行情"),
                   ("/tpex_mainboard_peratio_analysis", "上櫃本益比殖利率"),
                   ("/mopsfin_t187ap05_O", "上櫃月營收"),
                   ("/tpex_3insti_daily_trading", "上櫃三大法人個股"),
                   ("/tpex_3insti_summary", "上櫃三大法人彙總"),
                   ("/tpex_trading_warning_information", "上櫃注意股"),
                   ("/tpex_disposal_information", "上櫃處置股")]:
    probe("櫃買 OpenAPI", name, P + path)

# 3. FRED（公開 CSV，不需金鑰）
for sid in ["DGS10", "DGS30", "DEXTAUS", "DCOILBRENTEU"]:
    probe("FRED", sid, "https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": sid},
          expect="text", count=lambda t: max(0, t.count("\n") - 1))

# 4. FinMind（有金鑰就帶，沒有就用匿名額度；只查 1 檔）
fm_token = os.environ.get("FINMIND_TOKEN", "").strip()
fm_head = {"Authorization": f"Bearer {fm_token}"} if fm_token else {}
start = (dt.date.today() - dt.timedelta(days=14)).isoformat()
for ds in ["TaiwanStockInstitutionalInvestorsBuySell", "TaiwanStockPrice"]:
    probe("FinMind", ds + ("（有金鑰）" if fm_token else "（未設定金鑰）"),
          "https://api.finmindtrade.com/api/v4/data", headers=fm_head,
          params={"dataset": ds, "data_id": "2330", "start_date": start},
          count=lambda d: len(d.get("data", [])) if isinstance(d, dict) else None)

# 5. YouTube RSS 與字幕（實驗功能）
rss = probe("YouTube", "頻道 RSS", f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}",
            expect="text", count=lambda t: t.count("<entry>"))
video_id = None
if rss["ok"]:
    entries = re.findall(r"<yt:videoId>([^<]+)</yt:videoId>\s*<yt:channelId>[^<]+</yt:channelId>\s*<title>([^<]+)</title>", rss["_body"])
    full = [(v, t) for v, t in entries if "完整版" in t]
    rss["detail"] = f"完整版 {len(full)} 支"
    video_id = full[0][0] if full else None
row = {"group": "YouTube", "name": "自動抓字幕（實驗）", "url": "youtube-transcript-api",
       "ok": False, "status": None, "ms": None, "records": None, "detail": ""}
if video_id:
    t0 = time.time()
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        tr = YouTubeTranscriptApi().fetch(video_id, languages=["zh-TW", "zh-Hant", "zh"])
        row.update(ok=True, records=len(tr.snippets), detail="字幕段數")
    except Exception as e:
        row["detail"] = f"{type(e).__name__}"
    row["ms"] = int((time.time() - t0) * 1000)
else:
    row["detail"] = "RSS 沒有完整版影片，未測試"
results.append(row)

# 6. LINE（只驗證金鑰是否有效，不發送任何訊息、不輸出帳號資訊）
line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
if line_token:
    r = probe("LINE", "金鑰驗證（不發訊息）", "https://api.line.me/v2/bot/info",
              headers={"Authorization": f"Bearer {line_token}"}, count=lambda d: None)
    r["detail"] = "金鑰有效" if r["ok"] else "金鑰無效或無法連線"
    q = probe("LINE", "本月已用訊息數", "https://api.line.me/v2/bot/message/quota/consumption",
              headers={"Authorization": f"Bearer {line_token}"}, count=lambda d: d.get("totalUsage"))
    q2 = probe("LINE", "每月訊息上限", "https://api.line.me/v2/bot/message/quota",
               headers={"Authorization": f"Bearer {line_token}"}, count=lambda d: d.get("value"))
else:
    results.append({"group": "LINE", "name": "金鑰驗證", "url": "", "ok": False, "status": None,
                    "ms": None, "records": None, "detail": "未設定 LINE_CHANNEL_ACCESS_TOKEN"})
results.append({"group": "LINE", "name": "LINE_USER_ID 已設定", "url": "", "ok": bool(os.environ.get("LINE_USER_ID", "").strip()),
                "status": None, "ms": None, "records": None, "detail": "只檢查是否存在，不輸出內容"})

# 輸出
now = dt.datetime.now(VAN).strftime("%Y-%m-%d %H:%M")
for r in results:
    r.pop("_body", None)
os.makedirs("results", exist_ok=True)
json.dump({"tested_at_vancouver": now, "results": results}, open("results/connectivity.json", "w"), ensure_ascii=False, indent=1)
lines = [f"## 直連測試結果（溫哥華時間 {now}）", "", "| 來源 | 項目 | 結果 | HTTP | 毫秒 | 筆數 | 說明 |", "|---|---|---|---|---|---|---|"]
for r in results:
    lines.append(f"| {r['group']} | {r['name']} | {'✅' if r['ok'] else '❌'} | {r['status'] or ''} | {r['ms'] or ''} | {'' if r['records'] is None else r['records']} | {r['detail']} |")
ok = sum(r["ok"] for r in results)
lines += ["", f"通過 {ok}／{len(results)} 項。"]
text = "\n".join(lines)
print(text)
# 每個來源一則 notice 註記（方便用 API 讀取結果；不含任何金鑰或帳號資訊）
if os.environ.get("GITHUB_ACTIONS"):
    groups = {}
    for r in results:
        groups.setdefault(r["group"], []).append(r)
    for g, rs in groups.items():
        body = "%0A".join(f"{'OK' if r['ok'] else 'NG'}|{r['name']}|{r['status'] or ''}|{r['ms'] or ''}|{'' if r['records'] is None else r['records']}|{r['detail'][:90]}" for r in rs)
        print(f"::notice title={g}::{body}")
if os.environ.get("GITHUB_STEP_SUMMARY"):
    open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write(text + "\n")
