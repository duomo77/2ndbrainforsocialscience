# Research Operating System (ROS)

ROS는 논문, 강의 스크립트, 데이터셋, 수식, 연구 메모를 분석해 Obsidian용 Markdown 지식 노트로 변환하는 React/TypeScript 웹 앱입니다. Python 코어는 FastAPI 백엔드로 실행됩니다.

## 빠른 시작

### macOS / Linux / Windows

```bash
python3 -m pip install -r requirements.txt
npm install
npm run dev
```

브라우저에서 `http://127.0.0.1:5173/`을 엽니다. API 키가 없어도 `demo-local` 모델로 로컬 데모 분석을 실행할 수 있습니다.

업로드는 지원 확장자만 허용하며 요청당 50 MiB로 제한됩니다. 생성 노트에는 `ai_generated`, `human_verified`, `evidence_status`, `citation_status`, `provenance`가 기록되므로 AI 결과와 인간 검증 결과를 구분해 검토하세요.

백엔드만 실행하려면:

```bash
python3 main.py
```

React 앱을 정적 파일로 빌드하려면:

```bash
npm run build
python3 main.py
```

## 기본 사용 순서

1. 왼쪽 패널에서 입력 유형, 제목, 모델, 선택적 API 설정을 입력합니다.
2. 파일을 선택하거나 텍스트를 직접 입력합니다.
3. `Analyze`를 누릅니다.
4. 오른쪽 결과 패널에서 생성된 Markdown을 검토합니다.
5. 하단 Runtime Events에서 보안 검증, RAG, 그래프 업데이트 흐름을 확인합니다.

## 입력 유형

| 탭 | 지원 입력 | 용도 |
|---|---|---|
| Paper | `.pdf`, `.txt`, `.md`, `.tex` | 논문 기여, 식별 전략, 가정, 결과, 확장 아이디어 분석 |
| Script | `.txt`, `.md`, `.srt`, `.vtt` | 강의, 세미나, 회의록, 팟캐스트 전사 분석 |
| Dataset | `.csv`, `.tsv`, `.xlsx`, `.xls` | 변수 구조, 패널 구조, 연구 설계 기회 분석 |
| Equation | 직접 입력 | 수식의 의미, 가정, 연결 개념 분석 |
| Notes | `.txt`, `.md`, `.rst` 또는 직접 입력 | 연구 메모와 아이디어를 구조화된 노트로 변환 |

실제 음성 파일인 `.mp3`, `.wav`, `.m4a`, `.flac` 등은 먼저 텍스트, SRT 또는 VTT로 전사해야 합니다.

## 교수 연구 흐름 예시

### 논문 읽기

1. `Paper` 탭에서 PDF를 선택합니다.
2. 제목과 저자가 자동으로 채워졌는지 확인합니다.
3. 필요하면 저널, 연도, Zotero 링크를 입력합니다.
4. 분석 결과에서 식별 전략, 핵심 가정, 방법론적 약점, 후속 연구 질문을 검토합니다.

### 강의 준비

1. `Script` 탭에서 강의 원고 또는 전사 파일을 선택합니다.
2. 유형을 `lecture`로 선택하고 강의명과 날짜를 확인합니다.
3. 결과를 Obsidian에 저장해 강의별 핵심 개념과 연결 노트를 축적합니다.

### 데이터셋 검토

1. `Dataset` 탭에서 CSV, TSV 또는 Excel 파일을 선택합니다.
2. 데이터셋 이름과 분석 목적을 입력합니다.
3. 결과에서 관측 단위, 패널 구조, 처리 변수 후보, 고정효과 후보를 검토합니다.

## LLM Provider 설정

설정 창에서 Provider를 선택하면 Base URL과 추천 모델 목록이 바뀝니다. 모델 입력란은 직접 편집할 수 있으므로 프리셋에 없는 새 모델도 사용할 수 있습니다.

지원 경로:

- OpenAI
- Azure OpenAI
- Anthropic 호환 endpoint
- Groq
- DeepSeek
- Qwen / DashScope
- Zhipu GLM
- Moonshot Kimi
- MiniMax
- Baidu ERNIE
- SiliconFlow
- 01.AI

Provider마다 실제 사용 가능한 모델과 API 권한이 다를 수 있으므로 설정 창의 `연결 테스트`를 먼저 실행하세요.

## Obsidian 저장

분석 완료 후 자동 저장을 켜면 ROS가 입력 유형과 주제에 따라 노트를 분류합니다.

```text
YourVault/
  _INDEX.md
  Papers/
    Econometrics/
    MachineLearning/
    Finance/
  Transcripts/
  Datasets/
  Notes/
  Equations/
```

기존 파일을 덮어쓸 때는 백업 파일을 생성합니다. 결과 Markdown은 `[[WikiLink]]`를 사용해 지식 그래프에 연결됩니다.

백업은 볼트의 숨김 `.ros_backups/` 아래에 보관되며, 볼트 밖 경로와 symlink를 통한 저장은 차단됩니다. 자동 저장 실패는 분석 성공으로 처리되지 않습니다.

## 문제 해결

- 앱이 시작되지 않으면 `python main.py`로 실행해 오류 메시지를 확인하세요.
- API 연결 실패 시 API Key, Base URL, Model 이름을 확인하세요.
- PDF 텍스트가 비어 있으면 스캔 PDF일 수 있습니다. OCR 후 다시 시도하세요.
- 음성 파일은 먼저 전사해야 합니다.
- Obsidian 저장이 되지 않으면 볼트 경로와 쓰기 권한을 확인하세요.

## 테스트

```powershell
python -m pytest -q
```

설정 파일은 `~/.econometric_wiki/config.json`, 연구 메모리 파일은 `~/.ros_memory/` 아래에 저장됩니다.
