# Research Operating System (ROS) v2.0

> **경제학 연구자를 위한 지식 외재화 엔진**
> *"Think like Andrej Karpathy organizing compressed cognition."*
<img width="1587" height="1027" alt="image" src="https://github.com/user-attachments/assets/cd83aac2-c6bf-41f9-b114-be5a76de3167" />

---

## 빠른 시작

```bash
# 1. 압축 해제
unzip econometric-wiki-compiler.zip && cd econometric-wiki

# 2. 의존성 설치 (1회)
pip install -r requirements.txt

# 3. 실행
python main.py
```

**Windows 원클릭 EXE 빌드:**
```
build_exe.bat 더블클릭 → dist/ROS.exe 생성
```

---

## 핵심 철학

ROS는 단순 요약 도구가 아닙니다. 연구자의 인지를 **외재화·구조화·연결·진화**시키는 시스템입니다.

- 모든 노트는 **Atomic Reusable Intellectual Primitive**로 생성됩니다
- 선형 요약 대신 **의미론적 연결(Semantic Linking)**을 우선합니다
- 분석할수록 **지식 그래프가 축적**되고 더 정확해집니다

---

## 지원 입력 유형

| 탭 | 입력 형식 | 분석 결과 |
|----|-----------|-----------|
| 📄 논문 | PDF, 텍스트 | Causal DAG, 식별 전략, 추정식, CATE |
| 🎙 스크립트 | TXT, MD (강의/회의록) | 핵심 개념 추출, 지식 노드 생성 |
| 📊 데이터셋 | CSV, Excel | 패널 구조 추론, 처치변수 후보, FE 제안 |
| ✏️ 수식 | 직접 입력 | LaTeX 파싱, 경제학적 해석, 연결 개념 |
| 📝 노트 | 자유 텍스트 | Atomic note 변환, 위키 연결 |

---

## Obsidian 볼트 구조

```
YourVault/
└── Papers/
    ├── 📐 Econometrics/
    ├── 🤖 MachineLearning/
    ├── 📊 GeneralEconomics/
    ├── 👷 LaborEconomics/
    ├── 💹 Finance/
    ├── 🏥 HealthEconomics/
    ├── 🏛 PublicEconomics/
    ├── 🌍 DevelopmentEconomics/
    ├── 🏭 IndustrialOrganization/
    ├── 📈 Statistics/
    ├── 📝 WorkingPapers/
    ├── 🎙 Transcripts/
    ├── 📊 Datasets/
    └── _INDEX.md   ← MOC 자동 생성
```

---

## 지원 API Provider

**글로벌:** OpenAI, Azure OpenAI, Anthropic (호환), Groq

**중국:**

| Provider | 대표 모델 |
|----------|-----------|
| DeepSeek (深度求索) | deepseek-v4-pro, deepseek-chat |
| Qwen / 通义千问 | qwen3-72b, qwen-max |
| Zhipu GLM (智谱AI) | glm-4-plus, glm-z1-plus |
| Moonshot Kimi | kimi-k2.6, moonshot-v1-128k |
| MiniMax | MiniMax-Text-01 |
| Baidu ERNIE | ernie-4.5-turbo |
| SiliconFlow | DeepSeek-V3, Qwen3-235B |
| 01.AI / 零一万物 | yi-large |

---

## EXE 빌드 방법

### Windows
```
build_exe.bat 더블클릭
→ dist/ROS.exe 생성 (단일 파일, ~140MB)
```

### macOS / Linux
```bash
bash build_exe.sh
→ dist/ROS 생성
```

---

## 알려진 버그 수정 (v2.0)

| 버그 | 원인 | 상태 |
|------|------|------|
| KeyError: 'D, Y' | 프롬프트 {D, Y} → Python .format() 충돌 | ✅ 수정 |
| 스트리밍 토큰 누락 | openai SDK 2.x .stream() 이벤트 구조 변경 | ✅ 수정 |
| qwen3 thinking 토큰 혼입 | reasoning_content 필드 미처리 | ✅ 수정 |

---

## 파일 구조

```
econometric-wiki/
├── main.py
├── requirements.txt
├── ROS.spec              # PyInstaller 빌드 설정
├── build_exe.bat / .sh
├── core/
│   ├── config.py         # 설정 영속화 (Config 클래스)
│   ├── classifier.py     # 저널→주제 자동 분류
│   ├── memory.py         # 장기 메모리 & 지식 그래프
│   ├── parsers.py        # 멀티소스 파서
│   ├── ros_engine.py     # ROS LLM 분석 엔진
│   ├── obsidian_sync.py  # Obsidian 볼트 동기화
│   └── worker.py         # 백그라운드 워커
└── ui/
    ├── main_window.py    # 메인 윈도우 (다크 테마)
    ├── settings_dialog.py
    ├── profile_dialog.py # 연구자 프로필 편집
    ├── input_panel.py
    ├── result_panel.py
    └── vault_panel.py
```

설정 파일: `~/.econometric_wiki/config.json`
메모리/그래프: `~/.econometric_wiki/memory.json`
