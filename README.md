# 2027 수시모집 경쟁률 상황판 (충청권 프로토타입)

경기도교육청 GAS 웹앱 "2027 수시전형 경쟁률 검색기"(링크 모음)를 참고해, 링크 대신 **실제 경쟁률 수치를 자동 수집·비교**하도록 새로 만든 도구.

## 파일

| 파일 | 역할 |
|---|---|
| `universities.json` | 대상 대학 35개교(충남 19·대전 13·세종 3). 대학명·지역·설립·마감·경쟁률 페이지 URL(2027/2026/2025) |
| `collect.py` | 경쟁률 페이지 수집·파싱 → `data/latest.json`, `data/history.json`, `data/snapshots/` |
| `build.py` | 데이터를 `template.html`에 심어 `2027susi-ratio.html` 단일 파일 생성 |
| `template.html` | 화면 원본(직접 편집 대상). `2027susi-ratio.html`은 직접 편집 금지 |

## 사용

```bash
python collect.py --final 2026   # 작년 최종 경쟁률 1회 수집 (비교 기준)
python collect.py                # 2027 실시간 수집 (접수 기간 중 30분~1시간 간격 반복)
python build.py                  # HTML 재생성
```

미리보기: `.claude/launch.json` 의 `susiratio` (포트 8809) → `http://localhost:8809/2027susi-ratio.html`

## 파서가 다루는 페이지

- 진학어플라이 `addon.jinhakapply.com/RatioV1/...` (UTF-8)
- 유웨이어플라이 `ratio.uwayapply.com/...` (EUC-KR)
- 제목(h태그/caption) 뒤에 오는 표를 순서대로 읽고, `모집인원·지원인원·경쟁률·모집단위·전형명` 헤더 이름으로 열을 찾는다(rowspan/colspan 전개).
- 대학 자체 페이지(세한대·유원대·한국전통문화대)는 미지원.

## 알려진 한계

- 2027 링크 미확보 대학 10곳: 경찰대·국군간호사관·KAIST·단국대(천안, 죽전과 통합 공개)·을지대(대전)·공주교대·대전가톨릭대·세한대·유원대·한국전통문화대.
- 정원외 전형은 대학이 모집인원을 전형 총원으로 반복 표기하거나 rowspan으로 묶는 경우가 있어 `quotaShared` 표시(※)만 하고 대학 공개값을 그대로 보여준다.
- 작년 최종 연결은 전형·모집단위명 정규화 매칭이라 명칭이 바뀐 전형은 연결되지 않는다.
- 히스토리·직전 대비 증감은 수집을 2회 이상 해야 채워진다.

## 확장

`universities.json` 에 행을 추가하면 전국 어느 대학이든 동일하게 동작한다(URL만 확보하면 됨).
