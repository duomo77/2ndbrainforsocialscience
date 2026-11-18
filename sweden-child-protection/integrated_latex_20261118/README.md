# 스웨덴 아동보호 행정: 두 사례 통합 한국어 LaTeX 원고

2026-11-18. 완성 본문은 국문초록, I–IV절과 참고문헌으로 구성된다. 본문은 IV. 실증분석 결과에서 끝난다. CASE 1과 CASE 2의 원자료를 합치거나 새 통합 회귀를 추정하지 않았다.

[심사위원 관점의 재검토](REFEREE_REVIEW_KO.md)를 반영해 조사기간의 미관측 표본, 개편 전 VIND28 격차, 비교집단의 중첩과 분할별 추론을 설명했다. [그림 보충자료 PDF](supplement/supplement.pdf)는 290개 시군의 2015·2024년 해외 출생 주민 비중, 세 대도시권 확대 지도, 단면·패널 비교 및 VIND28 추이와 DML 민감도를 담는다. [지도 출처와 그림 재생성 방법](supplement/README.md)을 함께 제공한다.

본문에서도 같은 그림을 1–5번으로 읽을 수 있다. 전국 지도는 자료 절에, 대도시권 지도와 단면·패널 그림은 CASE 1 결과에, VIND28 추이와 DML 민감도는 CASE 2 결과에 배치했다. 본문은 시군 비중의 변화, 그림별 분모, 결측, 자료 분할을 각 그림의 해석에 연결한다.

최신 해석·스토리라인 개정은 [주장 범위 정리](CLAIM_SCOPE_KO.md)에 기록했다. 초록·서론·증거 상태·두 사례 요약·마지막 답변을 일관되게 고쳤다. 고비중 집단의 높은 충족률과 그 격차의 축소를 구분하고, 263개 표본에서 고비중 충족 건수가 유지됨을 설명한다. 새 모형이나 유의한 사양으로 교체하지 않았으며 기존 원자료·정제자료·결과 37개 파일의 바이트 보존을 확인했다.

최신 [전반 검수 기록](MANUSCRIPT_REVIEW_KO.md)에 초록의 표본 귀속 오류, 주요 회귀 재계산, 결측 범위 대조 및 남은 근거의 한계를 정리했다. CASE 1의 원자료 수집과 확장 분석은 [상위 연구 폴더](https://github.com/duomo77/2ndbrainforsocialscience/tree/main/sweden-child-protection)에서 확인할 수 있다.

공식 VIND28 원본 Excel·SCB 원응답을 포함한 전체 자료는 이 폴더의 `Sweden_ChildProtection_Integrated_LaTeX_KO_20261118.zip`에 있다. GitHub의 개별 파일은 코드와 결과 검토용이며, 실행에는 ZIP을 풀어 사용한다.

## 파일

- `main.tex`: 본문 LaTeX 원본. 같은 프로젝트의 `supplement/figures/`에 있는 PNG 그림 5개를 읽는다.
- `main.pdf`: 위 원본을 Tectonic 0.17.0으로 컴파일한 23쪽 PDF. III절은 분석 설계를, IV절은 추정과 민감도 점검을 담는다.
- `build_manuscript.py`: 문장과 표를 원본으로 출력하는 Python 스크립트. 표준 라이브러리만 필요하다. 실행은 LaTeX 파일을 다시 작성하며, 계량모형을 재추정하지 않는다.
- `case1_table_manifest.json`: 제공 CASE 1 26쪽 원고와 대조한 기존 결과표.
- `table_transcription.json`: 통합 원고 표 20개의 수치와 주석. 기존 보고치와 직접 재추정치를 구분한다.
- `input_provenance.json`: 실제 사용한 두 입력 PDF의 파일명, 크기, SHA-256.
- `data/`: CASE 1의 기존 2024년 자료와 2022–2025년 패널을 바이트 그대로 복사한 CSV.
- `reproduction/`: CASE 2 공식 Excel·SCB 원응답, 290개 시군 분석자료, 다운로드/정제/새 DML 코드, 실행 결과, OOF 예측, 폴드, 환경과 감사 기록. [자세한 재현 설명](reproduction/README.md)을 참조한다.
- `reproduction_update.py`: 실제 실행 결과 CSV에서 논문 비교표를 생성하고 설명을 갱신한다.
- `interpretation_revision.py`: 검증된 결과에 맞춰 초록·서론·결과 해석과 마지막 답변을 재작성한다.
- `CLAIM_SCOPE_KO.md`: 관측 사실, 조건부 추정, 허용되지 않는 인과·개인 주장을 대응시킨 검토 문서.
- `verify_interpretation.py`: 기존 경험적 파일의 보존과 본문 구조 확인. 결과는 `reproduction/results/interpretation_preservation.json`에 있다.
- `verify_manuscript.py`: CASE 1 기본 단면·고정효과 회귀와 CASE 2 집계·결측·DML 표 확인. 실행에는 pandas, numpy, statsmodels가 필요하다.
- `main.log`, `qa/verification.json`: 컴파일과 PDF 점검 기록.
- `SHA256SUMS.json`: 배포 파일 체크섬.

## 컴파일

Windows에서 Times New Roman, Batang(바탕), Malgun Gothic(맑은 고딕) 글꼴을 사용했다. 한글 글꼴이 없는 환경에서는 `main.tex`의 글꼴명을 설치된 한글 글꼴명으로 바꿔야 한다. pdfLaTeX 대신 XeLaTeX 또는 Tectonic을 사용한다.

```powershell
cd <압축을 푼 폴더>
tectonic --keep-logs main.tex
```

또는 TeX Live/MiKTeX에 XeLaTeX와 ko.TeX가 설치되어 있으면:

```powershell
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

이 작업에서 실제로 실행한 명령은 프로젝트 폴더에서 `../tex_runtime/tectonic.exe --keep-logs main.tex`였다. 실행 파일과 TeX 캐시는 배포 ZIP에 포함하지 않았다. 컴파일러 공식 배포: https://github.com/tectonic-typesetting/tectonic/releases/tag/tectonic%400.17.0 . 최초 실행에는 TeX 번들 다운로드를 위한 인터넷 연결이 필요할 수 있다.

표 전사와 문장을 수정한 뒤 원본을 재생성하려면:

```powershell
python build_manuscript.py
tectonic --keep-logs main.tex
```

일반적인 문장 편집은 `main.tex`에서 직접 하면 된다. 이후 빌더를 다시 실행하면 그 직접 수정은 덮어써진다.

## 증거 범위와 출처

실제 입력은 `Sweden_ChildProtection_Policy_Draft_KO.pdf`(26쪽)와 `Sweden_VIND28_Argument_Revised_20261111.pdf`(18쪽)다. 같은 제목의 후속 32쪽 개정본으로 대체하지 않았다. 입력 PDF 자체는 이 ZIP에 중복 배포하지 않으며 체크섬으로 식별한다.

CASE 1은 제공 PDF와 기존 결과표/자료를 활용했고 새 추정은 실행하지 않았다. CASE 2는 2026-11-18 공식 원자료를 직접 내려받아 표본·충족 건수·전환을 재구축하고, 191개 시군·21개 주에서 DML-DID를 독립 재추정했다. 기존 실행 코드를 찾지 못했으므로 원래 학습기·폴드·설정을 그대로 실행한 정확 재현은 아니다. 기존 DR-DID·SDID와 원고의 추가 민감도 보고치는 이번에 재추정하지 않았으며 별도로 표시한다.

새 주 DML 추정은 2025−2023년 +9.24%p [−16.18,34.67], 2026−2023년 −11.21 [−35.83,13.41], 2026−2025년 −18.43 [−40.09,3.22]다. 세 구간은 모두 0을 포함한다. 표본과 집계값의 일치가 DML 계수·유의성의 일치를 보장하지는 않았다. 새로운 수치와 방법 설정은 `reproduction/results/`에 있다.

원고에 인용한 원자료 기관:

- Kolada API 및 KPI 정의: https://api.kolada.se/v3/docs ; https://www.kolada.se/verktyg/fri-sokning/
- SCB 통계 데이터베이스: https://www.statistikdatabasen.scb.se/
- SCB TAB4824 공식 bulk 경로: https://www.statistikdatabasen.scb.se/Resources/PX/bulk/ssd/sv/TAB4824_sv.zip
- Socialstyrelsen 공개 비교·보호시설 제도 자료: https://www.socialstyrelsen.se/

CASE 1의 Kolada·SCB 전체 다운로드를 반복하지 않았다. CASE 2에서는 Socialstyrelsen 2026년 공식 Excel과 SCB TAB4823·TAB1121의 2015년 관측을 새로 확보했다. 정확한 URL·POST·UTC·체크섬은 `reproduction/results/`에 있다. 구체적인 방법 문헌은 PDF 참고문헌에 수록했다.

지역 집계 조사기간은 개별 이주 아동의 보호시설 배치 지연이 아니며, VIND28의 절차 충족은 처리기간이 아니다. 두 결과를 동일한 지연 척도로 합치지 않는다. DID 조정과 DML은 평행추세·중첩 및 측정동등성을 보장하지 않는다. 관측 결과를 인과적 정책효과로 해석하지 않았다. 새 DML 표는 주 군집 영향함수·t(20) 추론이며, 기존 보고 구간의 추론 방식과 구분한다.

## 확인

추가 점검은 `reproduction/SECOND_AUDIT_KO.md`에 있다. 동일 폴드에서 성향점수·결과 모형을 따로 바꾸고, 폴드 배정만 10회, 학습기 난수만 5회 바꾸었다. 2026−2025년은 폴드 10개 모두 음수·8개 p<.05였고 2026−2023년은 모두 비유의였다. 이전 한 분할의 비유의를 신호 부재로 일반화하지 않으며, 유의한 분할을 골라 주 결과로 대체하지도 않았다.

Tectonic 컴파일 성공. 23쪽 전체를 렌더링하고 본문 그림 5개와 범례, 번호 및 교차참조를 확인했다. 추출 텍스트에 미치환 자리표시자나 대체문자(�)는 없었고, Overfull 및 Missing character 경고도 없었다. 바탕체의 일부 굵은꼴·기울임꼴 대체와 Underfull 경고는 로그에 남아 있다. Windows 글꼴 의존성으로 운영체제에 따라 줄바꿈과 쪽수가 달라질 수 있다.
