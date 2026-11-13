# 스웨덴 대도시권 아동보호 행정 연구

스웨덴 51개 대도시권 지방정부의 공식 자료를 확보·검증하고, 이주배경 인구구성과 사회복지 조사기간을 분석한 재현 패키지와 한국어 정책논문 초안입니다.

- [한국어 정책논문 PDF](paper/output/Sweden_ChildProtection_Policy_Draft_KO.pdf)
- [편집 가능한 Word 원고](paper/output/Sweden_ChildProtection_Policy_Draft_KO.docx)
- [완전한 Markdown 원고](paper/output/Sweden_ChildProtection_Policy_Draft_KO.md)
- [자료와 분석 실행 안내](ANALYSIS_README.md)
- [영향력과 일차차분 진단](results/two_parent_influence_report.md)
- [2024년 51개 지방정부 데이터](data/metro_51_2024.csv)
- [2022–2025년 패널](data/metro_51_panel.csv)
- [도구변수 가능성 검토](results/iv_audit.md)
- [전체 공개 패키지 ZIP](sweden_child_protection_public_bundle.zip)

## 핵심 결과

2024년 평균 조사기간은 44개 지방정부에서 관측되며 평균 100.70일입니다. 지역 간 단면 관계는 작고 정밀하지 않습니다. 일부 지역 내 변화의 계수는 양수이나 영향력이 큰 지방정부와 기간에 민감합니다. 양부모 해외 출생 비중의 기본 패널 계수는 1%포인트당 6.70일이며, 가장 영향력이 큰 세 지방정부를 함께 제외하면 3.21일로 낮아집니다. 인접 연도 차분은 정밀하지 않지만 2022–2024년 양 끝 시점 차분은 더 강한 양의 관계를 보입니다.

이 결과는 지방정부 수준의 사회복지 조사기간에 관한 연관성입니다. 이주배경 아동 개인의 보호 지연, 가정폭력 사건의 대기기간이나 시설 입소 지연을 측정하거나 인과효과를 식별한 결과가 아닙니다. 검증된 도구변수가 없어 2SLS는 수행하지 않았습니다.

## 재현

```bash
python -m pip install -r requirements.txt
python analysis.py
python panel_followup.py
python panel_influence.py
python verify.py
```

공식 원자료가 포함되어 있어 분석부터는 오프라인 실행이 가능합니다. 자료를 새로 취득하려면 `retrieve.py`, `fetch_scb.py`를 먼저 실행합니다. Word 원고의 생성·출력은 [paper 안내](paper/README.md)를 참고하세요.

## 공개본 처리

공식 응답의 관측값과 파일 본문은 그대로 보존했습니다. 공개가 불필요한 HTTP 쿠키 헤더와 개인 컴퓨터 경로는 로그에서 제거했으며, 변경 내역은 `PUBLICATION_NOTES.json`에 있습니다. 임시 렌더링 이미지와 참고문서 추출 텍스트는 배포 대상이 아닙니다. 원자료와 제3자 문헌의 이용 조건은 각 원출처를 따릅니다.
