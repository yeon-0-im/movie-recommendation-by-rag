# RAG 파이프라인 학습 로그

RAG 파이프라인을 구축하면서 배운 개념, 결정 사항, 실험 결과를 기록한다.

---

## 4-Pillar LLM 모델 선택 (2026-06-05)

### 배경

`rag_pipeline/00b_4pillar.py`에서 영화 1편당 검색 친화적인 2문장 설명을 생성한다.
입력: 장르 + 줄거리 + 리뷰 / 출력: 감성·무드, 소재·테마, 관람 상황, 스타일을 담은 2문장

### 모델 비교

| 모델 | 방식 | 한국어 품질 | 비고 |
|------|------|------------|------|
| EXAONE 3.5:2.4b | 로컬 (Ollama) | 보통 — 뉘앙스가 뭉뚱그려질 수 있음 | 현재 설정값 |
| EXAONE 3.5:7.8b | 로컬 (Ollama) | 좋음 | VRAM ~8GB 필요 |
| Gemini 2.0 Flash | 무료 API | 매우 좋음 | 15 RPM / 1,500 req/day 무료 |

### 결정

1. **1차**: EXAONE 3.5:2.4b 로 20편 샘플 생성 후 품질 육안 검토
2. **2차**: 품질이 부족하면 Gemini 2.0 Flash 무료 티어로 전환
   - 1,934편 기준 이틀이면 충분 (하루 1,500 req)
   - `4pillar_cache.json` 체크포인트 덕분에 중간 전환 가능

### 배운 점

- 4-Pillar처럼 감성 묘사가 중요한 태스크는 소형 모델(~2B)로는 결과가 평균화되기 쉽다
- 로컬 모델은 비용 0이지만 품질-속도 트레이드오프가 있고, 무료 API 티어가 충분하다면 품질 우선이 낫다
- 체크포인트 설계(영화 제목 → 결과 캐싱)가 있으면 모델 교체 시 처음부터 재실행할 필요가 없다

---

## 왜 enriched_text를 만드는가 — 00_enrich_tmdb.py의 역할 (2026-06-05)

### 문제: 쿼리 언어 vs 영화 설명 언어의 간극

사용자는 "퇴근 후 지쳐서 머리 비우고 볼 영화"라고 검색하지만, 영화 데이터에는 그런 말이 없다.
줄거리는 사건 중심이고, 장르는 분류어일 뿐이다.
이 간극을 그대로 두면 벡터 유사도 검색이 제대로 작동하지 않는다.

### 해결: 리뷰를 문서에 포함시키기

왓챠피디아 리뷰는 실제 관람자가 자신의 감정과 상황으로 남긴 텍스트다.

```
"지쳐있을 때 보면 더 찡한 영화"
"연인이랑 같이 보면 최고"
"울면서 봤는데 이상하게 개운함"
```

이런 표현이 사용자 쿼리와 언어적으로 훨씬 가깝다.
`enriched_text = 장르 + 줄거리 + 리뷰`를 한 덩어리로 묶어 임베딩하면,
쿼리의 감성 표현이 리뷰 텍스트와 유사도 매칭이 일어난다.

### 왜 영화 1편 = 벡터 1개인가

리뷰를 개별 청크로 쪼개지 않고 전체를 하나의 벡터로 만드는 이유:
- 이 RAG의 목적은 **"쿼리에 어울리는 영화"를 찾는 것**이지, "쿼리와 비슷한 문장 조각"을 찾는 게 아님
- 청크로 쪼개면 리뷰 1줄("재밌음")이 장르·맥락 없이 매칭돼 엉뚱한 영화가 올라올 수 있음
- BGE-M3는 최대 ~8,000 토큰까지 처리하므로 영화 1편 분량(평균 ~600자)은 충분히 한 벡터에 담긴다

### 00_enrich_tmdb.py가 하는 일 요약

```
movie_db.csv   → 장르, 줄거리(overview_ko), 감독, 배우, OTT 등 구조적 메타데이터
review_db.csv  → positive 5개 + negative 5개 clean_text → combined_reviews
                                    ↓
                          enriched_text 생성
                  (장르: ... 줄거리: ... 리뷰: ...)
                                    ↓
                    data/movie_enriched.csv 저장
```

4-Pillar(00b_4pillar.py)가 이 enriched_text를 입력으로 받아 검색 설명을 추가 생성하고,
최종 enriched_text = 장르 + 4-Pillar 설명 + 줄거리 + 리뷰 로 갱신된다.

---

## 01_chunk.py — 문서 변환 및 정제 (2026-06-05)

### 왜 하는가

`02_embed_store.py`가 임베딩·저장을 한 번에 처리하는 LangChain `Chroma.from_documents()`를 쓰기 때문에, 입력이 LangChain `Document` 형식이어야 한다. `01_chunk.py`는 CSV를 이 형식에 맞는 JSON으로 변환하는 중간 다리 역할이다.
추가로 임베딩 전에 해결해야 할 데이터 품질 문제(토큰 초과, 마크다운 잔재, 고유 키 충돌)를 이 단계에서 처리한다.

### Input

| 파일 | 설명 |
|------|------|
| `data/movie_enriched.csv` | `00_enrich_tmdb.py` + `00b_4pillar.py` 완료 후 생성된 파일 |

주요 컬럼:
- `tmdb_id` — 영화 고유 키
- `movie_title` — 한국어 제목
- `enriched_text` — 장르 + 4-Pillar 설명 + 줄거리 + 리뷰 합본
- `tmdb_genres`, `tmdb_director`, `tmdb_cast`, `tmdb_country`, `tmdb_release_year`, `tmdb_runtime`, `tmdb_language`, `tmdb_ott` — ChromaDB 필터용 메타데이터

### 무엇을 했는가 (수정 사항)

초기 코드에서 세 가지 문제를 발견하고 수정했다.

**① id를 movie_title → tmdb_id로 교체**
- 문제: 동명이작 17건("괴물" 1982/2006/2023, "알라딘" 1992/2019 등)이 같은 id를 가져 ChromaDB 충돌
- 수정: `id = str(tmdb_id)` 로 교체 — tmdb_id는 전 세계 유일 식별자

**② metadata에 tmdb_id 추가**
- 문제: 검색 결과로 영화가 반환될 때 `movie_title`만 있으면 동명이작 구별 불가, `movie_db.csv`와 JOIN도 불가
- 수정: metadata에 `tmdb_id` 포함 → 검색 결과를 tmdb_id 기준으로 영화 상세 정보와 연결 가능

**③ enriched_text 4,500자 상한 적용**
- 문제: BGE-M3 최대 8,192 토큰 ≈ 한글 약 4,500자인데, 리뷰가 많은 영화가 최대 14,663자에 달해 모델 내부에서 조용히 잘림
- 수정: 4,500자 초과 시 명시적으로 truncate (91편 해당)
- 장르·4-Pillar·줄거리는 앞쪽에 배치되어 있어 truncate 시 리뷰 일부만 잘림

**④ 4-Pillar 마크다운 잔재 제거**
- 문제: EXAONE LLM 출력에 `**설명:**`, `**` 등 마크다운이 남아 임베딩 노이즈 유발
- 수정: 정규식으로 `**텍스트**`, `*텍스트*`, 중복 `설명:` 제거

### Output

파일: `output/movie_chunks.json`

```json
[
  {
    "id": "496243",
    "tmdb_id": 496243,
    "movie_title": "기생충",
    "text": "장르: 코미디, 스릴러, 드라마 추천설명: ... 줄거리: ... 리뷰: ...",
    "char_count": 1823,
    "tmdb_director": "봉준호",
    "tmdb_genres": "코미디, 스릴러, 드라마",
    "tmdb_cast": "송강호, 이선균, ...",
    "tmdb_country": "South Korea",
    "tmdb_release_year": "2019",
    "tmdb_runtime": "132",
    "tmdb_language": "한국어",
    "tmdb_ott": "netflix, watcha"
  },
  ...
]
```

실행 결과: 1,930편 / 스킵 0편 / truncate 91편 / 평균 1,621자

---

## 02_embed_store.py — 임베딩 + 벡터 DB 저장 (2026-06-05)

### 왜 하는가

텍스트 자체는 유사도를 계산할 수 없다. 텍스트를 고차원 숫자 벡터로 변환해야 "두 텍스트가 의미적으로 얼마나 가까운가"를 계산할 수 있다. 이 벡터들을 ChromaDB에 저장해두면, 이후 사용자 쿼리도 같은 모델로 벡터화해서 가장 가까운 영화를 빠르게 찾을 수 있다.

### Input

| 파일 | 설명 |
|------|------|
| `output/movie_chunks.json` | `01_chunk.py` 출력. 1,930개 문서 |

각 문서의 `text` 필드가 임베딩 대상이고, 나머지 필드는 ChromaDB metadata로 저장된다.

### 무엇을 하는가

**임베딩 모델: BAAI/bge-m3**
- 한국어·영어·다국어 지원 오픈소스 모델
- 출력: 1,024차원 벡터 (숫자 1,024개짜리 배열)
- `normalize_embeddings=True`: 벡터 크기를 1로 정규화 → 코사인 유사도 계산이 내적(dot product)과 동일해져 속도와 정확도 모두 확보
- 디바이스: NVIDIA → CUDA, 그 외 → CPU (MPS 제외 — 긴 시퀀스 처리 시 버퍼 오버플로 발생, 트러블슈팅 참고)

**ChromaDB 저장**
```python
Chroma.from_documents(
    documents=docs,
    embedding=embeddings,
    ids=ids,                              # tmdb_id 기반 고유 키
    collection_metadata={"hnsw:space": "cosine"},  # 코사인 유사도 기준 검색
)
```
- `hnsw:space: cosine`: 검색 알고리즘으로 HNSW(Hierarchical Navigable Small World)를 사용하며 거리 기준을 코사인으로 설정
- `Chroma.from_documents()`가 배치 분할과 저장을 내부적으로 자동 처리

**코사인 유사도란?**
두 벡터가 이루는 각도의 코사인 값. 1에 가까울수록 같은 방향(의미적으로 유사), 0에 가까울수록 무관한 내용. 벡터 크기(길이가 긴 리뷰 vs 짧은 리뷰)의 영향을 받지 않아 텍스트 유사도 측정에 적합하다.

### Output

```
chroma_db/
├── chroma.sqlite3       ← 메타데이터(tmdb_id, 장르, 감독 등) + HNSW 인덱스
└── {uuid}/              ← 실제 벡터 데이터 (바이너리)
```

저장 후 검색 흐름:
```
사용자 쿼리 ("퇴근 후 지쳐서 볼 영화")
        ↓ bge-m3 임베딩
   쿼리 벡터 [0.12, -0.34, ..., 0.08]  (1,024차원)
        ↓ ChromaDB 코사인 유사도 검색
   유사도 높은 영화 Top-K 반환
   → metadata의 tmdb_id로 movie_db.csv에서 상세 정보 조회
```

### 트러블슈팅: MPS 버퍼 오버플로 (2026-06-05)

**증상**: Apple Silicon MPS 디바이스에서 `RuntimeError: Invalid buffer size: 14.76 GiB` 발생

**원인**: BGE-M3의 attention 계산은 O(n²) 메모리를 요구한다. 4,500자(≈6,750 토큰) 시퀀스의 attention 행렬이 MPS 버퍼 한도를 초과했다. MPS는 CUDA와 달리 Flash Attention을 완전 지원하지 않아 naive attention으로 폴백 → 메모리 폭증.

**해결**: `get_device()`에서 MPS를 제외하고 CPU로 폴백.

**배운 점**:
- GPU 가속이 항상 옳지 않다. 긴 시퀀스 임베딩에서 MPS는 메모리 제약이 CUDA보다 훨씬 엄격하다
- MPS → CPU 전환은 속도에만 영향을 주고 **벡터 품질(값)은 동일**하다. 모델 가중치와 연산은 같고 실행 하드웨어만 다르기 때문
- Flash Attention 지원 여부가 긴 시퀀스 처리의 핵심 분기점이다

---

## 03_query_parser.py + 04_rag_search.py — 검색 파이프라인 (2026-06-05)

### 왜 쿼리 파서가 필요한가

사용자 쿼리는 크게 두 종류로 나뉜다.

| 쿼리 유형 | 예시 | 적합한 검색 방식 |
|-----------|------|-----------------|
| 감성·상황 기반 | "퇴근 후 지쳐서 볼 영화" | 벡터 유사도 검색 |
| 구조적 조건 기반 | "크리스토퍼 놀란 영화", "넷플릭스 공포" | 메타데이터 필터 검색 |
| 혼합 | "송강호 나오는 감동적인 영화" | 필터 → 유사도 하이브리드 |

규칙 기반으로는 "이창동"이 감독인지 배우인지 판단할 수 없다. LLM(Gemini)이 문맥을 이해해 필터와 의미 검색어를 분리한다.

### 03_query_parser.py

**Input**: 사용자 자연어 쿼리 (문자열)

**처리**: Few-shot 프롬프트로 LLM에게 JSON 출력 요청
```
입력: "송강호 나오는 감동적인 한국 영화"
출력: {
  "filters": {"tmdb_cast": "송강호", "tmdb_language": "한국어"},
  "semantic_query": "감동적인 영화"
}
```

**Output**: `{"filters": {...}, "semantic_query": "..."}`
- `filters`: ChromaDB where 절에 직접 사용되는 구조적 조건
- `semantic_query`: 벡터 유사도 검색에 사용되는 정제된 의미 쿼리
- 파싱 실패 시 전체 쿼리를 `semantic_query`로 폴백 (안전한 기본 동작)

### 04_rag_search.py

**Input**: `chroma_db/` (임베딩 완료된 벡터 DB)

**세 가지 검색 모드**:

```
유사도 검색    : 쿼리 벡터 → ChromaDB 코사인 유사도 → Top-K 반환
메타데이터 검색: ChromaDB where 필터 → exact/substring 매칭
하이브리드    : 필터로 후보 집합 추린 뒤 → 그 안에서 유사도 검색
```

**유사도 점수 변환**:
ChromaDB는 코사인 거리(0=동일, 2=반대)를 반환. 유사도로 변환:
```python
similarity = 1.0 - distance / 2.0  # [0, 2] → [1, 0] 역변환
```

**Output**: 영화 목록 (title, similarity, 장르, 감독, 줄거리, 리뷰 미리보기)

### 수정 사항 (2026-06-05)

| 항목 | 수정 전 | 수정 후 |
|------|---------|---------|
| `get_device()` | MPS 우선 → 버퍼 오버플로 | MPS 제외, CUDA → CPU |
| import 경로 | `pipeline/03_query_parser.py` | `rag_pipeline/03_query_parser.py` |

### LangGraph 전환 완료 (2026-06-07)

`04_rag_search.py`의 단일 스크립트 구조를 LangGraph 노드 구조로 재설계하여 `05_langgraph_rag.py` 및 `backend/movies/rag.py`에 구현 완료.

```
[실제 구현된 노드 구성]
  classify_intent  (Gemini — search / refine / detail 등 분기)
       ↓
  parse_query      (Gemini — 필터 추출 + 의미 쿼리 분리)
       ↓
  vector_search    (ChromaDB — 필터 + 벡터 유사도 검색)
       ↓ (결과 부족 시 retry_search → 필터 완화 재검색)
  score_filter → rerank → paginate
       ↓
  llm_answer / direct_response  (Gemini — 자연어 응답 생성)
```

임베딩·ChromaDB는 그대로 유지되고 흐름 제어가 LangGraph로 이전됨. `RAGSearch` 싱글톤이 서버 시작 시 그래프를 한 번만 빌드하고 이후 재사용.

---

## 언어 필터("한국영화 제외") 버그 수정 (2026-06-07)

### 버그 1 — 언어 코드 불일치

**현상**: "한국영화 빼고", "한국영화 말고" 등 언어 제외 조건이 전혀 동작하지 않음.

**원인**: ChromaDB에는 TMDB API에서 받은 ISO 639-1 코드(`"ko"`, `"en"`, `"ja"`)가 저장되어 있는데, Gemini 파서/분류기 프롬프트는 `"한국어"`, `"영어"` 같은 한국어 명칭을 출력하도록 지시하고 있었다.

```python
# 필터 비교 코드 (수정 전)
"한국어" in meta.get("tmdb_language", "")  # → "한국어" in "ko" → False
```

**수정** (`backend/movies/rag.py`):
```python
LANGUAGE_CODE_MAP = {
    "한국어": "ko", "영어": "en", "일본어": "ja",
    "프랑스어": "fr", "스페인어": "es", "중국어": "zh", ...
}

def _normalize_refine_value(field: str, value: str) -> str:
    if field == "language":
        return LANGUAGE_CODE_MAP.get(value, value)
    return value
```

`_node_parse_query`와 `_passes_refine` 양쪽에서 정규화 적용. `parse_query()` 메서드(SearchView용)도 동일하게 수정.

**배운 점**: 프롬프트가 LLM에게 요청하는 값의 형식이 실제 DB에 저장된 형식과 일치하는지 명시적으로 검증해야 한다. "TMDB API → ChromaDB 저장 형식 → 프롬프트 예시" 사이의 변환 지점을 항상 확인할 것.

---

### 버그 2 — Refine 필터 범위가 너무 좁음

**현상**: 현재 화면에 표시된 영화가 전부 한국 영화인 상태에서 "한국영화 말고"라고 하면 그대로 한국 영화가 뜸.

**원인**: `apply_refine_filter`가 `current_results`(현재 화면 풀, 3~7편)만 대상으로 필터링했다. 전부 한국 영화면 `filtered = []`가 되고, fallback으로 `candidates = current_results`(원래 한국 영화 목록)를 그대로 반환.

```
현재 풀(3~7편) 필터 → 빈 결과 → fallback: 원래 풀 그대로 반환
```

**수정**: 이전 검색어(`user_msgs[-2]`)로 **전체 ChromaDB를 재검색(k=60)**하고 Python-side 필터 적용. ChromaDB `$ne` 연산자에 의존하지 않음(신뢰성 문제).

```python
def _node_apply_refine_filter(state, vectorstore, search_k):
    # 이전 검색어 추출 (현재 refine 쿼리 제외)
    user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
    prev_query = user_msgs[-2] if len(user_msgs) >= 2 else ""

    if prev_query:
        fresh = _do_search(prev_query, vectorstore, None, None, None, search_k)
        filtered = [c for c in fresh if _passes_refine(c["metadata"], exclude, include)]
        if filtered:
            return {"candidates": filtered, ...}
    # fallback: current_results 에서 필터 (이전 검색어 없는 엣지케이스)
```

**배운 점**: Refine은 "현재 결과를 필터링"하는 것이 아니라 "이전 검색 의도를 유지하면서 조건을 추가"하는 것이다. 필터 범위가 현재 화면에 국한되면 반드시 이런 실패 케이스가 생긴다.

---

### 버그 3 — Intent 분류: 간접 표현 미처리

**현상**: "한국영화 싫어", "공포 별로야" 같은 간접 표현이 `not_satisfied`로 분류되어 refine이 실행되지 않음.

**원인**: `CLASSIFY_INTENT_PROMPT`의 `not_satisfied` 정의가 "별로야", "재미없어"를 예시로 포함하고 있어, Gemini가 "싫어"/"별로야"가 포함된 발화를 모두 `not_satisfied`로 분류했다. refine의 예시는 "빼고", "말고" 같은 명시적 제외 표현만 있었음.

**수정**: 프롬프트 개선.
- `refine` 정의에 "직접/간접" 두 종류 표현 명시
- `not_satisfied`를 "속성 언급 없이 막연한 불만"으로 한정
- 구분 규칙 섹션 추가: "언어·장르·배우 등 구체적 속성이 하나라도 있으면 → refine"
- 예시 추가: `"한국영화 싫어"`, `"공포는 별로야"`, `"액션은 안 좋아해"` → refine

**배운 점**: Few-shot 예시는 경계 케이스(border case)에 특히 중요하다. 유사하게 생긴 두 intent(`refine` vs `not_satisfied`)를 구분하려면 그 경계를 예시로 명시해야 한다.

---

### 버그 4 — Pool 영화에 추천 이유 없음

**현상**: "다른 거 보여줘"를 누르면 교체된 영화에 추천 이유가 표시되지 않음.

**원인**: `views.py`에서 `generate_pitches(top3, context)`로 상위 3편만 pitch를 생성하고 `results[3:]`(pool 영화)는 `pitch: ""`인 채로 반환했다.

```python
# 수정 전
top3 = [r["movie"] for r in results[:3]]
pitches = rag.generate_pitches(top3, context)

# 수정 후
pitches = rag.generate_pitches([r["movie"] for r in results], context)
```

`generate_pitches()`는 n편을 **한 번의 Ollama 호출**로 처리하므로 전체로 확장해도 추가 API 비용 없음. `ChatConverseView`와 `ChatFollowupView` 양쪽 수정.

**배운 점**: Pool 영화도 언제든 화면에 올라올 수 있으므로, 화면에 표시될 가능성이 있는 모든 결과에 pitch를 생성해야 한다.

---

### 버그 5 — 특정 영화 제외 요청이 검색에 반영되지 않음 (2026-06-11)

**현상**: 프론트에서 `exclude_ids`를 전달해도 제외한 영화가 검색 결과에 다시 등장함.

**원인**: `run_converse()`가 `exclude_ids` 파라미터를 받았지만 LangGraph `state`에 넣지 않아 검색 노드까지 전달되지 않았음. `views.py`의 `Movie.objects.exclude(id__in=exclude_ids)`는 카드 표시 단계 필터라 재검색·페이지네이션 경로에서는 효과 없음.

**수정**: `RAGState`에 `exclude_tmdb_ids` 필드 추가 → `_build_exact_where()`에 Chroma `$nin` 조건 추가 → `_node_vector_search` / `_node_retry_search` 양쪽에 적용. 벡터 검색 자체에서 해당 영화가 배제되므로 어떤 경로에서도 다시 나오지 않음.

**배운 점**: 파라미터가 함수 시그니처에 있다고 해서 파이프라인 내부에 전달되는 게 아니다. LangGraph처럼 state를 통해 노드 간 데이터를 전달하는 구조에서는, 파라미터를 state에 명시적으로 담아야 하위 노드에서 참조할 수 있다.
