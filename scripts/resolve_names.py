"""Agent 2 輔助：用證交所、櫃買中心公開名單核對個股名稱、代號與市場。
用法：python resolve_names.py "名稱:猜測代號" ...（猜測代號可空白）。結果以 ::notice 輸出。
"""
import sys
import sources as S


def main(items):
    tw = {r["Code"]: r.get("Name", "").strip() for r in S.get_json(S.TWSE + "/exchangeReport/STOCK_DAY_ALL")}
    tp = {}
    for r in S.get_json(S.TPEX + "/tpex_mainboard_daily_close_quotes"):
        tp[S._code(r)] = (r.get("CompanyName") or r.get("Name") or "").strip()
    en = {}
    try:
        for r in S.get_json(S.TWSE + "/opendata/t187ap03_L"):
            en[r.get("公司代號")] = (r.get("英文簡稱") or "").strip()
    except Exception as e:
        print("英文簡稱名單讀取失敗", e)
    try:
        for r in S.get_json(S.TPEX + "/mopsfin_t187ap03_O"):
            c = r.get("SecuritiesCompanyCode") or r.get("公司代號")
            en[c] = (r.get("SymbolEnglishAbbreviation") or r.get("英文簡稱") or r.get("CompanyEnglishAbbreviation") or "").strip()
    except Exception as e:
        print("櫃買英文簡稱讀取失敗", e)
    lines = []
    for it in items:
        name, _, guess = it.partition(":")
        hits = [(c, "TWSE", n) for c, n in tw.items() if n == name] + [(c, "TPEx", n) for c, n in tp.items() if n == name]
        if not hits:
            hits = [(c, "TWSE" if c in tw else "TPEx", tw.get(c) or tp.get(c)) for c, n in en.items() if name.upper() in n.upper()]
        if not hits:
            hits = [(c, "TWSE", n) for c, n in tw.items() if name in n] + [(c, "TPEx", n) for c, n in tp.items() if name in n]
        g = f"（猜 {guess}）" if guess else ""
        ok = "OK" if guess and any(h[0] == guess for h in hits) and len(hits) == 1 else "CHECK"
        lines.append(f"{ok} {name}{g} → " + ("、".join(f"{c} {m} {n}" for c, m, n in hits[:5]) or "找不到"))
    bad = [l for l in lines if not l.startswith("OK")]
    print("::notice title=名稱核對（需確認 %d 筆）::" % len(bad) + "%0A".join(bad or ["全部一致"]))
    print("::notice title=名稱核對（一致）::" + "%0A".join(l for l in lines if l.startswith("OK"))[:3900])


if __name__ == "__main__":
    main(sys.argv[1:])
