# 한국어 문체 검토에 사용한 도구

[im-not-ai-kiro](https://github.com/Gaeduck-0908/im-not-ai-kiro) 커밋 `a8e268aae6097ce5146e588ca6921002380992bf`의 MIT 라이선스 소스를 별도 ZIP에 보존했다. 전역 설치나 Kiro CLI 실행은 하지 않았다. ZIP의 LICENSE와 원저작자 표시를 유지했다.

압축을 푼 뒤 Python으로 `.kiro/scripts/verify_gates.py --before ../paper/style_audit/01_input.txt --after ../paper/style_audit/final.md --genre abstract --json`을 실행할 수 있다. 상대 경로는 실제 압축 해제 위치에 맞춘다. 진단, 수치·인용 보존 검사, 남은 경고와 후속 내용 수정은 `paper/style_audit/`에 있다.

문체 단계의 문자 변경률은 0.49%다. 수치·인용·격식·서법 보존 검사는 통과했지만 쉼표 관련 두 지표의 목표 미달로 최종 종합 판정은 WARN이다. 직접 대조 검토에서 추정 조건과 학술적 한계를 보존하기로 결정했다. 이 값은 학술적 주장·제목 수정의 변경률이 아니며 저자 판별 확률도 아니다.
