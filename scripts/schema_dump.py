"""一次性：列出各資料來源的欄位名稱與第一筆範例（公開資料，不含金鑰）。"""
import json, os, requests, datetime as dt
UA = {"User-Agent": "finance-video-insights schema dump"}
out = []
def dump(name, url, params=None, headers=None, pick=None):
    try:
        r = requests.get(url, params=params, headers={**UA, **(headers or {})}, timeout=60)
        d = r.json()
        rows = d.get("data", d) if isinstance(d, dict) else d
        if pick: rows = [x for x in rows if pick(x)] or rows
        first = rows[0] if isinstance(rows, list) and rows else rows
        out.append(f"{name}|{len(rows) if isinstance(rows, list) else ''}|{json.dumps(first, ensure_ascii=False)[:700]}")
    except Exception as e:
        out.append(f"{name}|ERR|{type(e).__name__}: {str(e)[:150]}")
T = "https://openapi.twse.com.tw/v1"; P = "https://www.tpex.org.tw/openapi/v1"
has = lambda code: (lambda x: code in json.dumps(x, ensure_ascii=False))
dump("STOCK_DAY_ALL", T + "/exchangeReport/STOCK_DAY_ALL", pick=has("2330"))
dump("BWIBBU_ALL", T + "/exchangeReport/BWIBBU_ALL", pick=has("2330"))
dump("t187ap05_L", T + "/opendata/t187ap05_L", pick=has("2330"))
dump("MI_INDEX", T + "/exchangeReport/MI_INDEX", pick=has("發行量加權股價指數"))
dump("notice", T + "/announcement/notice")
dump("punish", T + "/announcement/punish")
dump("tpex_close", P + "/tpex_mainboard_daily_close_quotes", pick=has("6488"))
dump("tpex_pe", P + "/tpex_mainboard_peratio_analysis", pick=has("6488"))
dump("tpex_rev", P + "/mopsfin_t187ap05_O", pick=has("6488"))
dump("tpex_3insti", P + "/tpex_3insti_daily_trading", pick=has("6488"))
dump("tpex_warning", P + "/tpex_trading_warning_information")
dump("tpex_disposal", P + "/tpex_disposal_information")
try:
    sw = requests.get(T + "/swagger.json", headers=UA, timeout=60).json()
    out.append("TWSE holiday paths|" + ",".join(p for p, v in sw["paths"].items() if "oliday" in p or "休市" in json.dumps(v, ensure_ascii=False)))
except Exception as e:
    out.append(f"swagger|ERR|{e}")
dump("TWSE holiday", T + "/holidaySchedule/holidaySchedule")
tok = os.environ.get("FINMIND_TOKEN", "")
h = {"Authorization": f"Bearer {tok}"} if tok else {}
start = (dt.date.today() - dt.timedelta(days=7)).isoformat()
dump("FinMind TAIEX", "https://api.finmindtrade.com/api/v4/data", {"dataset": "TaiwanStockPrice", "data_id": "TAIEX", "start_date": start}, h)
dump("FinMind inst 2330", "https://api.finmindtrade.com/api/v4/data", {"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "data_id": "2330", "start_date": start}, h)
dump("FinMind total inst", "https://api.finmindtrade.com/api/v4/data", {"dataset": "TaiwanStockTotalInstitutionalInvestors", "start_date": start}, h)
for i in range(0, len(out), 4):
    print("::notice title=schema " + str(i // 4) + "::" + "%0A".join(x.replace("\n", " ") for x in out[i:i + 4]))
