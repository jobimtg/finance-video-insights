"""資料來源（只用授權允許的公開資料）。
- 證交所、櫃買中心 OpenAPI：政府資料開放授權條款－第1版
- FinMind：只在執行時查詢，原始資料不寫入 repo
- FRED 官方 API：公有領域，須註明來源
金鑰只從環境變數讀取，不輸出。
"""
import os, time, datetime as dt
import requests

UA = {"User-Agent": "finance-video-insights (public data report)"}
TWSE = "https://openapi.twse.com.tw/v1"
TPEX = "https://www.tpex.org.tw/openapi/v1"
FINMIND = "https://api.finmindtrade.com/api/v4/data"


def get_json(url, params=None, headers=None, tries=4, timeout=60):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers={**UA, **(headers or {})}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # 連線中斷、逾時：等一下再試
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url.split('?')[0]} 讀取失敗：{type(last).__name__}")


def num(x):
    if x is None:
        return None
    s = str(x).replace(",", "").replace("+", "").strip()
    if s in ("", "-", "--", "N/A", "NA", "nan", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def roc_to_date(s):
    """1151016 或 115/10/16 → date"""
    s = str(s).strip().replace("/", "")
    if len(s) == 7 and s.isdigit():
        return dt.date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:7]))
    return None


# ---------- 證交所 ----------
def twse_close():
    rows = get_json(TWSE + "/exchangeReport/STOCK_DAY_ALL")
    return {r["Code"]: {"close": num(r.get("ClosingPrice")), "date": roc_to_date(r.get("Date"))} for r in rows}


def twse_valuation():
    rows = get_json(TWSE + "/exchangeReport/BWIBBU_ALL")
    return {r["Code"]: {"pe": num(r.get("PEratio")), "yield": num(r.get("DividendYield")), "date": roc_to_date(r.get("Date"))} for r in rows}


def revenue(url):
    rows = get_json(url)
    out = {}
    for r in rows:
        ym = str(r.get("資料年月", ""))
        out[r.get("公司代號")] = {"yoy": num(r.get("營業收入-去年同月增減(%)")),
                                 "month": int(ym[3:5]) if len(ym) == 5 else None}
    return out


def twse_revenue():
    return revenue(TWSE + "/opendata/t187ap05_L")


def twse_holidays():
    rows = get_json(TWSE + "/holidaySchedule/holidaySchedule")
    out = set()
    for r in rows:
        d = roc_to_date(r.get("Date"))
        name = r.get("Name", "") + r.get("Description", "")
        if d and "開始交易" not in name and "最後交易" not in name:
            out.add(d)
    return out


def twse_lists():
    rec = [r.get("Code") for r in get_json(TWSE + "/Announcement/BFZFZU_T") if r.get("Code")]
    att = [r.get("Code") for r in get_json(TWSE + "/announcement/notice") if r.get("Code")]
    dis = []
    for r in get_json(TWSE + "/announcement/punish"):
        if r.get("Code"):
            dis.append((r["Code"], r.get("DispositionPeriod", "")))
    return rec, att, dis


# ---------- 櫃買中心 ----------
def _code(r):
    return r.get("SecuritiesCompanyCode") or r.get("公司代號") or r.get("Code")


def tpex_close():
    rows = get_json(TPEX + "/tpex_mainboard_daily_close_quotes")
    out = {}
    for r in rows:
        close = None
        for k in ("Close", "ClosingPrice", "收盤"):
            if k in r:
                close = num(r[k]); break
        out[_code(r)] = {"close": close, "date": roc_to_date(r.get("Date"))}
    return out


def tpex_valuation():
    rows = get_json(TPEX + "/tpex_mainboard_peratio_analysis")
    return {_code(r): {"pe": num(r.get("PriceEarningRatio")), "yield": num(r.get("YieldRatio")), "date": roc_to_date(r.get("Date"))} for r in rows}


def tpex_revenue():
    return revenue(TPEX + "/mopsfin_t187ap05_O")


def tpex_institutional():
    """三大法人合計買賣超（張）"""
    rows = get_json(TPEX + "/tpex_3insti_daily_trading")
    out = {}
    for r in rows:
        total = None
        for k, v in r.items():
            kl = k.replace(" ", "").lower()
            if "total" in kl and "difference" in kl and not any(w in kl for w in ("foreign", "investment", "dealer", "securities")):
                total = num(v)
        out[_code(r)] = {"net": None if total is None else round(total / 1000), "date": roc_to_date(r.get("Date"))}
    return out


def tpex_lists():
    att = [_code(r) for r in get_json(TPEX + "/tpex_trading_warning_information") if _code(r)]
    dis = [(_code(r), r.get("DispositionPeriod", "")) for r in get_json(TPEX + "/tpex_disposal_information") if _code(r)]
    return att, dis


def in_disposal(period, day):
    parts = [p for p in period.replace("～", "~").split("~") if p.strip()]
    if len(parts) != 2:
        return False
    a, b = roc_to_date(parts[0]), roc_to_date(parts[1])
    return bool(a and b and a <= day <= b)


# ---------- FinMind（只在執行時查詢）----------
def _fm(dataset, start, data_id=None, end=None):
    tok = os.environ.get("FINMIND_TOKEN", "").strip()
    params = {"dataset": dataset, "start_date": start}
    if data_id:
        params["data_id"] = data_id
    if end:
        params["end_date"] = end
    d = get_json(FINMIND, params=params, headers={"Authorization": f"Bearer {tok}"} if tok else None)
    time.sleep(0.4)
    return d.get("data", [])


def fm_prices(code, start, end=None):
    return [{"date": dt.date.fromisoformat(r["date"]), "close": r["close"], "high": r["max"], "low": r["min"],
             "spread": r.get("spread")} for r in _fm("TaiwanStockPrice", start, code, end) if r.get("close")]


def fm_institutional(code, start):
    rows = _fm("TaiwanStockInstitutionalInvestorsBuySell", start, code)
    if not rows:
        return None, None
    last = max(r["date"] for r in rows)
    net = sum(r["buy"] - r["sell"] for r in rows if r["date"] == last)
    return round(net / 1000), dt.date.fromisoformat(last)


def fm_total_institutional(start):
    rows = _fm("TaiwanStockTotalInstitutionalInvestors", start)
    by = {}
    for r in rows:
        by.setdefault(r["date"], {})[r["name"]] = (r["buy"] - r["sell"]) / 1e8
    return by  # {date: {name: 億元}}


# ---------- FRED ----------
def fred_latest(series):
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        return None, None
    d = get_json("https://api.stlouisfed.org/fred/series/observations",
                 params={"series_id": series, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 10})
    for o in d.get("observations", []):
        v = num(o.get("value"))
        if v is not None:
            return v, dt.date.fromisoformat(o["date"])
    return None, None
