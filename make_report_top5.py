#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
주요 5개 대학(서울대·연세대·고려대·KAIST·포스텍) 2027학년도 vs 2026학년도 수시 경쟁률 비교 보고서
- 입력: docs/data.json (build.py 산출), data/final2026.json, data/prior_timeline.json(서울대 작년 모집단위 경쟁률)
- 출력: reports/top5_2027.html  (build.py 가 docs/ 로 복사해 배포)
- 사용: python make_report_top5.py
"""
import datetime as dt
import html
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "reports", "top5_2027.html")
NAMES = ["서울대학교", "연세대학교(서울)", "고려대학교(서울)", "한국과학기술원", "포항공과대학교"]
SHORT = {"서울대학교": "서울대", "연세대학교(서울)": "연세대(서울)", "고려대학교(서울)": "고려대(서울)", "한국과학기술원": "KAIST", "포항공과대학교": "포스텍"}

# 대학별 해설(수치는 표에서 자동 생성, 해설은 2026-09-10 확정치 기준으로 작성)
NARR = {
    "서울대학교": [
        "지역균형 4.60, 일반전형 7.98, 기회균형(사회통합) 10.24. 작년 최종은 모집단위 120개의 작년 경쟁률을 올해 모집인원으로 가중해 추정하면 지역균형 4.24→4.12, 일반전형 8.84→7.86으로 둘 다 소폭 내렸다.",
        "지역균형에서 수리과학부(2.57→5.14), 에너지자원공학과(3.4→5.8), 지구환경과학부(3.0→5.2) 등 자연계가 올랐고, 일반전형에서 종교학과(15.3→11.1), 화학부(9.85→6.33), 응용생물화학부(19.3→15.8), 사회교육과(13.2→9.5)가 내렸다.",
        "의학과는 일반 11.12·지역균형 7.28, 치의학과 8.00, 약학계열 일반 7.31·지역균형 9.91.",
    ],
    "연세대학교(서울)": [
        "지원자가 2,800명(8.3%) 줄었다. 학생부교과 추천형이 6.28→4.86으로 가장 크게 내렸고, 활동우수형 11.07→10.11, 국제형(국내고) 14.93→13.59도 하락했다.",
        "논술은 모집이 335→288명으로 줄어 경쟁률은 48.7→50.2로 올랐지만 지원자는 1,900명 줄었다. 논술 안에서 인문계는 급등(경영 82→100, 언론홍보 69→86, 정치외교 68→84, 심리 70→85), 자연계는 하락(약학 103→87, 수학 34→27, 지능형반도체 32→25).",
        "의예과는 추천형 6.0→4.2, 활동우수형 11.3→10.4, 기회균형 28.7→22.0으로 모든 전형에서 내렸고 치의예과 활동우수형도 12.3→8.8. 해외고·검정고시 국제형은 5.75→8.44로 올랐다.",
    ],
    "고려대학교(서울)": [
        "총 지원은 비슷하지만 구조가 바뀌었다. 논술이 71.9→79.9(지원 +2,900명)로 더 몰렸고, 학교추천 6.94→5.66, 학업우수 16.77→15.39, 계열적합 13.67→13.38로 학생부 전형은 모두 내렸다.",
        "논술 인문계 급등이 특히 크다(자유전공 87→114, 철학 88→113, 사회학 81→105, 경제 78→104, 미디어 75→99). 다문화 19.1→11.5, 재직자 14.3→9.1도 크게 내렸다.",
        "의과대학은 학교추천 12.9→8.5, 학업우수 28.3→25.1, 계열적합 25.0→23.9로 세 전형 모두 하락.",
    ],
    "한국과학기술원": [
        "다섯 대학 중 유일하게 뚜렷이 올랐다(지원 +20.1%). 창의도전은 모집이 200→270명으로 늘었는데도 9.45→10.09, 학교장추천 15.45→17.81, 일반 7.64→8.43, 특기자 7.9→9.57.",
        "반도체시스템인재는 모집 70→40명 축소로 경쟁률은 3.34→4.63이지만 지원자는 234→185명으로 줄었다.",
    ],
    "포항공과대학교": [
        "일반전형Ⅰ 8.27→8.64는 올랐고, 일반전형Ⅱ 13.04→11.27, 반도체공학 12.38→11.05는 내렸다.",
        "기회균형은 한 전형 20명(6.1)에서 세 전형 40명으로 나뉘어 합계 321명이 지원했다(통합전형 12.7, 저소득층 6.8, 지역인재 6.3).",
    ],
}
THEMES = [
    ("논술 쏠림 심화, 특히 인문계", "연세·고려 모두 논술 인문 학과가 15~27포인트 올랐다. 수능 최저 부담을 안고도 논술로 가는 흐름이 강해졌다."),
    ("교과 추천형 약세", "연세 추천형, 고려 학교추천이 나란히 1.3~1.4포인트 내렸다. 추천 인원 제한과 내신 부담으로 지원 자체가 줄었다."),
    ("의대 경쟁률 하락", "연세 의예과가 전 전형에서 내렸고 고려 의과대학도 세 전형 모두 하락, 서울대 의학과 일반 11.1도 높지 않다. 의대 정원 조정 이후 상위권 분산이 보인다."),
    ("과기원 선호 상승, 반도체 계약학과류 약세", "KAIST가 20% 늘었다. 반면 연세 IT융합·지능형반도체, 포스텍 반도체, KAIST 반도체는 지원자가 줄었다."),
]


def load(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return json.load(f)


def fmt(n):
    return "-" if n is None else ("{:,}".format(n) if isinstance(n, int) else "{:,.2f}".format(n))


def ratio(r):
    return "-" if r is None else "%.2f" % r


def delta(a, b):
    if a is None or b is None:
        return ""
    d = a - b
    cls = "up" if d > 0.05 else ("down" if d < -0.05 else "flat")
    return '<span class="d %s">%+.2f</span>' % (cls, d)


def esc(s):
    return html.escape(str(s if s is not None else ""))


def snu_estimate(u):
    """서울대: 엑셀의 모집단위별 작년 최종 경쟁률 × 올해 모집인원 → 유형별 작년 추정"""
    agg = {}
    for x in u["units"]:
        if x.get("detail"):
            continue
        tl = x.get("tl")
        if tl and tl["fin"][0] is not None and x["quota"]:
            a = agg.setdefault(x["type"], {"q": 0, "e": 0.0, "n": 0})
            a["q"] += x["quota"]
            a["e"] += tl["fin"][0] * x["quota"]
            a["n"] += 1
    return {k: {"quota": v["q"], "app": round(v["e"]), "ratio": round(v["e"] / v["q"], 2), "n": v["n"]} for k, v in agg.items()}


def type_rows(u, fin26):
    rows = []
    est = snu_estimate(u) if u["name"] == "서울대학교" else {}
    for t in u["types"]:
        f = t.get("fin") or {}
        if u["name"] == "서울대학교":
            e = est.get(t["name"])
            f = {"quota": None, "app": None, "ratio": e["ratio"], "est": e["n"]} if e else {}
        if u["name"] == "포항공과대학교" and t["name"].startswith("기회균형"):
            f = {}   # 2026 은 단일 기회균형전형(20명·122명·6.1)이라 개별 비교 불가 → 합계 행으로 표시
        rows.append((t, f))
    if u["name"] == "포항공과대학교":
        ks = [t for t in u["types"] if t["name"].startswith("기회균형")]
        q = sum(t["quota"] or 0 for t in ks)
        a = sum(t["app"] or 0 for t in ks)
        rows.append(({"name": "기회균형 3개 전형 합계", "quota": q, "app": a, "ratio": round(a / q, 2) if q else None}, {"quota": 20, "app": 122, "ratio": 6.1}))
    return rows


def unit_changes(u, top=6):
    rows = []
    for x in u["units"]:
        if x.get("detail"):
            continue
        fin = x.get("finRatio")
        if fin is None and x.get("tl"):
            fin = x["tl"]["fin"][0]
        if fin is None or x["ratio"] is None or not x["quota"] or x["quota"] < 3:
            continue
        rows.append((x["ratio"] - fin, x))
    rows.sort(key=lambda r: r[0])
    return rows[:top], rows[-top:][::-1]


def med_rows(u, fin26_units):
    keys = ("의예", "의학과", "의과대학", "치의", "약학", "수의")
    out = []
    for x in u["units"]:
        if x.get("detail") or not any(k in x["unit"] for k in keys):
            continue
        fin = x.get("finRatio")
        if fin is None and x.get("tl"):
            fin = x["tl"]["fin"][0]
        if fin is None and fin26_units:
            for y in fin26_units:
                if y["unit"] == x["unit"] and y["type"][:14] == x["type"][:14]:
                    fin = y["ratio"]
                    break
        out.append((x, fin))
    return out


def main():
    d = load("docs/data.json")
    fin26 = load("data/final2026.json")["universities"]
    unis = {u["name"]: u for u in d["universities"]}
    ids = {u["name"]: u["id"] for u in d["universities"]}
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y.%m.%d %H:%M")

    css = """
    :root{--navy:#1b3a6b;--navy-d:#12294d;--gold:#c8a232;--bg:#f3f5f9;--line:#e2e6ee;--muted:#6b7280;--up:#c43e00;--down:#1565c0}
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:"Pretendard","Noto Sans KR","Malgun Gothic",sans-serif;background:var(--bg);color:#1f2937;font-size:15px;line-height:1.6;word-break:keep-all}
    .wrap{max-width:1100px;margin:0 auto;padding:18px 20px 60px}
    header{background:linear-gradient(135deg,var(--navy-d),var(--navy));color:#fff;border-radius:14px;padding:26px 28px;margin-bottom:18px}
    header h1{font-size:26px;font-weight:800;letter-spacing:-.3px}
    header p{color:#cfd8e6;font-size:13.5px;margin-top:6px}
    .card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:16px}
    h2{font-size:19px;color:var(--navy);margin-bottom:10px;border-left:5px solid var(--gold);padding-left:10px}
    h3{font-size:15px;color:#334;margin:14px 0 6px}
    table{border-collapse:collapse;width:100%;font-size:13.5px}
    th,td{padding:7px 9px;border-bottom:1px solid #eef0f4;text-align:left;vertical-align:middle}
    th{background:#f4f6fa;font-weight:700;color:#334;white-space:nowrap}
    td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
    .tbl{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
    .d{font-weight:700;font-size:12.5px;padding:1px 6px;border-radius:5px;background:#eee;color:#666}
    .d.up{background:#ffe3d6;color:var(--up)} .d.down{background:#e3f2fd;color:var(--down)}
    .sum .big{font-size:22px;font-weight:900;color:var(--navy)}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
    ul.narr{margin:8px 0 0 18px}
    ul.narr li{margin-bottom:6px}
    .note{font-size:12.5px;color:var(--muted);margin-top:8px}
    .theme{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
    .theme div{background:#f7f8fb;border-radius:10px;padding:12px 14px}
    .theme b{display:block;color:var(--navy);margin-bottom:4px}
    footer{margin-top:24px;padding-top:12px;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted);line-height:1.7}
    @media print{.card{break-inside:avoid}}
    """

    parts = []
    parts.append('<header><h1>주요 5개 대학 2027학년도 수시모집 경쟁률 분석</h1><p>2026학년도 최종 경쟁률과 비교 · 서울대 · 연세대(서울) · 고려대(서울) · KAIST · 포스텍 · 작성 %s</p></header>' % now)

    # 요약표
    parts.append('<div class="card"><h2>전체 요약</h2><div class="tbl"><table><thead><tr><th>대학</th><th class="n">2027 지원</th><th class="n">모집</th><th class="n">경쟁률</th><th class="n">2026 지원</th><th class="n">모집</th><th class="n">경쟁률</th><th class="n">지원자 증감</th><th class="n">경쟁률 변화</th></tr></thead><tbody>')
    for n in NAMES:
        u = unis[n]
        t = u["total"] or {}
        f = u.get("finTotal") or {}
        if n == "서울대학교":
            est = snu_estimate(u)
            f = {}
            fnote = "유형별 추정만(아래)"
        else:
            fnote = ""
        chg = ""
        if t.get("app") and f.get("app"):
            chg = "%+.1f%%" % ((t["app"] - f["app"]) / f["app"] * 100)
        parts.append('<tr><td><b>%s</b>%s</td><td class="n">%s</td><td class="n">%s</td><td class="n"><b>%s</b></td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td></tr>' % (
            esc(SHORT[n]), (" <small style=\"color:#888\">%s</small>" % fnote) if fnote else "",
            fmt(t.get("app")), fmt(t.get("quota")), ratio(t.get("ratio")), fmt(f.get("app")), fmt(f.get("quota")), ratio(f.get("ratio")), chg, delta(t.get("ratio"), f.get("ratio"))))
    parts.append('</tbody></table></div><p class="note">2027은 각 대학이 접수 마감(9.9) 후 공개한 값(서울대는 최종 공지 PDF, 나머지는 진학어플라이·유웨이어플라이 경쟁률 페이지의 마감 후 수치). 2026은 같은 페이지의 작년 최종값. 서울대 2026은 대학 단위 총계 자료가 없어 모집단위별 작년 경쟁률을 올해 모집인원으로 가중한 추정치를 유형별 표에만 표시.</p></div>')

    # 흐름
    parts.append('<div class="card"><h2>관통하는 흐름</h2><div class="theme">' + "".join('<div><b>%s</b>%s</div>' % (esc(a), esc(b)) for a, b in THEMES) + '</div></div>')

    # 대학별
    for n in NAMES:
        u = unis[n]
        fu = fin26.get(ids[n], {}).get("units", [])
        parts.append('<div class="card"><h2>%s</h2>' % esc(SHORT[n]))
        parts.append('<ul class="narr">' + "".join("<li>%s</li>" % esc(s) for s in NARR[n]) + "</ul>")
        parts.append('<h3>전형별</h3><div class="tbl"><table><thead><tr><th>전형</th><th class="n">2027 모집</th><th class="n">지원</th><th class="n">경쟁률</th><th class="n">2026 모집</th><th class="n">지원</th><th class="n">경쟁률</th><th class="n">변화</th></tr></thead><tbody>')
        for t, f in type_rows(u, fin26):
            f26r = f.get("ratio")
            f26txt = ratio(f26r) + ((" <small style=\"color:#888\">추정·%d단위</small>" % f["est"]) if f.get("est") else "")
            parts.append('<tr><td>%s</td><td class="n">%s</td><td class="n">%s</td><td class="n"><b>%s</b></td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td></tr>' % (
                esc(t["name"]), fmt(t.get("quota")), fmt(t.get("app")), ratio(t.get("ratio")), fmt(f.get("quota")), fmt(f.get("app")), f26txt, delta(t.get("ratio"), f26r)))
        parts.append('</tbody></table></div>')
        down, up = unit_changes(u)
        if down or up:
            parts.append('<div class="grid">')
            for title, rows in (("경쟁률 상승 상위", up), ("경쟁률 하락 상위", down)):
                parts.append('<div><h3>%s (모집 3명 이상)</h3><div class="tbl"><table><thead><tr><th>전형</th><th>모집단위</th><th class="n">모집</th><th class="n">지원</th><th class="n">2027</th><th class="n">2026</th><th class="n">변화</th></tr></thead><tbody>' % title)
                for dlt, x in rows:
                    fin = x.get("finRatio")
                    if fin is None and x.get("tl"):
                        fin = x["tl"]["fin"][0]
                    parts.append('<tr><td>%s</td><td>%s</td><td class="n">%s</td><td class="n">%s</td><td class="n"><b>%s</b></td><td class="n">%s</td><td class="n">%s</td></tr>' % (
                        esc(x["type"][:18]), esc(x["unit"]), fmt(x["quota"]), fmt(x["app"]), ratio(x["ratio"]), ratio(fin), delta(x["ratio"], fin)))
                parts.append('</tbody></table></div></div>')
            parts.append('</div>')
        med = med_rows(u, fu)
        if med:
            parts.append('<h3>의·치·약·수의 계열</h3><div class="tbl"><table><thead><tr><th>전형</th><th>모집단위</th><th class="n">모집</th><th class="n">지원</th><th class="n">2027</th><th class="n">2026</th><th class="n">변화</th></tr></thead><tbody>')
            for x, fin in med:
                parts.append('<tr><td>%s</td><td>%s</td><td class="n">%s</td><td class="n">%s</td><td class="n"><b>%s</b></td><td class="n">%s</td><td class="n">%s</td></tr>' % (
                    esc(x["type"][:22]), esc(x["unit"]), fmt(x["quota"]), fmt(x["app"]), ratio(x["ratio"]), ratio(fin), delta(x["ratio"], fin)))
            parts.append('</tbody></table></div>')
        parts.append('</div>')

    parts.append('<footer><b>제작</b> 충청남도교육청진로융합교육원 교육연구사 정재연<br><b>출처</b> 각 대학 입학처 2027학년도 수시모집 경쟁률 공개 자료(서울대 입학본부 접수현황 최종 공지, 진학어플라이·유웨이어플라이 경쟁률 페이지) 및 2026학년도 최종 경쟁률. 진학 상담 참고용이며 합격 가능성을 판정하지 않습니다. 확정 수치는 각 대학 입학처 공식 발표를 따릅니다.</footer>')

    doc = '<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>주요 5개 대학 2027 수시 경쟁률 분석</title><style>%s</style></head><body><div class="wrap">%s</div></body></html>' % (css, "".join(parts))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    print("저장: %s (%.0f KB)" % (os.path.relpath(OUT, ROOT), len(doc.encode("utf-8")) / 1024))


if __name__ == "__main__":
    main()
