"""Agent 4 自動部分：用獨立寫法重新抓證交所／櫃買 OpenAPI，隨機抽檔比對 report.json 的收盤、本益比、殖利率、營收年增。
不共用 sources.py 的解析程式，避免同一個錯誤被重複使用。用法：python independent_check.py 20261013 [抽樣數]
"""
import datetime as dt, json, os, random, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
H = {"User-Agent": "Mozilla/5.0"}


def get(u):
    for _ in range(4):
        try:
            r = requests.get(u, headers=H, timeout=60); r.raise_for_status(); return r.json()
        except Exception as e:
            err = e
    raise err


def f(x):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return None


def roc(x):
    """1151020 → 2026-10-20（獨立寫法）"""
    x = str(x or "").replace("/", "").strip()
    return f"{int(x[:3]) + 1911}-{x[3:5]}-{x[5:7]}" if len(x) == 7 and x.isdigit() else None


def fm_close(code, day):
    """OpenAPI 日期和報告不同時（報告依方案 C 改用較新的 FinMind），直接向 FinMind 重抓該日收盤。"""
    tok = os.environ.get("FINMIND_TOKEN", "").strip()
    r = requests.get("https://api.finmindtrade.com/api/v4/data", timeout=60,
                     params={"dataset": "TaiwanStockPrice", "data_id": code, "start_date": day, "end_date": day},
                     headers={**H, **({"Authorization": f"Bearer {tok}"} if tok else {})})
    r.raise_for_status()
    d = [x for x in r.json().get("data", []) if x.get("date") == day]
    return f(d[0]["close"]) if d else None


def pick(r, *keys):
    for k in keys:
        if k in r and r[k] not in ("", None):
            return r[k]
    for k in r:   # 欄位名稱不確定時，用關鍵字找
        if any(s in k for s in keys if s.startswith("~")):
            return r[k]
    return None


def main(ep, n=12):
    R = json.loads((ROOT / "drafts" / ep / "report.json").read_text(encoding="utf-8"))
    core = [s for s in R["stocks"] if s["stance"] != "背景"]
    random.seed(ep); sample = random.sample(core, min(n, len(core)))
    tw = {r["Code"]: r for r in get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL")}
    twv = {r["Code"]: r for r in get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL")}
    twr = {r["公司代號"]: r for r in get("https://openapi.twse.com.tw/v1/opendata/t187ap05_L")}
    tp = {r["SecuritiesCompanyCode"]: r for r in get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes")}
    tpv = {r["SecuritiesCompanyCode"]: r for r in get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis")}
    tpr = {r.get("公司代號") or r.get("SecuritiesCompanyCode"): r for r in get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O")}
    ok, bad, skip, src_note = 0, [], [], []
    for s in sample:
        c, twse = s["code"], s["market"] == "TWSE"
        q = (tw if twse else tp).get(c, {}); v = (twv if twse else tpv).get(c, {}); rv = (twr if twse else tpr).get(c, {})
        close = f(q.get("ClosingPrice") if twse else q.get("Close"))
        qd, ld = roc(q.get("Date")), s.get("latest_date")
        if ld and qd and qd != ld:   # 2026-10-20 方案 C：OpenAPI 尚未更新時，收盤改向 FinMind 重抓同一天
            close = fm_close(c, ld); src_note.append(f"{c} 收盤改核 FinMind {ld}（OpenAPI 為 {qd}）")
        pe = f(v.get("PEratio") if twse else (v.get("PriceEarningRatio") or v.get("PERatio")))
        yl = f(v.get("DividendYield") if twse else (v.get("YieldRatio") or v.get("DividendYield")))
        yoy = f(next((rv[k] for k in rv if "去年同月增減" in k), None))
        for name, mine, got, tol in (("收盤", s["latest"], close, 0.001), ("本益比", s["pe"], pe, 0.02),
                                     ("殖利率", s["yield"], yl, 0.02), ("營收年增", s["rev_yoy"], yoy, 0.1)):
            if s["is_etf"] and name != "收盤":
                continue
            if got is None and mine is None:
                ok += 1; continue
            if got is None or mine is None:
                skip.append(f"{c}{s['name']} {name}：報告 {mine}／重抓 {got}"); continue
            if abs(got - mine) <= tol * max(1, abs(got)):
                ok += 1
            else:
                bad.append(f"{c}{s['name']} {name}：報告 {mine}／重抓 {got}")
    msg = [f"抽 {len(sample)} 檔，一致 {ok} 項、不一致 {len(bad)} 項、無法核對 {len(skip)} 項"] + [f"不一致：{x}" for x in bad] + [f"無法核對：{x}" for x in skip] + ([f"備註：{len(src_note)} 檔收盤改核 FinMind（OpenAPI 尚未更新）"] if src_note else [])
    print(f"::notice title=Agent 4 獨立重抓 {ep}（{'通過' if not bad else '未通過'}）::" + "%0A".join(msg))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 12))
