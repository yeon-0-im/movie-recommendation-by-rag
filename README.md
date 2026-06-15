# ㅇㅎㅊㅊ — 영화 추천 RAG 챗봇

> "영화는 언제 만나는지도 중요하다"

지금 내 상황과 감정에 딱 맞는 영화를 대화로 추천받는 챗봇 형태의 서비스입니다.
"퇴근하고 너무 지쳤어", "밖에 비가 와서 영화가 보고싶어"처럼 구체적인 상황을 말하면, RAG 파이프라인이 1,930편의 영화 중 가장 어울리는 영화를 골라줍니다.

---

## 기획 의도

OTT 플랫폼에 접속해서 마음에 드는 영화를 찾는 데만 영화의 러닝타임 정도의 시간을 쓴 경험이 있다.

기존 영화 추천 알고리즘은 협업 필터링, 콘텐츠 기반 필터가 주를 이루며, 유저 간 유사도와 아이템 간 유사도를 기반으로 작동한다. 그러나 추천된 영화가 선뜻 손이 가지 않는 이유는 **때에 따라 보고 싶은 영화가 달라지기 때문**이다. 도저히 웃을 기분이 아닐 땐 아무리 재밌다는 영화도 손이 안 가는 것처럼.

이 프로젝트는 그 지점에서 출발했다. 사용자의 리뷰를 기반으로 데이터를 정제하고, 영화의 감정·상황·분위기를 구조화해 지금 이 순간의 나에게 어울리는 영화를 추천하는 시스템을 구축했다.

좋은 영화도 기분에 따라 마음에 들지 않을 수 있고, 평점이 낮은 영화도 그날따라 마음에 들 수 있다. 영화를 좋아하는 개발자로서 다양한 영화들이 더 많은 사람에게 소개되고, 예상치 못한 영화를 발견하는 기쁨을 줄 수 있으면 좋겠다.

---

## 핵심 포인트

- **상황 기반 추천** — 감정·상황·분위기를 자연어로 말하면 맞춤 추천
- **대화형 필터링** — "한국 영화 빼고", "넷플릭스 것만"처럼 추가 조건을 누적 적용
- **영화 질문 응답** — 추천된 영화에 대해 바로 질문 가능 ("이건 어떤 영화야?")
- **4-Pillar 태깅** — Context / Tone / Sensory / Load 축으로 영화를 분류해 정교한 매칭

---

## 기술 스택

| 영역 | 기술 |
|---|---|
| Backend | Django REST Framework |
| Frontend | Next.js |
| Vector DB | ChromaDB |
| Embedding | BGE-M3 (HuggingFace) |
| Orchestration | LangGraph |
| LLM | Gemini 2.5 Flash-Lite |
| Pitch 생성 | Ollama (exaone3.5:2.4b) |

---

## 아키텍처

### LangGraph 파이프라인

```
사용자 입력
    │
    ▼
unified_intent_parser (Gemini)
    │ 의도 분류 + 쿼리 파싱 + 4-Pillar 태그 추출
    │
    ├─ search  ──► overwrite_filter ──┐
    ├─ refine  ──► merge_filter    ──┤
    │  └─ reset ► reset_filter    ──┤
    │                                ▼
    │                          vector_search (ChromaDB)
    │                                │
    │                          score_filter → rerank (4-Pillar 부스트)
    │                                │
    │                          cache_candidates → paginate
    │
    ├─ detail / when_to_watch / movie_question ──► llm_answer
    └─ spoiler / gratitude / not_satisfied    ──► direct_response
```

### 4-Pillar 시스템

영화를 4개 축으로 분류해 사용자 상황과 매칭합니다.

| Pillar | 설명 | 예시 |
|---|---|---|
| **Context** | 시청 상황 | 퇴근길·번아웃, 혼자 보는 영화, 주말 여유 |
| **Tone** | 감정 분위기 | comforting, exhilarating, melancholic |
| **Sensory** | 감각적 특징 | 압도적 미장센, 사운드트랙 맛집 |
| **Load** | 인지부하 | Low-Load, Fast-paced, High-Load |

---

## 프로젝트 구조

```
movie-recommendation-by-rag/
├── backend/                    # Django API 서버
│   ├── config/                 # Django 설정
│   └── movies/
│       ├── rag.py              # LangGraph RAG 파이프라인 핵심
│       ├── models.py           # Movie 모델 (4-Pillar 필드 포함)
│       ├── views.py            # API 엔드포인트
│       └── management/commands/
│           ├── import_movies.py        # CSV → DB 임포트
│           ├── rebuild_vectorstore.py  # ChromaDB 전체 재구축
│           └── tag_4pillar.py          # LLM 기반 4-Pillar 자동 태깅
├── rag_pipeline/               # 데이터 전처리 스크립트
├── ㅇㅎㅊㅊ/                   # UI 목업 및 관리자 대시보드
└── frontend/                   # Next.js 앱 (별도 repo)
```

---

## 시작하기

### 1. 환경 변수 설정 (로컬)

```bash
cp .env.example .env
```

```env
SECRET_KEY=your-django-secret-key
GEMINI_API_KEY=your-gemini-api-key
TMDB_API_KEY=your-tmdb-api-key
DB_NAME=ohcc_db
DB_USER=postgres
DB_PASSWORD=your-db-password
DB_HOST=localhost
```

### 2. 백엔드 설치 및 실행

```bash
pip install -r requirements.txt
cd backend
python manage.py migrate
python manage.py runserver 8080
```

### 3. 데이터 구축

```bash
# CSV 데이터 임포트
python manage.py import_movies --csv ../data/movie_db.csv

# ChromaDB 벡터스토어 구축
python manage.py rebuild_vectorstore

# 4-Pillar 자동 태깅 (Gemini 필요)
python manage.py tag_4pillar --limit 50 --dry-run
```

### 4. Ollama (pitch 생성용)

```bash
ollama serve
ollama pull exaone3.5:2.4b
```

---

## API 엔드포인트

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/chat/converse/` | 대화형 추천 (LangGraph) |
| POST | `/api/chat/followup/` | 시맨틱 재검색 |
| GET | `/api/movies/<id>/` | 영화 상세 정보 |
| GET | `/api/movies/random/` | 랜덤 영화 |
| GET | `/api/admin/overview/` | 대시보드 KPI |
| GET | `/api/admin/movies/` | 영화 풀 현황 |
| GET | `/api/admin/taxonomy/` | 4-Pillar 분포 |

---

## 관리자 대시보드

```
http://localhost:8080/admin/
```

- 전체 현황 KPI (추천 완료율, 응답 시간 등)
- 영화 풀 관리
- 4-Pillar Context / Load 분포 차트
- 시스템 상태 모니터링

Django Admin (`/django-admin/`)에서 영화별 4-Pillar 태그 직접 편집 가능.

---

## 데이터

### 수집 출처
- **TMDB API** — 영화 메타데이터 (제목, 감독, 출연, 장르, 평점, 포스터 등)
- **한국영상자료원** 추천 영화 리스트 — 선정의 기준점으로 활용

### 선정 기준
총 **1,930편**을 다음 기준으로 선별했습니다.

- **메이저 50%** — 대중적으로 널리 알려진 작품
- **마이너 50%** — 상대적으로 덜 알려졌지만 카테고리별 평점이 높은 작품

단순히 인기작만 추천하지 않고, 평소엔 접하기 어려운 영화를 발견하는 경험을 제공하기 위해 비율을 의도적으로 조정했습니다.

### 데이터 분포 (EDA)

**카테고리**

| 카테고리 | 편수 |
|---|---|
| 영미권 컬트·장르 | 636 |
| 한국 흥행작 | 604 |
| 영미권 정통 명작 | 525 |
| 아시아·유럽 대표작 | 139 |
| 한국 독립·마이너 | 42 |

**연대별 분포** — 1990년대 이후 급격히 증가, 2010년대 이후 작품이 전체의 약 60% 이상

**TMDB 평점 분포** — 평균 6~8점대에 집중된 정규분포 형태. 극단적 저평점·고평점 작품은 소수

**상영시간 분포** — 90~120분대 집중, 피크는 약 100분

**OTT 플랫폼별 보유 편수 (상위)**
- TMDB 제공 데이터 2026.06.05 기준
| 플랫폼 | 편수 |
|---|---|
| Watcha | ~850 |
| Netflix | ~700 |
| Wavve | ~500 |
| Tving | ~400 |
| Disney+ | ~300 |

**장르 TOP 8** — 드라마 · 스릴러 · 액션 · 코미디 · 범죄 · 로맨스 · 공포 · 애니메이션 순

---

## 라이선스

개인 포트폴리오 프로젝트입니다. 수집된 데이터는 비상업적 학습 목적으로만 사용됩니다.