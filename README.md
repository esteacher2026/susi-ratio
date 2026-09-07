# 2027 수시모집 경쟁률 상황판

전국 205개교(캠퍼스 통합 기준)의 2027학년도 수시모집 경쟁률을 30분 간격으로 자동 수집해
전형별·모집단위별로 비교하는 웹 상황판.

- **배포 주소**: https://esteacher2026.github.io/susi-ratio/
- 경기도교육청 GAS 웹앱 "2027 수시전형 경쟁률 검색기"(링크 모음)를 참고해 링크 대신 실제 수치를 수집하도록 새로 제작.

## 자동 갱신 구조 (하이브리드)

| 구성 | 역할 | 주기 |
|---|---|---|
| GitHub Actions `collect-and-deploy` | 유웨이어플라이 대학 수집 + 국내 피드 병합 + 빌드 + Pages 배포 | 30분 (cron) |
| 국내 PC `feed.cmd` (작업 스케줄러) | **진학어플라이** 대학만 수집해 `jinhak-feed` 브랜치의 `feed.json`에 force-push | 30분 |

진학어플라이(`addon.jinhakapply.com`)는 Cloudflare가 해외 IP를 차단하므로 GitHub 러너에서 열리지 않는다.
그래서 국내 PC가 피드를 올리고, 워크플로가 `--feed` 옵션으로 더 새로운 기록을 병합한다.
PC가 꺼져 있으면 진학어플라이 대학은 "직전 자료 유지(stale)"로 표시되고 유웨이 대학만 갱신된다.

상태(추이·직전 대비 증감)는 커밋 없이 유지된다: 워크플로가 시작할 때 배포된 사이트의
`state/latest.json`·`state/history.json`을 내려받아 이어 쓴다.

### PC 쪽 설정 (1회)

```bat
schtasks /Create /F /SC MINUTE /MO 30 /TN "susi-ratio-feed" /TR "cmd /c D:\claude\susi2027_ratio\feed.cmd"
```

해제: `schtasks /Delete /F /TN "susi-ratio-feed"`. 로그는 `_feed.log`. `_feed/`는 `jinhak-feed` 브랜치의 클론.

## 파일

| 파일 | 역할 |
|---|---|
| `universities.json` | 대상 대학 205개교. 대학명·지역·설립·마감·경쟁률 페이지 URL(2027/2026/2025). 같은 페이지를 쓰는 캠퍼스는 1건으로 통합 |
| `collect.py` | 수집·파싱. `--final 2026`(작년 최종 1회), `--vendor jinhakapply --out 파일`(피드), `--feed URL`(병합) |
| `build.py` | `docs/index.html` + `docs/data.json`(웹) 생성. `--embed`를 주면 오프라인용 `2027susi-ratio.html`도 생성 |
| `template.html` | 화면 원본(직접 편집 대상). `docs/`와 `2027susi-ratio.html`은 직접 편집 금지 |
| `feed.cmd` | 국내 PC 피드 전송기 (ASCII만 사용, cmd 인코딩 문제 방지) |
| `data/final2026.json` | 2026학년도 최종 경쟁률(커밋됨, 비교 기준) |
| `data/prior_timeline.json` | 2026·2025 접수 기간 시점별(D-3·D-2·D-1·D-day 오전/오후·최종) 경쟁률 + 3개년 최종. 원본: 카카오톡 수신 엑셀 「2027 대입을 위한 실시간 경쟁률.xlsx」(163개교 12,309행). build.py가 대학명 별칭·전형·모집단위 정규화로 실시간 모집단위에 결합(`tl`), 미결합 행은 `ref`로 화면에 "작년 자료만" 표시 |

## 로컬 사용

```bash
python collect.py --final 2026     # 작년 최종 (1회)
python collect.py                  # 2027 실시간 전체 수집
python build.py --embed            # docs/ + 오프라인 단일 HTML
```

미리보기: `.claude/launch.json` 의 `susiratio` (포트 8809) → `http://localhost:8809/docs/index.html`

## 파서

- 진학어플라이(UTF-8)·유웨이어플라이(EUC-KR) 표를 제목(h태그/caption) 순서로 읽고, `모집인원·지원인원·경쟁률·모집단위·전형` 헤더 이름으로 열을 찾는다(rowspan/colspan 전개, 헤더 공백 무시).
- 모집단위 표의 전형 제목과 전형별 표의 이름이 다른 대학은 build.py의 다단계 정규화(norm/norm2)로 연결한다.
- 대학 자체 페이지 형식은 미지원(수집 현황 탭에 "불가"로 표시).

## 시간대별 자료 보관과 내보내기

- PC 예약 실행(`feed.cmd`)이 매 회차 **전체 대학**을 수집해 `data/snapshots/2027_YYYYMMDD_HHMM.json`으로 남긴다(모집단위 단위 원본). GitHub 러너도 회차마다 `data/latest.json`을 아티팩트(90일)로 남겨 PC가 꺼져 있던 시간대를 보완한다.
- 접수가 끝난 뒤:

```bash
python export_excel.py                     # export/경쟁률_시간대별.xlsx + .csv (전체)
python export_excel.py --hourly            # 열을 1시간 간격으로 솎음
python export_excel.py --region 충남 대전 세종 --out export/충청권
```

- 엑셀 시트: 지원인원 / 경쟁률(행=대학·전형·모집단위, 열=수집시각), 전형별, 대학별. CSV는 분석용 긴 형식(대학,전형,모집단위,시각,모집,지원,경쟁률).
- GitHub 아티팩트를 합치려면 `gh run download`로 받은 폴더를 `--extra 폴더` 로 넘긴다.

## 2027 링크 발굴 방법 (링크가 없는 대학이 생기면)

- **유웨이**: URL 끝의 base64를 풀면 연도 토큰만 다르다. 2026 링크의 디코드 문자열 끝 `J-fTf`를 `J7fTf`로 바꿔 다시 인코딩하면 2027 링크가 된다(2028은 다음 문자로 추정, 검증 필요).
- **진학어플라이**: `Ratio{대학코드4}{순번4}.html`에서 순번이 해마다 10단위로 커진다(대개 끝자리 1). 2026 순번 +10 ~ +400을 순서대로 열어 "2027학년도 수시" 표가 나오는 첫 페이지를 취한다.
- **입학처 홈페이지**: `admissionUrl` 페이지에서 `addon.jinhakapply.com/RatioV1`·`ratio.uwayapply.com` 링크를 긁는다(연도별 링크가 섞여 있어 페이지 본문의 학년도로 확인).
- 대학 자체 페이지도 표에 `모집인원·지원인원·경쟁률` 헤더가 있으면 범용 파서가 처리한다(JS로 숫자를 채우는 페이지는 불가).

## 알려진 한계

- 2027 링크 미확보 대학(수집 현황 탭 참고)과 대학 자체 페이지는 수집하지 못한다.
- 정원외 전형은 대학이 모집인원을 전형 총원으로 반복 표기하거나 rowspan으로 묶는 경우가 있어 `quotaShared`(※)로만 표시한다.
- 작년 최종 연결은 명칭 정규화 매칭이라 이름이 바뀐 전형은 연결되지 않는다.
- GitHub 예약 워크플로는 저장소가 60일간 활동이 없으면 자동 중지된다(접수 기간 이후 중지돼도 무방).
