# 지도와 실증 그림 보충자료

`supplement.pdf`는 지도 2장과 결과 그림 3장을 담는다. PNG와 지도·그림을 만드는 코드 및 자료 CSV를 함께 제공한다. 그림 재생성에 사용하는 공식 원응답과 경계 ZIP은 상위 폴더의 전체 배포 ZIP 안 `supplement/raw/`에 있다. 코드 결합에서는 네 자리 시군 코드를 문자열로 읽는다.

| 그림 | 내용 | 자료 |
|---|---|---|
| S1 | 스웨덴 290개 시군의 2015년·2024년 해외 출생 주민 비중. 두 시점에 공통 색상 구간 사용 | 보존한 Kolada N02926 연도별 공식 응답 |
| S2 | 세 대도시권의 해외 출생 주민 비중, 0–17세 해외 배경 비중, 평균 조사기간 | 통합 원고의 51개 시군 CSV. 조사기간 미관측 7개는 빗금 표시 |
| S3 | 같은 40개 시군의 단면·패널 부분 관계 | CASE 1의 시군·연도별 자료와 고정효과 회귀 잔차 |
| S4 | VIND28 장기패널의 응답 추이와 2025–2026년 연결표본 | Case 2 공식 응답 정제자료. 2024년은 191개 장기표본 정의에서 제외 |
| S5 | 독립 DML 주 추정, 추가 폴드별 점, 기존 보고치 | 저장된 DML 비교·민감도 CSV |

지도 경계는 [SCB Digitala gränser](https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/digitala-granser/)의 [공식 ZIP](https://www.scb.se/contentassets/3443fea3fa6640f7a57ea15d9a372d33/shape_svenska_260225.zip)에서 지방정부 레이어를 사용했다. SWEREF 99 TM 좌표계이며, 현재 공개된 동일 도식 경계를 두 시점에 적용했다. SCB 게시 페이지에 표시된 이용 조건은 CC0다. 시군 경계 자체의 변화나 법적 경계, 공간효과를 분석하지 않는다.

N02926은 전체 주민을 분모로 한다. 지도 범례는 하한을 포함하고 상한을 제외하는 구간이며 최상단 경계를 포함한다. 2015년과 2024년 자료의 원 응답은 기존 CASE 1 수집 때 내려받은 파일이다. [2015년 API](https://api.kolada.se/v3/data/kpi/N02926/year/2015) · [2024년 API](https://api.kolada.se/v3/data/kpi/N02926/year/2024). 지도 결합, 관측 수와 원파일 SHA-256은 `data/map_validation.json`에 있다.

그림을 생성하려면 통합 원고 폴더에서 `python supplement/make_figures.py`를 실행한다. Python에는 matplotlib, numpy, pandas, pyshp, statsmodels가 필요하며 한글 글꼴은 Malgun Gothic, Noto Sans CJK KR 또는 NanumGothic을 사용한다. `supplement/`에서 `tectonic --keep-logs supplement.tex`를 실행하면 PDF가 생성된다. LaTeX 글꼴과 상세 조건은 상위 README에 있다.
