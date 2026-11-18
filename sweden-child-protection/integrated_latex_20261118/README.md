# 스웨덴 아동보호 행정: 두 사례 통합 한국어 LaTeX 원고

2026-11-18. 완성 본문은 국문초록, I–IV절과 참고문헌으로 구성된다. 본문은 IV. 실증분석 결과에서 끝난다. CASE 1과 CASE 2의 원자료를 합치거나 새 통합 회귀를 추정하지 않았다.

## 파일

- `main.tex`: 독립적으로 컴파일할 수 있는 전체 LaTeX 원본.
- `main.pdf`: 위 원본을 Tectonic 0.17.0으로 컴파일한 15쪽 PDF.
- `build_manuscript.py`: 문장과 표를 원본으로 출력하는 Python 스크립트. 표준 라이브러리만 필요하다. 실행은 LaTeX 파일을 다시 작성하며, 계량모형을 재추정하지 않는다.
- `case1_table_manifest.json`: 제공 CASE 1 26쪽 원고와 대조한 기존 결과표.
- `table_transcription.json`: 통합 원고 표 17개의 수치 및 주석 전사 기록.
- `input_provenance.json`: 실제 사용한 두 입력 PDF의 파일명, 크기, SHA-256.
- `data/`: CASE 1의 기존 2024년 자료와 2022–2025년 패널을 바이트 그대로 복사한 CSV. CASE 2 원시 패널은 제공되지 않았으므로 만들지 않았다.
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

CASE 1은 제공 PDF와 기존 결과표/자료를 활용했고 새 추정은 실행하지 않았다. CASE 2의 DID·DR-DID·DML-DID·SDID, 구간, 전환표, 표본 확장 및 민감도 수치는 제공 PDF의 보고치다. 이번 작업은 CASE 2 원시자료, 코드, 교차적합 폴드와 부트스트랩을 재현·검증한 작업이 아니다. 수치 전사 점검과 통계 추정의 독립적 재현을 구분한다.

원고에 인용한 원자료 기관:

- Kolada API 및 KPI 정의: https://api.kolada.se/v3/docs ; https://www.kolada.se/verktyg/fri-sokning/
- SCB 통계 데이터베이스: https://www.statistikdatabasen.scb.se/
- SCB TAB4824 공식 bulk 경로: https://www.statistikdatabasen.scb.se/Resources/PX/bulk/ssd/sv/TAB4824_sv.zip
- Socialstyrelsen 공개 비교·보호시설 제도 자료: https://www.socialstyrelsen.se/

이 통합 편집에서 위 기관의 API 전체를 다시 다운로드한 것은 아니다. 구체적인 방법 문헌은 PDF 참고문헌에 수록했다.

지역 집계 조사기간은 개별 이주 아동의 보호시설 배치 지연이 아니며, VIND28의 절차 충족은 처리기간이 아니다. 두 결과를 동일한 지연 척도로 합치지 않는다. DID 조정과 DML은 평행추세·중첩 및 측정동등성을 보장하지 않는다. 관측 결과를 인과적 정책효과로 해석하지 않았다. 유의확률과 구간은 원고의 추론 방식 그대로이며 새 검정의 결과가 아니다.

## 확인

Tectonic 컴파일 성공. 15쪽 전체의 렌더링을 검토했으며, 추출 텍스트에서 미치환 자리표시자나 대체문자(�)는 없었다. Overfull 및 Missing character 경고는 없었다. 바탕체의 일부 굵은꼴/기울임꼴 대체와 표의 Underfull 경고는 로그에 남아 있다. Windows 글꼴 의존성이 있으므로 다른 운영체제에서 줄바꿈과 쪽수는 달라질 수 있다.
