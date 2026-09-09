#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
2027 수시 경쟁률 상황판 빌드
- universities.json + data/latest.json + data/history.json + data/final2026.json(있으면)
  → template.html 에 JSON 을 심어 2027susi-ratio.html 단일 파일 생성
- 사용: python build.py   (수집 후 실행)
"""
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")               # GitHub Pages 배포 폴더 (index.html + data.json)
OUT_EMBED = os.path.join(ROOT, "2027susi-ratio.html")   # 오프라인용 단일 파일(--embed)
REGION_ORDER = ["충남", "대전", "세종", "충북", "서울", "경기", "인천", "강원", "대구", "경북", "부산", "울산", "경남", "광주", "전남", "전북", "제주"]


def load(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def norm(s):
    """전형명·모집단위명 1차 정규화: 괄호종류 통일, 비율 설명 괄호 제거, 공백·기호 제거"""
    s = str(s or "")
    s = re.sub(r"\[[^\]]*(?:%|점|단계|없음|반영)[^\]]*\]", "", s)   # [학생부(교과) 70% + 면접 30%] 류 설명 제거
    s = s.replace("[", "(").replace("]", ")").replace("【", "(").replace("】", ")")
    s = re.sub(r"\([^()]*(?:%|점|단계|없음|반영)[^()]*\)", "", s)   # (교과 100%) 류 설명 제거
    s = re.sub(r"\s+[-–:]\s+.*(?:%|단계).*$", "", s)                  # ' - 교과70% + 면접30%' 류 꼬리 제거
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[·ㆍ\-–_/,.*※:]", "", s)
    s = s.replace("(정원내)", "").replace("(정원외)", "")
    s = s.replace("전형", "")
    return s.lower()


PREFIXES = ("학생부교과면접", "학생부교과", "학생부종합", "실기실적위주", "실기실적", "실기위주", "실기", "논술위주", "논술",
            "예체능계열", "학생부", "정원내", "정원외", "모집", "일괄합산", "단계별")


def strip_prefixes(k):
    changed = True
    while changed:
        changed = False
        for p in PREFIXES:
            if k.startswith(p) and len(k) > len(p):
                k = k[len(p):]
                changed = True
    return k


def norm2(s):
    """2차 정규화: 유형 접두어·괄호·수능최저 문구 제거(느슨한 매칭용).
    '학생부교과(지역균형)' 처럼 유형(이름) 꼴이면 괄호 안 이름을 취한다."""
    k = norm(s)
    k = k.replace("수능최저없음", "").replace("면접없음", "").replace("경쟁률현황", "")
    k = strip_prefixes(k)
    m = re.fullmatch(r"\(([^()]+)\)(.*)", k)
    if m:                                   # 유형(이름)꼬리 → 이름+꼬리
        k = m.group(1) + m.group(2)
    else:
        k = re.sub(r"\([^()]*\)", "", k)
    k = strip_prefixes(k)
    return k


def make_index(names):
    l1, l2 = {}, {}
    for n in names:
        l1.setdefault(norm(n), n)
        l2.setdefault(norm2(n), n)
    return l1, l2


def match_name(name, index):
    import difflib
    l1, l2 = index
    k1, k2 = norm(name), norm2(name)
    if k1 in l1:
        return l1[k1]
    if k2 in l2:
        return l2[k2]
    if k2:
        cands = [v for k, v in l2.items() if k and (k in k2 or k2 in k)]
        if len(set(cands)) == 1:
            return cands[0]
        best = difflib.get_close_matches(k2, [k for k in l2 if k], n=1, cutoff=0.7)
        if best:
            return l2[best[0]]
    return None


def category(type_name):
    n = str(type_name or "")
    if "논술" in n:
        return "논술"
    if any(k in n for k in ("실기", "특기", "실적")):
        return "실기·특기"
    if any(k in n for k in ("종합", "학종", "서류", "면접")):
        return "학생부종합"
    if any(k in n for k in ("교과", "학생부우수", "일반", "지역인재", "지역학생", "추천")):
        return "학생부교과"
    return "기타"


def norm_heading(s):
    s = str(s or "")
    s = re.split(r"경쟁률\s*현황", s)[0] if re.search(r"\S\s*경쟁률\s*현황", s) else re.sub(r"경쟁률\s*현황", " ", s)
    s = re.sub(r"^[\s\-–·•]+", "", s)
    s = re.sub(r"^모집\s+", "", s)
    s = re.sub(r"\([^)]*(?:죽전|천안|캠퍼스)[^)]*\)", "", s)
    return s


def map_unit_types(item):
    """모집단위 표의 전형 제목을 전형별 표의 전형명에 연결한다(표기 차이 흡수)"""
    types = item.get("types", [])
    if not types:
        return
    idx = make_index([t["name"] for t in types])
    cache = {}
    for u in item.get("units", []):
        raw = u["type"]
        if raw not in cache:
            cache[raw] = match_name(norm_heading(raw), idx)
        hit = cache[raw]
        if hit and hit != raw:
            u["typeRaw"] = raw
            u["type"] = hit


def attach_final(cur, fin):
    """현재 수집분(cur)의 전형·모집단위에 작년 최종(fin) 수치를 붙인다"""
    if not (fin and fin.get("ok")):
        return
    ftypes = {t["name"]: t for t in fin.get("types", [])}
    fidx = make_index(list(ftypes.keys()))
    tmap = {}   # 27 전형명 → 26 전형명
    for t in cur.get("types", []):
        hit = match_name(t["name"], fidx)
        if hit:
            tmap[t["name"]] = hit
            f = ftypes[hit]
            t["fin"] = {"quota": f.get("quota"), "app": f.get("app"), "ratio": f.get("ratio"), "name": hit}
    fu_exact, fu_unit = {}, {}
    for u in fin.get("units", []):
        fu_exact.setdefault((u["type"], norm(u["unit"])), u)
        fu_unit.setdefault(norm(u["unit"]), []).append(u)
    for u in cur.get("units", []):
        f = None
        ft = tmap.get(u["type"])
        if ft:
            f = fu_exact.get((ft, norm(u["unit"])))
        if not f:
            cands = fu_unit.get(norm(u["unit"]), [])
            same = [c for c in cands if category(c["type"]) == category(u["type"]) and (c.get("group") or "정원내") == (u.get("group") or "정원내")]
            if len(same) == 1:
                f = same[0]
        if f:
            u["finRatio"] = f.get("ratio")
            u["finApp"] = f.get("app")
    ft = fin.get("total")
    if ft:
        cur["finTotal"] = {"quota": ft.get("quota"), "app": ft.get("app"), "ratio": ft.get("ratio")}


# ---------------------------------------------------------------- 엑셀(과거 시점별 경쟁률) 결합

def ubase(name):
    """대학명 → (기본키, 캠퍼스토큰)  예: '고려대학교(세종)' → ('고려대','세종'), '서울과기대' → ('서울과기대','')"""
    name = str(name or "").strip()
    m = re.search(r"\((.*?)\)", name)
    campus = m.group(1) if m else ""
    base = re.sub(r"\(.*?\)", "", name)
    for a, b in (("대학교", "대"), ("학교", ""), ("여자대", "여대"), ("과학기술대", "과기대"), ("외국어대", "외대"),
                 ("기술교육대", "기술교대"), ("교육대", "교대"), ("국립", ""), (" ", "")):
        base = base.replace(a, b)
    return base, campus.replace(" ", "")


CAMPUS_ALIAS = {"국제": "용인", "글로벌": "용인", "메디컬": "인천", "다빈치": "안성", "죽전": "죽전", "강릉원주": "강릉원주"}


def build_univ_alias(unis, excel_names):
    """엑셀 대학명 → 우리 대학 id"""
    by_base = {}
    for u in unis:
        b, c = ubase(u["name"])
        by_base.setdefault(b, []).append((u, c))
    out = {}
    for name in excel_names:
        b, c = ubase(name)
        cands = by_base.get(b) or []
        if not cands:
            continue
        pick = None
        if len(cands) == 1:
            pick = cands[0][0]
        elif c:
            tok = CAMPUS_ALIAS.get(c, c)
            for u, uc in cands:
                if tok in uc or c in uc:
                    pick = u
                    break
        if pick is None:
            for u, uc in cands:
                if not uc or "서울" in uc:
                    pick = u
                    break
        out[name] = (pick or cands[0][0])["id"]
    return out


def attach_timeline(out_unis, excel_rows):
    """엑셀 시점별 경쟁률(2026·2025 D-3~최종, 3개년 최종)을 모집단위에 붙이고, 못 붙인 행은 참고용 목록으로 반환"""
    alias = build_univ_alias(out_unis, {r["univ"] for r in excel_rows})
    by_id = {u["id"]: u for u in out_unis}
    ref = []
    stats = {"rows": len(excel_rows), "univ_mapped": 0, "attached": 0}
    grouped = {}
    for r in excel_rows:
        grouped.setdefault(r["univ"], []).append(r)
    for exname, rows in grouped.items():
        uid = alias.get(exname)
        u = by_id.get(uid) if uid else None
        if u:
            stats["univ_mapped"] += len(rows)
        live = bool(u and u.get("ok") and u.get("units"))
        idx = make_index([t["name"] for t in u["types"]]) if live else None
        exact, by_unit = {}, {}
        if live:
            for x in u["units"]:
                exact.setdefault((x["type"], norm(x["unit"])), x)
                by_unit.setdefault(norm(x["unit"]), []).append(x)
        for r in rows:
            tl = {"t26": r["t26"], "t25": r["t25"], "j26": r["jump26"], "j25": r["jump25"], "fin": r["fin"], "q27": r["quota27"]}
            target = None
            if live:
                t = match_name(r["type"], idx)
                if t:
                    target = exact.get((t, norm(r["unit"])))
                if target is None:
                    cands = [x for x in by_unit.get(norm(r["unit"]), []) if x.get("cat", "").startswith(r["cat"][:2]) and (x.get("group") or "정원내") == "정원내"]
                    if len(cands) == 1:
                        target = cands[0]
            if target is not None and "tl" not in target:
                target["tl"] = tl
                stats["attached"] += 1
            else:
                ref.append({"u": u["name"] if u else exname, "uid": uid, "r": r["region"], "c": r["cat"], "t": r["type"], "n": r["unit"], "tl": tl})
    return ref, stats


def main():
    unis = load(os.path.join(ROOT, "universities.json"), [])
    latest = load(os.path.join(DATA, "latest.json"), {})
    hist = load(os.path.join(DATA, "history.json"), {})
    fin26 = load(os.path.join(DATA, "final2026.json"), {}).get("universities", {})
    fin25 = load(os.path.join(DATA, "final2025.json"), {}).get("universities", {})
    lu = latest.get("universities", {})

    out_unis = []
    for u in unis:
        rec = lu.get(u["id"], {})
        item = {
            "id": u["id"], "name": u["name"], "region": u["region"], "founder": u["founder"],
            "uniType": u.get("uniType"), "campus": u.get("campus"),
            "uniUrl": u.get("uniUrl"), "admissionUrl": u.get("admissionUrl"),
            "deadline": u.get("deadline"), "links": u.get("ratio", {}),
            "ok": bool(rec.get("ok")), "error": rec.get("error"),
            "asOf": rec.get("asOf"), "prevAsOf": rec.get("prevAsOf"),
            "stale": bool(rec.get("stale")), "staleError": rec.get("staleError"), "staleSince": rec.get("staleSince"),
            "source": rec.get("source"), "final": bool(rec.get("final")),
            "total": rec.get("total"), "types": rec.get("types", []), "units": rec.get("units", []),
            "history": [{"t": h["t"], "app": h["app"], "ratio": h["ratio"]} for h in hist.get(u["id"], [])],
        }
        map_unit_types(item)
        f26 = fin26.get(u["id"])
        if f26 and f26.get("ok"):
            map_unit_types(f26)
        for t in item["types"]:
            t["cat"] = category(t["name"])
        for x in item["units"]:
            x["cat"] = category(x["type"])
        attach_final(item, f26)
        f25 = fin25.get(u["id"])
        if f25 and f25.get("ok") and f25.get("total"):
            item["fin25Total"] = f25["total"]
        # 작년 최종 전체 요약(수집 실패 대학도 작년 수치는 보여줌)
        f26 = fin26.get(u["id"])
        if f26 and f26.get("ok") and f26.get("total") and "finTotal" not in item:
            item["finTotal"] = f26["total"]
        out_unis.append(item)

    # 엑셀(과거 시점별 경쟁률) 결합
    excel_rows = load(os.path.join(DATA, "prior_timeline.json"), [])
    ref, tl_stats = attach_timeline(out_unis, excel_rows) if excel_rows else ([], {})
    if excel_rows:
        print("시점별 과거자료: %d행 중 대학 매칭 %d, 모집단위 결합 %d, 참고용 %d" % (
            tl_stats["rows"], tl_stats["univ_mapped"], tl_stats["attached"], len(ref)))

    regions = [r for r in REGION_ORDER if any(u["region"] == r for u in out_unis)]
    regions += sorted({u["region"] for u in out_unis} - set(regions))
    payload = {
        "builtAt": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%dT%H:%M"),
        "collectedAt": latest.get("collectedAt"),
        "year": latest.get("year", 2027),
        "regions": regions,
        "universities": out_unis,
        "ref": ref,
        "tlStats": tl_stats,
    }
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    with open(os.path.join(ROOT, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    if "/*__DATA__*/null" not in tpl:
        raise SystemExit("template.html 에 /*__DATA__*/null 자리표시자가 없습니다")

    # 1) 웹 배포용: docs/index.html (데이터는 data.json 을 fetch) + docs/data.json + 상태 사본
    os.makedirs(os.path.join(DOCS, "state"), exist_ok=True)
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(tpl)
    with open(os.path.join(DOCS, "data.json"), "w", encoding="utf-8") as f:
        f.write(js)
    for name, obj in (("latest.json", latest), ("history.json", hist)):
        with open(os.path.join(DOCS, "state", name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    ok = sum(1 for x in out_unis if x["ok"])
    units = sum(len(x["units"]) for x in out_unis)
    print("빌드 완료: docs/index.html + docs/data.json (%.1f KB) — 대학 %d/%d 수집, 모집단위 %d건, 수집시각 %s" % (
        len(js.encode("utf-8")) / 1024, ok, len(out_unis), units, payload["collectedAt"]))

    # 2) 오프라인용 단일 파일(--embed)
    if "--embed" in sys.argv:
        html = tpl.replace("/*__DATA__*/null", js.replace("</", "<\\/"), 1)
        with open(OUT_EMBED, "w", encoding="utf-8") as f:
            f.write(html)
        print("임베드 완료: %s (%.1f KB)" % (os.path.basename(OUT_EMBED), len(html.encode("utf-8")) / 1024))


if __name__ == "__main__":
    main()
