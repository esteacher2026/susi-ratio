#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
2027 수시모집 경쟁률 수집기
- universities.json 의 경쟁률 공개 페이지(진학어플라이·유웨이어플라이)를 받아 표를 파싱한다.
- 산출: data/latest.json (최신 전체), data/history.json (대학별 총계 추이),
        data/snapshots/{year}_{YYYYMMDD_HHMM}.json (회차별 사본)
- 사용:
    python collect.py                 # 2027 실시간 수집
    python collect.py --final 2026    # 2026 최종 경쟁률 1회 수집 → data/final2026.json
    python collect.py --only u05,u09  # 일부 대학만
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
SNAP = os.path.join(DATA, "snapshots")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
SUPPORTED_HOSTS = ("jinhakapply.com", "uwayapply.com")

# ---------------------------------------------------------------- 네트워크

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.jinhakapply.com/",
    "Connection": "close",
}


def fetch(url, retries=2, timeout=40):
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "")
            return decode(raw, ctype)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("fetch failed: %s (%s)" % (url, last))


def decode(raw, ctype=""):
    m = re.search(rb'charset=["\']?\s*([\w-]+)', raw[:4000], re.I)
    cands = []
    if m:
        cands.append(m.group(1).decode("ascii", "ignore"))
    m2 = re.search(r'charset=([\w-]+)', ctype or "", re.I)
    if m2:
        cands.append(m2.group(1))
    cands += ["utf-8", "cp949"]
    for enc in cands:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "ignore")

# ---------------------------------------------------------------- HTML 유틸

TAG = re.compile(r"""<(?:"[^"]*"|'[^']*'|[^>"'])*>""")
WS = re.compile(r"\s+")


def text_of(fragment):
    s = TAG.sub(" ", fragment)
    s = html.unescape(s).replace("\xa0", " ")
    return WS.sub(" ", s).strip()


BLOCK = re.compile(r"<br\s*/?>|</(?:p|div|li|tr|h[1-6])\s*>", re.I)


def cell_text(fragment):
    """표 셀 텍스트: <br>·블록 끝을 줄바꿈으로 남긴다(모집단위명 뒤에 붙은 설명 분리용)"""
    s = BLOCK.sub("\n", fragment)
    s = TAG.sub(" ", s)
    s = html.unescape(s).replace("\xa0", " ")
    lines = [WS.sub(" ", ln).strip() for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def first_line(s):
    return (s or "").split("\n")[0].strip()


def flat(s):
    return (s or "").replace("\n", " ").strip()


def strip_noise(doc):
    return re.sub(r"<(script|style)\b.*?</\1>", "", doc, flags=re.S | re.I)


def table_grid(table_html):
    """rowspan/colspan 을 펼쳐 (is_header, [cell,...]) 목록으로 반환"""
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", table_html, re.S | re.I)
    grid = []
    pending = {}  # col -> [text, remaining]
    for r in rows:
        cells = re.findall(r"""<t([hd])\b((?:"[^"]*"|'[^']*'|[^>"'])*)>(.*?)</t[hd]>""", r, re.S | re.I)
        if not cells:
            continue
        out = []
        spanned = set()
        col = 0

        def flush_pending():
            nonlocal col
            while col in pending:
                txt, rem = pending[col]
                out.append(txt)
                spanned.add(col)
                rem -= 1
                if rem <= 0:
                    del pending[col]
                else:
                    pending[col][1] = rem
                col += 1

        for kind, attrs, inner in cells:
            flush_pending()
            rs = re.search(r"rowspan\s*=\s*[\"']?\s*(\d+)", attrs, re.I)
            cs = re.search(r"colspan\s*=\s*[\"']?\s*(\d+)", attrs, re.I)
            rs = int(rs.group(1)) if rs else 1
            cs = int(cs.group(1)) if cs else 1
            txt = cell_text(inner)
            for _ in range(max(cs, 1)):
                out.append(txt)
                if rs > 1:
                    pending[col] = [txt, rs - 1]
                col += 1
        flush_pending()
        is_header = all(k.lower() == "h" for k, _, _ in cells)
        grid.append((is_header, out, spanned))
    return grid


def to_int(s):
    if s is None:
        return None
    s = s.replace(",", "").strip()
    m = re.fullmatch(r"-?\d+", s)
    return int(m.group(0)) if m else None


def to_ratio(s):
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*:", s)
    if m:
        return float(m.group(1))
    m = re.fullmatch(r"\d+(?:\.\d+)?", s.strip())
    return float(m.group(0)) if m else None


def find_asof(doc_text):
    pats = [
        r"(20\d\d)-(\d{1,2})-(\d{1,2})\s*(오전|오후)?\s*(\d{1,2}):(\d{2})",
        r"(20\d\d)\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*(오전|오후)?\s*(\d{1,2})\s*시\s*(\d{2})\s*분",
        r"(20\d\d)[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})[^\d]{0,8}(오전|오후)?\s*(\d{1,2}):(\d{2})",
    ]
    for p in pats:
        m = re.search(p, doc_text)
        if m:
            y, mo, d, ampm, h, mi = m.groups()
            h = int(h)
            if ampm == "오후" and h < 12:
                h += 12
            if ampm == "오전" and h == 12:
                h = 0
            try:
                return dt.datetime(int(y), int(mo), int(d), h, int(mi)).strftime("%Y-%m-%dT%H:%M")
            except ValueError:
                continue
    return None

# ---------------------------------------------------------------- 파서

SUBTOTAL = {"소계", "합계", "총계", "계", "총합계", "합 계", "총 계"}


def header_map(hdr):
    hdr = [h.replace(" ", "").replace("\n", "") for h in hdr]

    def idx_all(pred):
        return [i for i, h in enumerate(hdr) if pred(h)]
    m = {}
    q = idx_all(lambda h: "모집인원" in h and "최대" not in h)
    a = idx_all(lambda h: "지원인원" in h or h in ("지원자", "지원자수"))
    r = idx_all(lambda h: "경쟁률" in h)
    u = idx_all(lambda h: "모집단위" in h or (("학과" in h or "전공" in h)
                                            and not any(k in h for k in ("홈페이지", "소개", "진로"))))
    c = idx_all(lambda h: h == "대학" or h.startswith("대학(") or h == "단과대학")
    if not c:
        c = idx_all(lambda h: h and ("대학" in h or "계열" in h or "단과" in h) and "모집단위" not in h)
    t = idx_all(lambda h: h in ("전형명", "전형", "전형유형"))
    g = idx_all(lambda h: h == "구분")
    m["quota"] = q[0] if q else None
    m["app"] = a[0] if a else None
    m["ratio"] = r[0] if r else None
    m["units"] = u
    m["college"] = c[0] if c else None
    m["type"] = t[-1] if t else (g[-1] if g else None)
    m["typeStrict"] = t[-1] if t else None      # '전형명' 류 명시 열만 (모집단위 표의 '구분' 열은 정원/단과대 구분)
    m["gubun"] = g[-1] if g else None
    m["maxsel"] = idx_all(lambda h: "최대선발" in h)
    return m


def clean_heading(h):
    h = h.strip()
    group = ""
    m = re.match(r"\[\s*(정원내|정원외)\s*\]\s*", h) or re.match(r"(정원내|정원외)\s+", h)
    if m:
        group = m.group(1)
        h = h[m.end():]
    h = re.sub(r"\s*경쟁률\s*현황\s*$", "", h).strip()
    return h, group


def simplify(s):
    """제목↔전형명 대조용 단순화"""
    s = str(s or "")
    s = re.sub(r"\s*경쟁률\s*현황\s*", "", s)
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = re.sub(r"\([^()]*(?:%|점|단계|없음|반영)[^()]*\)", "", s)
    s = re.sub(r"[\s\-–·ㆍ_/,.*※:()\[\]]", "", s)
    s = s.replace("전형", "")
    return s.lower()


GROUP_RE = re.compile(r"\[?\s*정원\s*\(?\s*(내|외)\s*\)?\s*\]?")


def heading_kind(text):
    """제목 텍스트 분류: ('group','정원내') / ('type', text) / None"""
    t = re.sub(r"\s*경쟁률\s*현황\s*$", "", text).strip()
    if not t:
        return None
    g = GROUP_RE.fullmatch(t)
    if g:
        return ("group", "정원" + g.group(1))
    return ("type", text)


def pick_type_heading(stack, known_types):
    """제목 스택(오래된→최근)에서 전형 제목과 그 아래 소제목(단과대학 등)을 고른다"""
    cands = [(i, lv, tx) for i, (lv, tx) in enumerate(stack) if heading_kind(tx) and heading_kind(tx)[0] == "type"]
    if not cands:
        return "", ""
    if known_types:
        ks = [(simplify(k), k) for k in known_types]
        for i, lv, tx in reversed(cands):
            h = simplify(clean_heading(tx)[0])
            if len(h) < 2:
                continue
            for sk, k in ks:
                if sk and (h == sk or (len(sk) >= 2 and sk in h) or (len(h) >= 2 and h in sk)):
                    below = [t for j, l, t in cands if j > i]
                    return tx, (below[-1] if below else "")
    return cands[-1][2], ""


def parse_page(doc):
    doc = strip_noise(doc)
    plain = text_of(doc)
    result = {"asOf": find_asof(plain), "total": None, "types": [], "units": [], "warnings": []}

    seq = re.finditer(
        r"(<(h[1-6])\b[^>]*>(.*?)</h[1-6]>|<(caption)\b[^>]*>(.*?)</caption>|<(strong|b)\b[^>]*>(.*?)</(?:strong|b)>"
        r"|<table\b[^>]*>.*?</table>)", doc, re.S | re.I)
    stack = []          # [(level, text)] 오래된→최근

    def push(level, text):
        text = text.strip()
        if not text or len(text) > 120:
            return
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, text))

    for m in seq:
        tok = m.group(0)
        low = tok[:8].lower()
        if not low.startswith("<table"):
            if m.group(2):
                push(int(m.group(2)[1]), text_of(m.group(3)))
            elif m.group(4):
                push(7, text_of(m.group(5)))
            else:
                t = text_of(m.group(7))
                if 2 <= len(t) <= 60:
                    push(6, t)
            continue
        grid = table_grid(tok)
        if not grid:
            continue
        hdr_rows = [g for g in grid if g[0]]
        hdr = hdr_rows[0][1] if hdr_rows else grid[0][1]
        body = [(g[1], g[2]) for g in grid if not g[0]]
        hm = header_map(hdr)
        if hm["quota"] is None or hm["app"] is None:
            # 제목 역할만 하는 표(예: '학생부교과(일반전형) 경쟁률 현황' 한 칸짜리)
            cells = [flat(c) for r in grid for c in r[1] if flat(c)]
            if 1 <= len(grid) <= 2 and cells and len(cells[0]) <= 80 and ("경쟁률" in cells[0] or "전형" in cells[0] or GROUP_RE.fullmatch(cells[0])):
                push(6, cells[0])
            continue
        max_sel = hm["maxsel"]

        if hm["units"]:
            known = [t["name"] for t in result["types"]]
            type_h, sub_h = pick_type_heading(stack, known)
            tname, group = clean_heading(type_h)
            # 정원 구분 소제목: 전형 제목보다 최근에 나온 것
            for lv, tx in reversed(stack):
                hk = heading_kind(tx)
                if hk and hk[0] == "group":
                    if not group:
                        group = hk[1]
                    break
                if tx == type_h:
                    break
            sub_college = ""
            if sub_h:
                hk = heading_kind(sub_h)
                if hk and hk[0] == "type":
                    sub_college = clean_heading(sub_h)[0]
            unit_cols = [i for i in hm["units"] if "모집단위" in hdr[i].replace(" ", "")] or hm["units"]
            for row, spanned in body:
                if len(row) <= max(hm["quota"], hm["app"]):
                    continue
                unit_parts = []
                for i in unit_cols:
                    if i < len(row):
                        v = first_line(row[i])
                        if v and v not in unit_parts:
                            unit_parts.append(v)
                unit = " ".join(unit_parts).strip()
                if not unit or unit in SUBTOTAL:
                    continue
                quota = to_int(flat(row[hm["quota"]]))
                app = to_int(flat(row[hm["app"]]))
                if quota is None and app is None:
                    continue
                ratio = to_ratio(flat(row[hm["ratio"]])) if hm["ratio"] is not None and hm["ratio"] < len(row) else None
                if ratio is None and quota and app is not None:
                    ratio = round(app / quota, 2)
                college = first_line(row[hm["college"]]) if hm["college"] is not None and hm["college"] < len(row) else ""
                if college == unit:
                    college = ""
                if not college and sub_college:
                    college = sub_college
                row_type = tname
                row_group = group
                if hm["typeStrict"] is not None and hm["typeStrict"] not in hm["units"] and hm["typeStrict"] < len(row) and flat(row[hm["typeStrict"]]):
                    row_type = flat(row[hm["typeStrict"]])
                    if not college:
                        college = tname
                if hm["gubun"] is not None and hm["gubun"] not in hm["units"] and hm["gubun"] < len(row):
                    gv = flat(row[hm["gubun"]])
                    gm = GROUP_RE.fullmatch(gv) if gv else None
                    if gm:
                        row_group = "정원" + gm.group(1)
                    elif gv and not college and gv != unit:
                        college = gv
                rec = {
                    "type": row_type, "group": row_group, "college": college, "unit": unit,
                    "quota": quota, "app": app, "ratio": ratio,
                }
                desc = row[unit_cols[0]] if unit_cols and unit_cols[0] < len(row) else ""
                if "\n" in desc:
                    rec["unitNote"] = flat(desc.split("\n", 1)[1])[:120]
                if max_sel or hm["quota"] in spanned:
                    rec["quotaShared"] = True
                    if max_sel and max_sel[0] < len(row) and flat(row[max_sel[0]]):
                        rec["maxSel"] = flat(row[max_sel[0]])
                result["units"].append(rec)
        elif hm["type"] is not None:
            for row, _spanned in body:
                if len(row) <= max(hm["quota"], hm["app"], hm["type"]):
                    continue
                tname = flat(row[hm["type"]])
                quota = to_int(flat(row[hm["quota"]]))
                app = to_int(flat(row[hm["app"]]))
                ratio = to_ratio(flat(row[hm["ratio"]])) if hm["ratio"] is not None and hm["ratio"] < len(row) else None
                if ratio is None and quota and app is not None:
                    ratio = round(app / quota, 2)
                if not tname:
                    continue
                if tname in SUBTOTAL:
                    if result["total"] is None and quota is not None:
                        result["total"] = {"quota": quota, "app": app, "ratio": ratio}
                    continue
                group = ""
                first = flat(row[0])
                if first in ("정원내", "정원외") and hm["type"] != 0:
                    group = first
                if re.fullmatch(r"(정원내|정원외)\s*(소계|합계|계)?", tname):
                    continue
                result["types"].append({"name": tname, "group": group, "quota": quota, "app": app, "ratio": ratio})

    if not result["types"] and result["units"]:
        agg = {}
        for x in result["units"]:
            k = (x["type"], x["group"])
            a = agg.setdefault(k, {"name": x["type"], "group": x["group"], "quota": 0, "app": 0})
            a["quota"] += x["quota"] or 0
            a["app"] += x["app"] or 0
        for a in agg.values():
            a["ratio"] = round(a["app"] / a["quota"], 2) if a["quota"] else None
            a["derived"] = True
        result["types"] = list(agg.values())
    if result["total"] is None and result["types"]:
        q = sum(t["quota"] or 0 for t in result["types"])
        a = sum(t["app"] or 0 for t in result["types"])
        result["total"] = {"quota": q, "app": a, "ratio": round(a / q, 2) if q else None, "derived": True}
    if not result["types"] and not result["units"]:
        result["warnings"].append("표를 찾지 못했습니다")
    return result

# ---------------------------------------------------------------- 실행

def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj, compact=False):
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1)


def collect_one(u, year):
    url = (u.get("ratio") or {}).get(str(year))
    rec = {"id": u["id"], "name": u["name"], "url": url, "ok": False}
    if not url:
        rec["error"] = "경쟁률 페이지 링크 없음"
        return rec
    if not any(h in url for h in SUPPORTED_HOSTS):
        rec["error"] = "지원하지 않는 페이지 형식(대학 자체 페이지)"
        return rec
    try:
        doc = fetch(url)
        parsed = parse_page(doc)
        rec.update(parsed)
        rec["ok"] = bool(parsed["types"] or parsed["units"])
        if not rec["ok"]:
            rec["error"] = "; ".join(parsed["warnings"]) or "파싱 결과 없음"
        # 페이지 제목에 대학명이 없으면 링크 오류 가능성 → 경고 표시(수집은 유지)
        tm = re.search(r"<title[^>]*>(.*?)</title>", doc, re.S | re.I)
        title = text_of(tm.group(1)) if tm else ""
        rec["pageTitle"] = title[:60]
        stem = re.sub(r"\(.*?\)|대학교|학교|국립|\s", "", u["name"])[:3]
        if stem and title and stem not in title.replace(" ", ""):
            rec["nameWarning"] = "페이지 제목 '%s' 에 대학명이 없음(링크 확인 필요)" % title[:30]
            rec.setdefault("warnings", []).append(rec["nameWarning"])
    except Exception as e:  # noqa
        rec["error"] = str(e)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2027)
    ap.add_argument("--final", type=int, help="지정 학년도 최종 경쟁률을 1회 수집해 data/final{year}.json 저장")
    ap.add_argument("--only", help="쉼표로 구분한 대학 id")
    ap.add_argument("--vendor", help="경쟁률 페이지 호스트 필터 (예: jinhakapply)")
    ap.add_argument("--out", help="결과를 이 파일에만 저장(피드용). latest/history 는 건드리지 않음")
    ap.add_argument("--feed", help="다른 곳(내 PC 등)에서 수집한 피드 JSON 경로 또는 URL. 더 새로운 기록으로 병합")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    unis = load_json(os.path.join(ROOT, "universities.json"), [])
    if args.only:
        keep = set(args.only.split(","))
        unis = [u for u in unis if u["id"] in keep]
    if args.vendor:
        unis = [u for u in unis if args.vendor in ((u.get("ratio") or {}).get(str(args.final or args.year)) or "")]

    year = args.final or args.year
    started = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))   # 한국 시간(러너는 UTC)
    print("[%s] %d개교 %d학년도 수집 시작" % (started.strftime("%H:%M:%S"), len(unis), year))
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        recs = list(ex.map(lambda u: collect_one(u, year), unis))

    ok = [r for r in recs if r["ok"]]
    for r in recs:
        if r["ok"]:
            t = r["total"] or {}
            print("  OK  %-16s 기준 %s  전형 %2d  모집단위 %4d  총 %s/%s (%s)" % (
                r["name"], r.get("asOf") or "-", len(r["types"]), len(r["units"]),
                t.get("app"), t.get("quota"), t.get("ratio")))
        else:
            print("  --  %-16s %s" % (r["name"], r.get("error")))
    print("성공 %d / %d" % (len(ok), len(recs)))

    now_iso = started.strftime("%Y-%m-%dT%H:%M")
    # 대학 목록(id↔이름) 버전: 목록이 바뀌면 이전 상태(latest/history)를 이어 쓰지 않는다
    import hashlib
    uver = hashlib.sha1("|".join(u["id"] + ":" + u["name"] for u in load_json(os.path.join(ROOT, "universities.json"), [])).encode("utf-8")).hexdigest()[:10]
    payload = {"collectedAt": now_iso, "year": year, "uver": uver, "universities": {r["id"]: r for r in recs}}

    if args.final:
        save_json(os.path.join(DATA, "final%d.json" % year), payload)
        print("저장: data/final%d.json" % year)
        return

    if args.out:
        # 피드 모드: 이 결과만 파일로 남긴다(다른 머신의 워크플로가 --feed 로 병합)
        save_json(args.out, payload, compact=True)
        print("저장: %s (피드, %d개교)" % (args.out, len(ok)))
        return

    if args.feed:
        # 외부 피드 병합: 이번 수집이 실패했거나 피드가 더 최신이면 피드 기록을 사용
        try:
            if re.match(r"https?://", args.feed):
                feed = json.loads(fetch(args.feed + ("&" if "?" in args.feed else "?") + "nocache=%d" % int(time.time())))
            else:
                feed = load_json(args.feed, {})
        except Exception as e:  # noqa
            feed = {}
            print("피드 읽기 실패: %s" % e)
        fu = feed.get("universities", {}) if isinstance(feed, dict) else {}
        merged = 0
        for i, r in enumerate(recs):
            f = fu.get(r["id"])
            if not (f and f.get("ok")):
                continue
            if f.get("name") != r["name"]:   # 대학 목록 번호가 바뀐 옛 피드 → 무시
                continue
            newer = (not r["ok"]) or ((f.get("asOf") or "") > (r.get("asOf") or "")) or (f.get("asOf") == r.get("asOf") and not r["ok"])
            if newer:
                f = dict(f)
                f["source"] = "feed"
                f["feedCollectedAt"] = feed.get("collectedAt")
                recs[i] = f
                merged += 1
        ok = [r for r in recs if r["ok"]]
        payload["universities"] = {r["id"]: r for r in recs}
        print("피드 병합: %d개교 (피드 수집시각 %s) → 성공 %d / %d" % (merged, feed.get("collectedAt"), len(ok), len(recs)))

    # 직전 수집분과 비교해 모집단위별 이전 지원인원(prevApp) 기록
    prev = load_json(os.path.join(DATA, "latest.json"), {})
    if prev and prev.get("uver") != uver:
        print("이전 latest.json 의 대학 목록 버전이 달라 무시합니다 (%s → %s)" % (prev.get("uver"), uver))
        prev = {}
    prev_unis = prev.get("universities", {})
    # 이번에 실패(차단·일시 오류)한 대학은 직전 성공분을 유지하고 stale 표시
    for i, r in enumerate(recs):
        p = prev_unis.get(r["id"])
        if not r["ok"] and r.get("url") and p and p.get("ok"):
            kept = dict(p)
            kept["stale"] = True
            kept["staleError"] = r.get("error")
            kept["staleSince"] = kept.get("staleSince") or now_iso
            recs[i] = kept
            print("  ~~  %-16s 직전 수집분 유지 (%s)" % (r["name"], r.get("error")))
    payload["universities"] = {r["id"]: r for r in recs}
    for r in recs:
        p = prev_unis.get(r["id"])
        if not (r["ok"] and p and p.get("ok")) or r.get("stale"):
            continue
        r["prevAsOf"] = p.get("asOf")
        pm = {(x["type"], x["group"], x["unit"]): x["app"] for x in p.get("units", [])}
        for x in r["units"]:
            key = (x["type"], x["group"], x["unit"])
            if key in pm:
                x["prevApp"] = pm[key]
        ptm = {(x["name"], x["group"]): x["app"] for x in p.get("types", [])}
        for x in r["types"]:
            if (x["name"], x["group"]) in ptm:
                x["prevApp"] = ptm[(x["name"], x["group"])]

    # 추이 기록(대학별 총계, asOf 기준 중복 제거)
    hist = load_json(os.path.join(DATA, "history.json"), {})
    if hist and hist.get("_uver") != uver:
        print("이전 history.json 의 대학 목록 버전이 달라 새로 시작합니다")
        hist = {}
    hist["_uver"] = uver
    for r in ok:
        t = r["total"] or {}
        stamp = r.get("asOf") or now_iso
        arr = hist.setdefault(r["id"], [])
        if arr and arr[-1]["t"] == stamp:
            arr[-1] = {"t": stamp, "app": t.get("app"), "quota": t.get("quota"), "ratio": t.get("ratio")}
        else:
            arr.append({"t": stamp, "app": t.get("app"), "quota": t.get("quota"), "ratio": t.get("ratio")})

    save_json(os.path.join(DATA, "latest.json"), payload)
    save_json(os.path.join(DATA, "history.json"), hist)
    snap = os.path.join(SNAP, "%d_%s.json" % (year, started.strftime("%Y%m%d_%H%M")))
    save_json(snap, payload, compact=True)
    print("저장: data/latest.json, data/history.json, %s" % os.path.relpath(snap, ROOT))


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
