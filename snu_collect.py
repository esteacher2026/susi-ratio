#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
서울대학교 수시 접수현황 PDF 수집기
- 서울대 입학본부 공지사항에서 "수시모집 지원서 접수현황(MM/DD HH:MM기준)" 최신 글의 첨부 PDF를 받아
  숫자 열을 좌표로 읽고, 행 순서 템플릿(단과대학·모집단위)에 대응시켜 data/extra/서울대학교.json 을 만든다.
- PDF 의 한글이 폰트 문제로 추출되지 않아 템플릿 방식을 쓴다. 소계·총계 검증으로 어긋남을 잡는다.
- 사용: python snu_collect.py [--pdf 파일경로]   (파일을 주면 다운로드 생략)
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "data", "extra", "서울대학교.json")
CACHE = os.path.join(ROOT, "data", "snu_pdf")
NOTICE = "https://admission.snu.ac.kr/undergraduate/notice"
NAME = "서울대학교"
FINAL_ASOF = "2026-09-09T18:00"   # 접수 마감(최종 공지의 기준 시각)

# ------------------------------------------------------------ 행 템플릿 (u=모집단위, s=소계, t=총계)
S1 = [  # Ⅰ. 지역균형전형 | 일반전형  (1~3쪽)
    ("학부대학", "자유전공학부", "u"), ("인문대학", "인문계열", "u"), ("인문대학", "국어국문학과", "u"), ("인문대학", "중어중문학과", "u"),
    ("인문대학", "영어영문학과", "u"), ("인문대학", "불어불문학과", "u"), ("인문대학", "독어독문학과", "u"), ("인문대학", "노어노문학과", "u"),
    ("인문대학", "서어서문학과", "u"), ("인문대학", "언어학과", "u"), ("인문대학", "아시아언어문명학부", "u"), ("인문대학", "역사학부", "u"),
    ("인문대학", "고고미술사학과", "u"), ("인문대학", "철학과", "u"), ("인문대학", "종교학과", "u"), ("인문대학", "미학과", "u"), ("인문대학", "소계", "s"),
    ("사회과학대학", "정치외교학부", "u"), ("사회과학대학", "경제학부", "u"), ("사회과학대학", "사회학과", "u"), ("사회과학대학", "인류학과", "u"),
    ("사회과학대학", "심리학과", "u"), ("사회과학대학", "지리학과", "u"), ("사회과학대학", "사회복지학과", "u"), ("사회과학대학", "언론정보학과", "u"), ("사회과학대학", "소계", "s"),
    ("자연과학대학", "수리과학부", "u"), ("자연과학대학", "통계학과", "u"), ("자연과학대학", "물리·천문학부(물리학전공)", "u"), ("자연과학대학", "물리·천문학부(천문학전공)", "u"),
    ("자연과학대학", "화학부", "u"), ("자연과학대학", "생명과학부", "u"), ("자연과학대학", "지구환경과학부", "u"), ("자연과학대학", "소계", "s"),
    ("간호대학", "간호대학", "u"),
    ("경영대학", "경영대학", "u"),
    ("공과대학", "건설환경도시공학부", "u"), ("공과대학", "기계공학부", "u"), ("공과대학", "재료공학부", "u"), ("공과대학", "전기·정보공학부", "u"),
    ("공과대학", "컴퓨터공학부", "u"), ("공과대학", "화학생물공학부", "u"), ("공과대학", "건축학과", "u"), ("공과대학", "산업공학과", "u"),
    ("공과대학", "에너지자원공학과", "u"), ("공과대학", "원자핵공학과", "u"), ("공과대학", "조선해양공학과", "u"), ("공과대학", "항공우주공학과", "u"), ("공과대학", "소계", "s"),
    ("농업생명과학대학", "농경제사회학부", "u"), ("농업생명과학대학", "식물생산과학부", "u"), ("농업생명과학대학", "산림과학부", "u"), ("농업생명과학대학", "식품·동물생명공학부", "u"),
    ("농업생명과학대학", "응용생물화학부", "u"), ("농업생명과학대학", "조경·지역시스템공학부", "u"), ("농업생명과학대학", "바이오시스템·소재학부", "u"), ("농업생명과학대학", "스마트시스템과학과", "u"), ("농업생명과학대학", "소계", "s"),
    ("미술대학", "디자인과", "u"),
    ("사범대학", "교육학과", "u"), ("사범대학", "국어교육과", "u"), ("사범대학", "영어교육과", "u"), ("사범대학", "독어교육과", "u"), ("사범대학", "불어교육과", "u"),
    ("사범대학", "사회교육과", "u"), ("사범대학", "역사교육과", "u"), ("사범대학", "지리교육과", "u"), ("사범대학", "윤리교육과", "u"), ("사범대학", "수학교육과", "u"),
    ("사범대학", "물리교육과", "u"), ("사범대학", "화학교육과", "u"), ("사범대학", "생물교육과", "u"), ("사범대학", "지구과학교육과", "u"), ("사범대학", "체육교육과", "u"), ("사범대학", "소계", "s"),
    ("생활과학대학", "소비자아동학부(소비자학전공)", "u"), ("생활과학대학", "소비자아동학부(아동가족학전공)", "u"), ("생활과학대학", "식품영양학과", "u"), ("생활과학대학", "의류학과", "u"), ("생활과학대학", "소계", "s"),
    ("수의과대학", "수의예과", "u"), ("약학대학", "약학계열", "u"),
    ("음악대학", "피아노과", "u"), ("음악대학", "관현악과", "u"), ("음악대학", "국악과", "u"), ("음악대학", "소계", "s"),
    ("의과대학", "의학과", "u"), ("첨단융합학부", "첨단융합학부", "u"), ("치의학대학원", "치의학과", "u"),
    ("", "총계", "t"),
]
S2 = [  # Ⅱ. 기회균형특별전형(사회통합) 전체 | 농생명계열(총계에서만)  (4~5쪽)
    ("학부대학", "자유전공학부", "u"), ("인문대학", "인문계열", "u"),
    ("사회과학대학", "정치외교학부", "u"), ("사회과학대학", "경제학부", "u"), ("사회과학대학", "사회학과", "u"), ("사회과학대학", "인류학과", "u"),
    ("사회과학대학", "심리학과", "u"), ("사회과학대학", "지리학과", "u"), ("사회과학대학", "사회복지학과", "u"), ("사회과학대학", "언론정보학과", "u"), ("사회과학대학", "소계", "s"),
    ("자연과학대학", "수리과학부", "u"), ("자연과학대학", "통계학과", "u"), ("자연과학대학", "물리·천문학부(물리학전공)", "u"), ("자연과학대학", "화학부", "u"),
    ("자연과학대학", "생명과학부", "u"), ("자연과학대학", "지구환경과학부", "u"), ("자연과학대학", "소계", "s"),
    ("간호대학", "간호대학", "u"), ("경영대학", "경영대학", "u"),
    ("공과대학", "건설환경도시공학부", "u"), ("공과대학", "기계공학부", "u"), ("공과대학", "재료공학부", "u"), ("공과대학", "전기·정보공학부", "u"),
    ("공과대학", "컴퓨터공학부", "u"), ("공과대학", "화학생물공학부", "u"), ("공과대학", "건축학과", "u"), ("공과대학", "산업공학과", "u"),
    ("공과대학", "에너지자원공학과", "u"), ("공과대학", "원자핵공학과", "u"), ("공과대학", "조선해양공학과", "u"), ("공과대학", "항공우주공학과", "u"), ("공과대학", "소계", "s"),
    ("농업생명과학대학", "농경제사회학부", "u"), ("농업생명과학대학", "식물생산과학부", "u"), ("농업생명과학대학", "산림과학부", "u"), ("농업생명과학대학", "식품·동물생명공학부", "u"),
    ("농업생명과학대학", "응용생물화학부", "u"), ("농업생명과학대학", "조경·지역시스템공학부", "u"), ("농업생명과학대학", "바이오시스템·소재학부", "u"), ("농업생명과학대학", "스마트시스템과학과", "u"), ("농업생명과학대학", "소계", "s"),
    ("미술대학", "동양화과", "u"), ("미술대학", "서양화과", "u"), ("미술대학", "조소과", "u"), ("미술대학", "공예과", "u"), ("미술대학", "디자인과", "u"), ("미술대학", "소계", "s"),
    ("사범대학", "교육학과", "u"), ("사범대학", "국어교육과", "u"), ("사범대학", "영어교육과", "u"), ("사범대학", "독어교육과", "u"), ("사범대학", "불어교육과", "u"),
    ("사범대학", "사회교육과", "u"), ("사범대학", "역사교육과", "u"), ("사범대학", "지리교육과", "u"), ("사범대학", "윤리교육과", "u"), ("사범대학", "수학교육과", "u"),
    ("사범대학", "물리교육과", "u"), ("사범대학", "화학교육과", "u"), ("사범대학", "생물교육과", "u"), ("사범대학", "지구과학교육과", "u"), ("사범대학", "체육교육과", "u"), ("사범대학", "소계", "s"),
    ("생활과학대학", "소비자아동학부(소비자학전공)", "u"), ("생활과학대학", "소비자아동학부(아동가족학전공)", "u"), ("생활과학대학", "식품영양학과", "u"), ("생활과학대학", "의류학과", "u"), ("생활과학대학", "소계", "s"),
    ("수의과대학", "수의예과", "u"), ("약학대학", "약학계열", "u"),
    ("음악대학", "성악과", "u"), ("음악대학", "작곡과", "u"), ("음악대학", "피아노과", "u"), ("음악대학", "관현악과", "u"), ("음악대학", "소계", "s"),
    ("의과대학", "의학과", "u"), ("첨단융합학부", "첨단융합학부", "u"),
    ("", "총계", "t"),
]
S3 = [  # Ⅲ. 음악대학 세부전공: 일반전형 | 기회균형(사회통합)  (6쪽)
    ("음악대학", "성악과(여자)", "u"), ("음악대학", "작곡과(작곡)", "u"), ("음악대학", "피아노과(피아노)", "u"),
] + [("음악대학", "관현악과(%s)" % x, "u") for x in ["바이올린", "비올라", "첼로", "콘트라베이스", "하프", "클래식기타", "플루트", "오보에", "클라리넷", "바순", "혼", "트럼펫", "트롬본", "색소폰", "튜바", "타악기"]] \
  + [("음악대학", "국악과(%s)" % x, "u") for x in ["가야금", "거문고", "해금", "피리", "대금", "아쟁", "타악기", "이론", "작곡", "성악"]]

SECTIONS = [
    {"pages": [0, 1, 2], "rows": S1, "types": ("지역균형전형", "일반전형"), "group2_rows": True},
    {"pages": [3, 4], "rows": S2, "types": ("기회균형특별전형(사회통합)", "기회균형특별전형(사회통합)-농생명계열"), "group2_rows": False},
    {"pages": [5], "rows": S3, "types": ("일반전형", "기회균형특별전형(사회통합)"), "group2_rows": True, "detail": True},
]
# 숫자는 오른쪽 정렬이므로 x1(오른쪽 끝) 기준 열 구간 (자릿수가 늘어도 안정)
BANDS = [("q1", 0, 365), ("a1", 365, 395), ("r1", 395, 450), ("q2", 450, 485), ("a2", 485, 515), ("r2", 515, 560)]
NUM = re.compile(r"^[\d,]+$|^-$|^\d+\.\d+$")


def num(v):
    if v is None or v == "-":
        return None
    try:
        return int(v.replace(",", ""))
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return None


def page_rows(page):
    """숫자 단어를 y 로 묶어 행으로, x 로 열에 배정"""
    ws = page.extract_words()
    keep = []
    for j, w in enumerate(ws):
        if w["text"] == ":":
            continue
        if w["text"] == "1" and j > 0 and ws[j - 1]["text"] == ":":
            continue
        if NUM.match(w["text"]):
            keep.append(w)
    rows = {}
    for w in keep:
        key = round(w["top"] / 3)
        # 근접 행 병합
        hit = next((k for k in rows if abs(k - key) <= 1), None)
        rows.setdefault(hit if hit is not None else key, []).append(w)
    out = []
    for key in sorted(rows):
        cells = {}
        for w in rows[key]:
            for name, lo, hi in BANDS:
                if lo <= w["x1"] < hi:
                    cells.setdefault(name, w["text"])
                    break
        if any(k in cells for k in ("q1", "q2", "a1", "a2")):
            out.append(cells)
    return out


def parse_pdf(path):
    import pdfplumber
    warnings, types, units = [], [], []
    with pdfplumber.open(path) as pdf:
        for sec in SECTIONS:
            rows = []
            for pi in sec["pages"]:
                rows += page_rows(pdf.pages[pi])
            if not sec["group2_rows"]:
                # 2열(농생명계열)은 세로로 걸쳐 있어 별도 행으로 잡힘 → 1열 값이 없는 행 제거
                rows = [c for c in rows if "q1" in c or "a1" in c]
            tmpl = sec["rows"]
            if len(rows) != len(tmpl):
                warnings.append("행 수 불일치: %s 구간 템플릿 %d행 vs PDF %d행" % (sec["types"][0], len(tmpl), len(rows)))
                # 총계 검증만이라도 하도록 짧은 쪽에 맞춤
            acc = {"q1": 0, "a1": 0, "q2": 0, "a2": 0}
            prev_college = None
            for (college, unit, kind), cells in zip(tmpl, rows):
                if kind == "u" and college != prev_college:
                    acc = {"q1": 0, "a1": 0, "q2": 0, "a2": 0}   # 소계 없는 단과대학(학부대학·간호·경영 등) 경계에서 초기화
                prev_college = college
                q1, a1, r1 = num(cells.get("q1")), num(cells.get("a1")), num(cells.get("r1"))
                q2, a2, r2 = num(cells.get("q2")), num(cells.get("a2")), num(cells.get("r2"))
                if kind == "u":
                    if q1 is not None:
                        units.append({"type": sec["types"][0], "group": "", "college": college, "unit": unit,
                                      "quota": q1, "app": a1 or 0, "ratio": r1 if r1 is not None else (round((a1 or 0) / q1, 2) if q1 else None),
                                      **({"detail": True} if sec.get("detail") else {})})
                        acc["q1"] += q1
                        acc["a1"] += a1 or 0
                    if sec["group2_rows"] and q2 is not None:
                        units.append({"type": sec["types"][1], "group": "", "college": college, "unit": unit,
                                      "quota": q2, "app": a2 or 0, "ratio": r2 if r2 is not None else (round((a2 or 0) / q2, 2) if q2 else None),
                                      **({"detail": True} if sec.get("detail") else {})})
                        acc["q2"] += q2
                        acc["a2"] += a2 or 0
                elif kind == "s":
                    if q1 is not None and q1 != acc["q1"]:
                        warnings.append("소계 불일치(%s %s 1열): 합 %s vs 소계 %s" % (college, sec["types"][0], acc["q1"], q1))
                    if a1 is not None and a1 != acc["a1"]:
                        warnings.append("소계 불일치(%s %s 지원): 합 %s vs 소계 %s" % (college, sec["types"][0], acc["a1"], a1))
                    if sec["group2_rows"] and q2 is not None and q2 != acc["q2"]:
                        warnings.append("소계 불일치(%s %s 2열): 합 %s vs 소계 %s" % (college, sec["types"][1], acc["q2"], q2))
                    acc = {"q1": 0, "a1": 0, "q2": 0, "a2": 0}
                elif kind == "t":
                    if q1 is not None:
                        types.append({"name": sec["types"][0], "group": "", "quota": q1, "app": a1 or 0, "ratio": r1})
                    if q2 is not None:
                        types.append({"name": sec["types"][1], "group": "", "quota": q2, "app": a2 or 0, "ratio": r2})
    return types, units, warnings


def find_latest_pdf():
    """공지 목록에서 최신 접수현황 글 → 첨부 PDF URL, 기준시각"""
    doc = collect.fetch(NOTICE, retries=1, timeout=30)
    cands = []
    for href, txt in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', doc, re.S | re.I):
        t = collect.text_of(txt)
        m = re.search(r"수시모집\s*지원서\s*접수현황\s*\((\d{1,2})/(\d{1,2})\s*(\d{1,2}):(\d{2})\s*기준\)", t)
        mf = re.search(r"수시모집\s*지원서\s*접수현황\s*\(\s*최종\s*\)", t)
        idx = re.search(r"bbsidx=(\d+)", href)
        if m and idx:
            mo, d, h, mi = map(int, m.groups())
            cands.append((int(idx.group(1)), "2026-%02d-%02dT%02d:%02d" % (mo, d, h, mi)))
        elif mf and idx:
            cands.append((int(idx.group(1)), FINAL_ASOF))
    if not cands:
        raise RuntimeError("접수현황 공지를 찾지 못했습니다")
    idx, as_of = max(cands)
    page = collect.fetch("%s?md=v&bbsidx=%d" % (NOTICE, idx), retries=1, timeout=30)
    url = fname = None
    for href, txt in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, re.S | re.I):
        t = collect.text_of(txt)
        if "md=down" in href and ".pdf" in t.lower():
            url = html.unescape(href)
            fname = re.search(r"(\S+\.pdf)", t, re.I).group(1)
            break
    if not url:
        raise RuntimeError("첨부 PDF 링크를 찾지 못했습니다 (bbsidx=%d)" % idx)
    if url.startswith("/"):
        url = "https://admission.snu.ac.kr" + url
    return url, fname, as_of, "%s?md=v&bbsidx=%d" % (NOTICE, idx)


def download(url, fname, referer=NOTICE):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, re.sub(r"[^\w.\-]", "_", fname))
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    headers = dict(collect.HEADERS)
    headers["Referer"] = referer          # 서울대 서버는 Referer 없이는 404
    req = collect.urllib.request.Request(url, headers=headers)
    with collect.urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with open(path, "wb") as f:
        f.write(data)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", help="이미 받은 PDF 경로(다운로드 생략)")
    args = ap.parse_args()
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%dT%H:%M")
    rec = {"name": NAME, "ok": False, "source": "pdf", "url": NOTICE, "collectedAt": now}
    try:
        if args.pdf:
            path, as_of, page_url = args.pdf, None, NOTICE
            m = re.search(r"_(\d{2})(\d{2})(\d{2})(\d{2})\.pdf$", os.path.basename(path))
            if m:
                as_of = "2026-%s-%sT%s:%s" % m.groups()
            elif re.search(r"final|최종", os.path.basename(path), re.I):
                as_of = FINAL_ASOF
        else:
            url, fname, as_of, page_url = find_latest_pdf()
            path = download(url, fname, referer=page_url)
        types, units, warnings = parse_pdf(path)
        bad = [w for w in warnings if "불일치" in w]
        rec.update({"asOf": as_of, "url": page_url, "pdf": os.path.basename(path), "types": types, "units": units,
                    "warnings": warnings, "pageTitle": "서울대학교 수시모집 지원서 접수현황(PDF)"})
        # 총계: 세부전공(Ⅲ)은 Ⅰ·Ⅱ에 이미 포함되므로 전형 총계 합만 사용
        q = sum(t["quota"] or 0 for t in types)
        a = sum(t["app"] or 0 for t in types)
        rec["total"] = {"quota": q, "app": a, "ratio": round(a / q, 2) if q else None}
        rec["ok"] = bool(types) and not bad
        if bad:
            rec["error"] = "PDF 행 대응 검증 실패: " + "; ".join(bad[:3])
    except Exception as e:  # noqa
        rec["error"] = str(e)[:200]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
            if old.get("ok") and (not rec["ok"] or (old.get("asOf") or "") > (rec.get("asOf") or "")):
                print("서울대: 기존 기록(%s)이 더 최신·유효하므로 유지" % old.get("asOf"))
                return
        except Exception:
            pass
    if rec["ok"] and rec.get("asOf") == FINAL_ASOF:
        rec["final"] = True
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print("서울대: ok=%s asOf=%s 전형 %d 모집단위 %d 총 %s 경고 %d %s" % (
        rec["ok"], rec.get("asOf"), len(rec.get("types", [])), len(rec.get("units", [])), rec.get("total"), len(rec.get("warnings", [])), rec.get("error", "")))
    for w in rec.get("warnings", [])[:8]:
        print("  !", w)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
