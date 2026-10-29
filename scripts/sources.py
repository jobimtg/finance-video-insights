"""資料來源（只用授權允許的公開資料）。
- 證交所、櫃買中心 OpenAPI：政府資料開放授權條款－第1版
- FinMind：只在執行時查詢，原始資料不寫入 repo
- FRED 官方 API：公有領域，須註明來源
金鑰只從環境變數讀取，不輸出。
"""
import os, re, time, datetime as dt
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


ADJUSTED = []   # 本次產出中偵測到分割／減資並調整過歷史價格的代號


def fm_prices(code, start, end=None):
    px = [{"date": dt.date.fromisoformat(r["date"]), "close": r["close"], "high": r["max"], "low": r["min"],
           "open": r.get("open"), "spread": r.get("spread")} for r in _fm("TaiwanStockPrice", start, code, end) if r.get("close")]
    # 台股單日漲跌幅上限 10%：隔日價格跳動超過 ±40% 視為股票分割、減資等，將之前的價格依比例調整，
    # 避免 52 週高低、均線與區間被未調整的舊價格扭曲（2026-10-18 加入，例：0052 一拆七）。
    # 2026-10-28 經使用者同意（選項 A）：槓桿／反向 ETF（代號 00 開頭、L 或 R 結尾，例 00631L、00632R）
    # 沒有單日漲跌幅限制且淨值會大幅變動，不做分割偵測，避免誤判成多次分割、出現負倍數。
    if re.fullmatch(r"00\d{3,4}[LR]", code):
        return px
    for i in range(len(px) - 1, 0, -1):
        prev = px[i]["close"] - (px[i]["spread"] or 0) if px[i].get("spread") is not None else px[i - 1]["close"]
        ratio = prev / px[i - 1]["close"] if px[i - 1]["close"] else 1
        if ratio < 0.6 or ratio > 1.67:
            for p in px[:i]:
                for k in ("close", "high", "low", "open"):
                    if p.get(k) is not None:
                        p[k] = round(p[k] * ratio, 4)
            ADJUSTED.append(f"{code}（{px[i]['date']} 前價格乘以 {ratio:.4f}）")
    return px


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
TREASURY_COL = {"DGS10": "10 Yr", "DGS20": "20 Yr", "DGS30": "30 Yr"}
_FRED_CACHE = {}


def treasury_latest(series):
    """美債備援：美國財政部每日公債殖利率 CSV（skill 已定案的備援來源）"""
    import csv, io
    y = dt.date.today().year
    url = (f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all"
           f"?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")
    r = requests.get(url, headers=UA, timeout=60); r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.text)))
    col = TREASURY_COL[series]
    best = None
    for row in rows:
        v = num(row.get(col)); d = dt.datetime.strptime(row["Date"], "%m/%d/%Y").date()
        if v is not None and (best is None or d > best[1]):
            best = (v, d)
    return best or (None, None)


def fred_latest(series):
    """2026-10-21：FRED 讀取失敗時不讓整份報告失敗；美債改用財政部備援，其餘回傳查無並記錄。"""
    if series in _FRED_CACHE:
        return _FRED_CACHE[series]
    key = os.environ.get("FRED_API_KEY", "").strip()
    res = (None, None)
    try:
        if not key:
            raise RuntimeError("沒有 FRED_API_KEY")
        d = get_json("https://api.stlouisfed.org/fred/series/observations",
                     params={"series_id": series, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 10})
        for o in d.get("observations", []):
            v = num(o.get("value"))
            if v is not None:
                res = (v, dt.date.fromisoformat(o["date"])); break
    except Exception as e:
        FRED_FAIL.append(f"{series}（{type(e).__name__}）")
        if series in TREASURY_COL:
            try:
                res = treasury_latest(series); FRED_FALLBACK.append(series)
            except Exception as e2:
                FRED_FAIL.append(f"{series} 財政部備援（{type(e2).__name__}）")
    _FRED_CACHE[series] = res
    return res


FRED_FAIL, FRED_FALLBACK = [], []
