"""LINE Flex 卡片（2026-10-17 定案：選項 B 白底摘要卡，mega）"""
from collections import Counter

UP, DN, NEU, NAVY = "#d64545", "#1a9e5c", "#8a8984", "#1f3a5f"


def c(x):
    return NEU if not x else (UP if x > 0 else DN)


def short(t, n=28):
    t = t.split("：", 1)[-1]
    return t if len(t) <= n else t[:n - 1] + "…"


def build(R, pdf_url, air_short_tw):
    ep = R["episode"]
    core = [s for s in R["stocks"] if s["stance"] != "背景" and s["since_video_pct"] is not None]
    mv = sorted(core, key=lambda s: -s["since_video_pct"])
    vc = Counter(s["verify"] for s in core)

    def kpi(k):
        return {"type": "box", "layout": "vertical", "flex": 1, "backgroundColor": "#f3f2ee", "cornerRadius": "8px", "paddingAll": "6px",
                "contents": [{"type": "text", "text": k["label"].split(" ")[0], "size": "xxs", "color": "#666666"},
                             {"type": "text", "text": f"{k['close']:,.0f}", "size": "sm", "weight": "bold"},
                             {"type": "text", "text": f"{k['chg']:+,.0f}", "size": "xxs", "weight": "bold", "color": c(k["chg"])}]}

    def mrow(s):
        return {"type": "box", "layout": "horizontal", "contents": [
            {"type": "text", "text": f"{s['name']} {s['code']}", "size": "xs", "flex": 5, "wrap": False},
            {"type": "text", "text": f"{s['since_video_pct']:+.1f}%", "size": "xs", "weight": "bold", "align": "end", "flex": 3, "color": c(s["since_video_pct"])}]}

    sep = {"type": "separator", "margin": "md"}
    body = [
        {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [kpi(k) for k in R["taiex"]]},
        sep,
        {"type": "text", "text": "三個重點", "size": "sm", "weight": "bold", "color": NAVY, "margin": "md"},
        *[{"type": "text", "text": f"{i}. {short(h)}", "size": "xs", "wrap": True, "color": "#333333"} for i, h in enumerate(R["highlights"], 1)],
        sep,
        {"type": "box", "layout": "horizontal", "spacing": "lg", "margin": "md", "contents": [
            {"type": "box", "layout": "vertical", "flex": 1, "contents": [{"type": "text", "text": "漲幅前 3", "size": "xxs", "weight": "bold", "color": UP}, *[mrow(s) for s in mv[:3]]]},
            {"type": "box", "layout": "vertical", "flex": 1, "contents": [{"type": "text", "text": "跌幅前 3", "size": "xxs", "weight": "bold", "color": DN}, *[mrow(s) for s in mv[-3:][::-1]]]}]},
        sep,
        {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
            {"type": "text", "text": "2 日驗證", "size": "xxs", "color": "#555555"},
            {"type": "text", "text": f"一致 {vc.get('方向一致', 0)}｜相反 {vc.get('方向相反', 0)}｜觀察 {vc.get('待觀察', 0)}", "size": "xxs", "color": "#555555", "align": "end"}]},
    ]
    A = R.get("alerts")
    if A and A.get("lists"):
        codes = {s["code"] for s in R["stocks"] if s["stance"] != "背景"}
        n = {k: len([x for x in A["lists"].get(k, []) if x in codes]) for k in ("異常推介", "注意股", "處置股")}
        if any(n.values()):
            body.append({"type": "text", "text": f"主管機關名單：異常推介 {n['異常推介']}、注意 {n['注意股']}、處置 {n['處置股']}", "size": "xxs", "color": "#b02a2a", "margin": "sm"})
    latest_k = R["taiex"][-1]
    bubble = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "backgroundColor": NAVY, "paddingAll": "14px", "contents": [
            {"type": "text", "text": f"錢線百分百 {ep['video_date_short']} 個股統整", "color": "#ffffff", "weight": "bold", "size": "md"},
            {"type": "text", "text": f"台灣 {air_short_tw} 21:00 播出｜數據至 {ep['latest_date_short']} 收盤", "color": "#dfe6ef", "size": "xxs"}]},
        "body": {"type": "box", "layout": "vertical", "spacing": "xs", "paddingAll": "14px", "contents": body},
        "footer": {"type": "box", "layout": "vertical", "paddingAll": "12px", "contents": [
            {"type": "button", "style": "primary", "color": NAVY, "height": "sm",
             "action": {"type": "uri", "label": "開啟完整 PDF", "uri": pdf_url}}]},
    }
    alt = f"錢線百分百 {ep['video_date_short']} 個股統整｜加權 {latest_k['close']:,.0f} {latest_k['chg']:+,.0f}"
    return {"type": "flex", "altText": alt, "contents": bubble}
