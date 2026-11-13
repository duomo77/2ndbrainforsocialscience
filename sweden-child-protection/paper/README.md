# 한국어 정책논문 초안

최종 원고는 `output/Sweden_ChildProtection_Policy_Draft_KO.docx`, 같은 이름의 PDF 및 Markdown이다. 제목은 **이주배경 인구가 많은 지역의 조사는 더 오래 걸리는가**이다.

사용자가 제시한 22쪽 참고 원고의 판형(448 × 655 pt), 국문초록·번호 본문·학술 표·참고문헌·부록·영문초록 구성을 참고했다. 학회의 정식 투고규정 자체를 인증한 문서는 아니다. 저자명과 소속은 기입하지 않았다. 참고 원고의 VIND28와 스톡홀름 구역 추정치를 본고의 새 실증 결과로 전재하지 않았다.

본문은 11개 절, 표 13개와 모형 비교 그림 1개, 편집 가능한 Word 수식 6개로 구성된다. 표는 분석 CSV에서 생성한다. `manuscript_source_ko.md`는 작성한 본문이며 `build_paper.py`가 표와 참고문헌을 결합해 DOCX와 완전한 Markdown을 만든다.

```powershell
# python-docx가 있는 Python 환경
python build_paper.py
# Windows Microsoft Word로 실제 DOCX를 PDF로 출력
.\export_word_pdf.ps1
# pdf2image, pypdf, Pillow 및 Poppler가 있는 환경
python qa_render.py
```

DOCX 작성은 Codex 번들 Python 3 환경과 python-docx를 사용했다. 기본 `render_docx.py`는 Windows 환경에 LibreOffice가 없어 실패했으므로, 설치된 Microsoft Word의 비표시 COM PDF 출력 기능으로 실제 DOCX를 렌더링했다. 원고는 읽기 전용으로 열어 PDF를 내보낸 뒤 문서를 닫고 Word 프로세스를 정상 종료했다. PDF의 모든 쪽을 Poppler로 이미지화해 한글, 표, 수식 및 페이지 넘김을 확인한다. 임시 렌더링 이미지와 참고자료 텍스트는 배포본에 포함하지 않는다.

2024년 보호시설 개편의 제도적 배경은 정부 발표와 당시 사회보건청 안내를 다시 확인했다. 실증 결과는 취득 시점의 자료 스냅샷에 한정한다. 논문 표의 반올림 전 수치와 모든 민감도는 상위 `results/` 및 분석 스크립트에 있다.

2026년 11월 개정의 추가 추론과 측정시점 검증은 `../UPGRADE_NOTES_KO.md`를 참조한다.

VIND28을 출발점으로 삼은 후속 문체·구성 개정의 출처와 범위는 `../NARRATIVE_REVISION_KO.md`에 기록했다.


2026년 11월 14일 세 관점 검토와 문체·주장 개정은 `../EXPERT_REVIEW_KO.md`, 공개 문체 코드의 적용·경고는 `../tools/README.md`에 기록했다. 별도 데이터 해설은 `output/SUPPLEMENTARY_Data_Guide_KO.pdf`와 DOCX다.

```powershell
python paper/build_supplementary.py
powershell -NoProfile -ExecutionPolicy Bypass -File paper/export_supplementary_pdf.ps1
python paper/render_revision.py SUPPLEMENTARY_Data_Guide_KO
```

위 명령은 연구 패키지 루트에서 실행한다. Windows Microsoft Word와 Poppler, 문서 Python 의존성이 필요하다. 핵심 예제 수치는 `results/supplementary_worked_example.csv`에 있다.
