# AI Code — AI-Powered Code Analysis Tool

> 소스 코드를 분석하여 언어 변환, 리팩토링, 의존성 점검을 도와주는 CLI 도구

프로젝트의 소스 코드를 AI로 분석하여 **언어 변환, 리팩토링, 의존성 점검**을 도와줍니다.
"자동으로 고쳐주는 마법"이 아니라, **개발자가 판단할 수 있는 근거를 제공하는 보조 도구**입니다.

---

## 주요 기능

### 1. 코드 분석 & 리팩토링
- 프로젝트 내 여러 파일을 동시 분석
- 코드 구조 개선 제안
- 언어 변환 지원 (예: Python → TypeScript)

### 2. 의존성 분석
- `requirements.txt`, `package.json` 등 의존성 파일 자동 판별
- 사용되지 않는(unused) 의존성 탐지
- 누락된(missing) 의존성 탐지
- 버전 충돌(conflict) 및 위험한 범위 분석
- 오래된(outdated) 패키지 경고

### 3. 안전한 적용 흐름
- 실제 파일 수정 전 **diff 미리보기 제공**
- 사용자 확인 후에만 파일 적용
- 의존성 파일 포맷 유지 (`-r`, `-e`, marker 등)

> ⚠️ 의존성을 "자동 설치"하지 않습니다. 파일 수정 후 `pip install` / `npm install`은 사용자가 직접 수행합니다.

## 아키텍처

```
┌──────────┐     ┌──────────────┐     ┌───────────┐
│   CLI    │ ──→ │  Agent Core  │ ──→ │  AI/LLM   │
│ (cli.py) │     │  (agent.py)  │     │  Analysis │
└──────────┘     └──────┬───────┘     └───────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │  Core Engine │
                 │  - Parser    │
                 │  - Analyzer  │
                 │  - Differ    │
                 └──────────────┘
```

## 기술 스택

| 구분 | 기술 |
|------|------|
| Language | Python |
| AI | LLM API (코드 분석/리팩토링) |
| Interface | CLI |
| Analysis | AST Parsing, Dependency Graph |

## 프로젝트 구조

```
ai_code/
├── cli.py              # CLI 엔트리 포인트
├── agent.py            # AI 에이전트 코어
├── core/               # 핵심 분석 엔진
│   ├── parser/         # 코드 파서
│   ├── analyzer/       # 의존성 분석
│   └── differ/         # Diff 생성
├── __init__.py
├── requirements.txt
└── .gitignore
```

## 실행 방법

```bash
# 설치
pip install .

# 코드 분석 실행
python cli.py analyze <project_path>

# 의존성 점검
python cli.py deps <project_path>
```

## 테스트

```bash
# pytest 설치
pip install pytest

# 전체 테스트 실행
pytest tests/ -v

# 특정 모듈만 실행
pytest tests/test_chuck.py -v
```

### 테스트 구조

| 파일 | 테스트 대상 |
|------|------------|
| `tests/test_chuck.py` | 텍스트 분할 (chunk_by_chars, chunk_with_line_info) |
| `tests/test_diff.py` | unified diff 생성 (make_unified_diff) |
| `tests/test_file_utils.py` | 파일 읽기/리스팅 (read_file_safe, list_files) |
| `tests/test_refactor_engine.py` | 코드 펜스 제거, 스니펫 병합 |
| `tests/test_openai_client.py` | OpenAI 클라이언트 (mock 사용) |
| `tests/test_deps_analyzer.py` | 텍스트 파일 수집 (collect_text_files) |
