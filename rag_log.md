# RAG 변경 로그

---

## 2026-06-15 — Filter Action Router 3-node 구조 도입

### 배경

아키텍처 다이어그램과 현재 구현 간의 핵심 격차:
- `refine` 경로가 단일 `_node_apply_refine_filter`에서 **항상 merge만** 수행
- LLM이 필터를 어떤 방식으로 업데이트할지(`merge` / `overwrite` / `reset`)를 결정하는 구조가 없음
- search 경로의 session_filters 업데이트가 그래프 밖(`run_converse`)에서 사후 처리됨

---

### 변경 내용

#### 1. `RAGState` — `filter_action` 필드 추가 (`rag.py:262`)

```python
filter_action: str  # "merge" | "overwrite" | "reset"
```

#### 2. `CLASSIFY_INTENT_PROMPT` — filter_action 출력 추가 (`rag.py:117`)

LLM이 intent와 함께 filter_action을 결정하도록 프롬프트 수정.

| 상황 | filter_action |
|---|---|
| search | `overwrite` (항상, 코드에서 강제) |
| refine + 조건 추가·제외 | `merge` |
| refine + "처음부터" / "다 초기화" | `reset` |
| 나머지 | `merge` |

#### 3. `_node_classify_intent` — filter_action 파싱 (`rag.py:400`)

- LLM 출력에서 `filter_action` 추출
- search intent는 코드에서 강제로 `overwrite` 덮어씀 (LLM 착오 방지)

#### 4. `_node_apply_refine_filter` 제거 → 3개 노드로 분리

**`_node_overwrite_filter`** (Overwrite Node) — search 경로 전용
- `parse_query` 직후 실행
- `parsed.intent_exclude` + `intent_params.include` → session_filters 완전 교체
- 이전 session_filters를 버리고 새 검색의 필터로 대체

**`_node_merge_filter`** (Merge Node) — refine(merge) 경로
- 기존 session_filters에 새 exclude/include를 누적
- `session_filters.semantic_query`(이전 검색어)로 재검색 준비
- include → `tmdb_filters` 변환 (EXACT: $eq, PYTHON: py_filters)
- language exclude → `exclude_exact` (ChromaDB $ne)

**`_node_reset_filter`** (Reset Node) — refine(reset) 경로
- session_filters를 `{"exclude": {}, "include": {}, "semantic_query": query}`로 초기화
- 현재 사용자 쿼리를 새 semantic_query로 설정
- 이후 vector_search가 필터 없이 재검색

#### 5. `_route_by_intent` 수정 (`rag.py:716`)

```
refine → filter_action == "reset" ? reset_filter : merge_filter
```

#### 6. `_build_converse_graph` 재구성 (`rag.py:726`)

**이전 그래프:**
```
classify_intent
  search → parse_query → vector_search → ...
  refine → apply_refine_filter → (paginate | END)  ← 자체 검색 포함, 분기 끝점 2개
```

**변경 후 그래프:**
```
classify_intent (Intent Router)
  search → parse_query → overwrite_filter ─┐
  refine(merge) → merge_filter             ├→ vector_search → score_filter → rerank → paginate
  refine(reset) → reset_filter            ─┘
  chat/clarify → llm_answer / direct_response
```

- search/refine 모두 vector_search → score_filter → rerank → paginate 공통 경로 사용
- `_route_after_refine` 삭제 (더 이상 refine 경로에서 END 분기 없음)

#### 7. `run_converse` 단순화 (`rag.py:960`)

session_filters 사후처리 로직(intent별 if-else) 제거. 그래프 노드가 업데이트한 `result["session_filters"]`를 그대로 사용.

```python
# 이전: intent == "search"면 parsed에서 수동 재조립
# 변경: 그래프에서 나온 session_filters 직접 사용
updated_session = result.get("session_filters") or session_filters or {}
```

---

### 새 LangGraph 구조 요약

```
[User Input]
     ↓
[classify_intent]  ← filter_action: merge | overwrite | reset 출력
     ├── search       → [parse_query] → [overwrite_filter] ──┐
     ├── refine/merge → [merge_filter]                      │
     ├── refine/reset → [reset_filter]                      │
     │                                                      ↓
     │                                             [State Store 업데이트]
     │                                                      ↓
     │                                         [vector_search (Pre-Filtering)]
     │                                                      ↓
     │                                   [score_filter] → [rerank] → [paginate]
     │                                                      ↓
     └── chat/clarify → [llm_answer / direct_response]  [Final Response]
```

---

### 수정 파일

- `backend/movies/rag.py` — 위 모든 변경 포함

---

---

## 2026-06-15 — reset 트리거 프롬프트 보강

### 변경 내용

#### `CLASSIFY_INTENT_PROMPT` 추가 (`rag.py`)

1. **reset 트리거 표현 목록** 명시 — 6가지 카테고리
   - 직접 초기화: "처음부터", "다시 처음으로", "초기화해줘", "필터 다 지워줘"
   - 전체 제거: "조건 다 빼줘", "전부 빼줘", "다 없애줘", "아무 조건 없이", "제한 없이"
   - 재시작: "다시 추천해줘"(속성 없을 때), "새로 추천해줘"(속성 없을 때)
   - ※ "한국영화 빼고 다시" 같이 속성이 붙은 경우는 merge

2. **전체 예시에 `filter_action` 추가** — LLM이 형식을 학습하도록 모든 예시 업데이트

3. **reset 예시 7개 추가**
   - "처음부터 다시" / "조건 다 빼줘" / "전부 빼줘" / "아무 조건 없이 추천해줘" / "다시 처음으로 돌아가서" / "필터 다 지워줘" + merge와 경계 케이스 "한국영화 빼고 다시 추천해줘"(→ merge)

---

## 미결 / 다음 작업

| 항목 | 내용 |
|---|---|
| `classify_intent` + `parse_query` 통합 | 현재 Gemini 2회 호출 → 1회로 줄일 여지 있음 (선택사항) |
| merge_filter include 커버리지 | tone/director/cast include가 실제로 잘 동작하는지 E2E 테스트 필요 |
