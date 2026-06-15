"""
[STEP 5] LangGraph RAG 파이프라인 v2

의도 분류(classify_intent) 기반 멀티-브랜치 구조:

  [search]        parse_query → vector_search ─(retry)→ retry_search ─→ score_filter → rerank → paginate
  [refine]        apply_refine_filter ─(results있음)→ paginate / (없음)→ END
  [detail]        llm_answer (ChromaDB + Gemini 상세 정보)
  [when_to_watch] llm_answer (시청 상황 추천)
  [spoiler]       direct_response ("재미없으실걸요?")
  [gratitude]     direct_response ("별말씀을요~")
  [not_satisfied] direct_response ("어떤 영화가 보고 싶으신가요?")
  [unrelated]     direct_response ("관련없는 질문이네요.")

  저유사도(top-k < 0.5): score_filter에서 low_similarity=True 설정,
    paginate에서 "찾기 힘드네요. 대신 이런 영화는 어떠세요?" 포함

  "다른거 추천": next_page(state) → offset +1, candidates 재슬라이싱

실행: /opt/miniconda3/envs/p311_movie_rag/bin/python3 rag_pipeline/05_langgraph_rag.py
전제: chroma_db/ 존재, GEMINI_API_KEY 환경변수 설정
"""

import json
import os
import re
import statistics
from functools import partial
from typing import TypedDict

import torch
from google import genai
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.graph import END, StateGraph

from dotenv import load_dotenv
load_dotenv()

# ── 설정값 ────────────────────────────────────────────────────
MODEL_NAME = "BAAI/bge-m3"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "movie_reviews"
GEMINI_MODEL = "gemini-3,1-flash-lite"

SEARCH_K = 60
MIN_RESULTS = 4
STD_MULTIPLIER = 1.5
MIN_CANDIDATES = 8
PAGE_SIZE = 4
LOW_SIM_THRESHOLD = 0.5

EXCLUDE_TONE_PENALTY = 0.15
POS_TONE_BOOST = 0.05

VALID_TONES = {"exhilarating", "suspenseful", "melancholic", "comforting", "intellectual"}
TMDB_EXACT_FIELDS = {"tmdb_director", "tmdb_release_year", "tmdb_language"}
TMDB_PYTHON_FIELDS = {"tmdb_cast", "tmdb_genres", "tmdb_ott"}

TONE_KO = {
    "exhilarating": "카타르시스·유쾌함",
    "suspenseful":  "긴장감·스릴",
    "melancholic":  "묵직한 여운·잔잔한 슬픔",
    "comforting":   "따뜻함·힐링",
    "intellectual": "사유를 자극하는",
}

# refine 필터에서 사용자가 쓰는 키 → ChromaDB 메타데이터 키 매핑
REFINE_FIELD_MAP = {
    "language":     "tmdb_language",
    "genres":       "tmdb_genres",
    "director":     "tmdb_director",
    "cast":         "tmdb_cast",
    "ott":          "tmdb_ott",
    "tone":         "pos_tones",
    "release_year": "tmdb_release_year",
}


# ── State ─────────────────────────────────────────────────────
class RAGState(TypedDict):
    query: str
    messages: list          # 대화 이력 (컨텍스트용, 최근 N개)
    current_results: list   # 이전 검색 candidates 전체 (refine/detail 컨텍스트)

    intent: str             # classify_intent 결과
    intent_params: dict     # intent별 추출 파라미터

    offset: int
    parsed: dict
    candidates: list
    results: list
    use_filters: bool
    low_similarity: bool

    response_type: str      # "results" | "results_with_warning" | "text"
    response_text: str      # direct_response / llm_answer / 경고 메시지


# ── 전역 리소스 ────────────────────────────────────────────────

def get_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def load_vectorstore() -> Chroma:
    device = get_device()
    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )
    return Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )


def load_gemini_client() -> genai.Client:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
    return genai.Client(api_key=api_key)


# ── 프롬프트 ──────────────────────────────────────────────────

CLASSIFY_INTENT_PROMPT = """\
영화 추천 챗봇의 의도 분류기입니다.

[현재 추천 중인 영화]
{current_titles}

[사용자 입력]: "{query}"

[의도 분류 기준]
- search       : 새로운 영화 추천 요청 (기분/상황/장르/감독/배우/연도/OTT 등으로)
- refine       : 현재 결과에 조건 추가/제외 ("한국영화 빼고", "공포 말고", "넷플릭스만")
- detail       : 특정 영화 상세 정보 요청 ("줄거리", "어떤 영화야", "자세히 알려줘")
- when_to_watch: 특정 영화를 언제/누구와 보면 좋은지 ("언제 보면 좋아?", "혼자 보기 좋아?")
- spoiler      : 스포일러·결말 요청 ("결말", "스포", "엔딩 알려줘")
- gratitude    : 감사·칭찬 표현 ("고마워", "최고야", "도움됐어")
- not_satisfied: 결과 불만이지만 새 조건 없음 ("별로야", "재미없어", "다른 거 줘")
- unrelated    : 영화와 무관한 질문 ("배고파", "오늘 날씨")

[출력] JSON만 출력하세요.
{{"intent": "...", "intent_params": {{}}}}

intent_params 형식:
- search        : {{"search_query": "원문 그대로"}}
- refine        : {{"exclude": {{"language": "한국어"}}, "include": {{}}}}
                  (키: language / genres / director / cast / ott / tone)
- detail        : {{"movie_title": "영화 제목"}}
- when_to_watch : {{"movie_title": "영화 제목"}}
- 나머지         : {{}}

"이 영화", "첫번째", "그거" 등은 현재 추천 목록 첫 번째 영화({first_title})로 해석하세요.

[예시]
입력: "퇴근 후 보기 좋은 영화"   → {{"intent": "search", "intent_params": {{"search_query": "퇴근 후 보기 좋은 영화"}}}}
입력: "한국영화는 빼고"          → {{"intent": "refine", "intent_params": {{"exclude": {{"language": "한국어"}}, "include": {{}}}}}}
입력: "공포 말고"               → {{"intent": "refine", "intent_params": {{"exclude": {{"genres": "공포"}}, "include": {{}}}}}}
입력: "기생충 자세히 알려줘"     → {{"intent": "detail", "intent_params": {{"movie_title": "기생충"}}}}
입력: "이 영화 언제 보면 좋아?"  → {{"intent": "when_to_watch", "intent_params": {{"movie_title": "{first_title}"}}}}
입력: "스포해줘"                → {{"intent": "spoiler", "intent_params": {{}}}}
입력: "고마워!"                 → {{"intent": "gratitude", "intent_params": {{}}}}
입력: "재미없어, 다른 거"        → {{"intent": "not_satisfied", "intent_params": {{}}}}
입력: "배고파"                  → {{"intent": "unrelated", "intent_params": {{}}}}

입력: "{query}"
출력:\
"""

PARSER_PROMPT = """\
영화 검색 쿼리를 분석해서 JSON으로만 출력하세요.

[출력 필드]
- semantic_query: 임베딩 검색용 자연어 표현 (메타데이터 조건 제거 후 핵심 감성·상황만)
- tmdb_filters: 해당 없으면 {{}}
  - tmdb_director: 감독 이름
  - tmdb_cast: 배우 이름
  - tmdb_genres: 드라마/액션/코미디/로맨스/스릴러/공포/SF/판타지/애니메이션/다큐멘터리/범죄/모험 중 하나
  - tmdb_release_year: 숫자 문자열 (예: "2020")
  - tmdb_language: 한국어/영어/일본어/프랑스어/중국어 중 하나
  - tmdb_ott: Netflix/Disney Plus/Watcha 등
- pos_tones: 원하는 분위기 목록
- exclude_tones: 원하지 않는 분위기 목록
  (키: exhilarating / suspenseful / melancholic / comforting / intellectual)

[예시]
입력: "운전하고 싶게 만드는 신나는 영화"
출력: {{"semantic_query": "드라이브하고 싶어지는 에너지 넘치는 영화", "tmdb_filters": {{}}, "pos_tones": ["exhilarating"], "exclude_tones": []}}

입력: "힐링되는데 신파 아닌 영화"
출력: {{"semantic_query": "잔잔하고 따뜻한 힐링 영화", "tmdb_filters": {{}}, "pos_tones": ["comforting"], "exclude_tones": ["melancholic"]}}

입력: "크리스토퍼 놀란 긴장감 있는 영화"
출력: {{"semantic_query": "긴장감 넘치는 스릴러", "tmdb_filters": {{"tmdb_director": "크리스토퍼 놀란"}}, "pos_tones": ["suspenseful"], "exclude_tones": []}}

입력: "송강호 나오는 감동적인 한국 영화"
출력: {{"semantic_query": "감동적인 한국 영화", "tmdb_filters": {{"tmdb_cast": "송강호", "tmdb_language": "한국어"}}, "pos_tones": ["melancholic", "comforting"], "exclude_tones": []}}

입력: "{query}"
출력:\
"""

DETAIL_PROMPT = """\
아래 영화에 대해 리뷰를 참고하여 2-3문장으로 소개해주세요. 친근하고 자연스러운 어투로.

영화: {title}
장르: {genres}
감독: {director}
리뷰: {review}

답변:\
"""

WHEN_TO_WATCH_PROMPT = """\
아래 영화는 언제, 어떤 상황에서 보면 좋을지 2문장으로 추천해주세요. 친근하고 자연스러운 어투로.

영화: {title}
분위기: {tones}
시청 상황: {viewing_context}
리뷰 발췌: {review}

답변:\
"""


# ── ChromaDB 검색 헬퍼 ────────────────────────────────────────

def _build_exact_where(tmdb_filters: dict) -> dict | None:
    conditions = [
        {field: {"$eq": value}}
        for field, value in tmdb_filters.items()
        if field in TMDB_EXACT_FIELDS and value
    ]
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _do_search(
    semantic_query: str,
    vectorstore: Chroma,
    where: dict | None,
    tmdb_python_filters: dict | None = None,
    pos_tones: list | None = None,
) -> list[dict]:
    kwargs = {"k": SEARCH_K}
    if where:
        kwargs["filter"] = where

    raw = vectorstore.similarity_search_with_score(semantic_query, **kwargs)

    seen = set()
    results = []
    for doc, distance in raw:
        title = doc.metadata["movie_title"]
        if title in seen:
            continue
        seen.add(title)

        meta = doc.metadata

        if tmdb_python_filters:
            if not all(v in meta.get(f, "") for f, v in tmdb_python_filters.items()):
                continue

        if pos_tones:
            doc_pos = meta.get("pos_tones", "")
            if not any(tone in doc_pos for tone in pos_tones):
                continue

        similarity = max(0.0, 1.0 - distance / 2.0)
        results.append({
            "movie_title": title,
            "score": similarity,
            "metadata": meta,
            "page_content": doc.page_content,
        })
    return results


def _fetch_movie(title: str, vectorstore: Chroma, current_results: list) -> dict | None:
    """제목으로 영화 정보 검색. current_results 우선, 없으면 ChromaDB."""
    for c in current_results:
        if c.get("movie_title") == title:
            return c

    try:
        raw = vectorstore.similarity_search_with_score(
            title, k=3, filter={"movie_title": {"$eq": title}}
        )
        if raw:
            doc, dist = raw[0]
            return {
                "movie_title": doc.metadata["movie_title"],
                "score": max(0.0, 1.0 - dist / 2.0),
                "metadata": doc.metadata,
                "page_content": doc.page_content,
            }
    except Exception:
        pass

    raw = vectorstore.similarity_search_with_score(title, k=1)
    if raw:
        doc, dist = raw[0]
        return {
            "movie_title": doc.metadata["movie_title"],
            "score": max(0.0, 1.0 - dist / 2.0),
            "metadata": doc.metadata,
            "page_content": doc.page_content,
        }
    return None


# ── 노드 ──────────────────────────────────────────────────────

def node_classify_intent(state: RAGState, client: genai.Client) -> dict:
    query = state["query"]
    current_results = state.get("current_results", [])
    current_titles = [c["movie_title"] for c in current_results[:5]]
    first_title = current_titles[0] if current_titles else ""
    titles_str = ", ".join(current_titles) if current_titles else "없음"

    prompt = CLASSIFY_INTENT_PROMPT.format(
        query=query,
        current_titles=titles_str,
        first_title=first_title,
    )

    try:
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        match = re.search(r"\{.*\}", resp.text, re.DOTALL)
        parsed = json.loads(match.group()) if match else {}
        intent = parsed.get("intent", "search")
        intent_params = parsed.get("intent_params", {})
    except Exception:
        intent, intent_params = "search", {"search_query": query}

    valid = {"search", "refine", "detail", "when_to_watch", "spoiler", "gratitude", "not_satisfied", "unrelated"}
    if intent not in valid:
        intent, intent_params = "search", {"search_query": query}

    return {"intent": intent, "intent_params": intent_params}


def node_parse_query(state: RAGState, client: genai.Client) -> dict:
    query = state["query"]
    prompt = PARSER_PROMPT.format(query=query)

    try:
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        match = re.search(r"\{.*\}", resp.text, re.DOTALL)
        pj = json.loads(match.group()) if match else {}
    except Exception:
        pj = {}

    semantic = pj.get("semantic_query", "").strip() or query
    tmdb_filters = {k: v for k, v in pj.get("tmdb_filters", {}).items() if v}
    pos_tones = [t for t in pj.get("pos_tones", []) if t in VALID_TONES]
    exclude_tones = [t for t in pj.get("exclude_tones", []) if t in VALID_TONES]

    parsed = {
        "semantic_query": semantic,
        "tmdb_filters": tmdb_filters,
        "pos_tones": pos_tones,
        "exclude_tones": exclude_tones,
        "has_filters": bool(tmdb_filters or pos_tones),
    }
    return {"parsed": parsed, "use_filters": parsed["has_filters"]}


def node_vector_search(state: RAGState, vectorstore: Chroma) -> dict:
    parsed = state["parsed"]
    if state["use_filters"]:
        where = _build_exact_where(parsed["tmdb_filters"])
        python_filters = {f: v for f, v in parsed["tmdb_filters"].items() if f in TMDB_PYTHON_FIELDS and v}
        pos_tones = parsed.get("pos_tones") or None
    else:
        where, python_filters, pos_tones = None, None, None

    return {"candidates": _do_search(parsed["semantic_query"], vectorstore, where, python_filters, pos_tones)}


def node_retry_search(state: RAGState, vectorstore: Chroma) -> dict:
    results = _do_search(state["parsed"]["semantic_query"], vectorstore, None)
    return {"candidates": results, "use_filters": False}


def node_score_filter(state: RAGState) -> dict:
    candidates = state["candidates"]
    if not candidates:
        return {"candidates": [], "low_similarity": False}

    scores = [c["score"] for c in candidates]
    max_score = max(scores)
    low_similarity = max_score < LOW_SIM_THRESHOLD

    std = statistics.stdev(scores) if len(scores) > 1 else 0.0
    threshold = max_score - STD_MULTIPLIER * std
    filtered = [c for c in candidates if c["score"] >= threshold]

    if len(filtered) < MIN_CANDIDATES and len(candidates) >= MIN_CANDIDATES:
        filtered = candidates[:MIN_CANDIDATES]
    elif len(filtered) < MIN_CANDIDATES:
        filtered = candidates

    return {"candidates": filtered, "low_similarity": low_similarity}


def node_rerank(state: RAGState) -> dict:
    candidates = [dict(c) for c in state["candidates"]]
    pos_tones = set(state["parsed"].get("pos_tones", []))
    exclude_tones = set(state["parsed"].get("exclude_tones", []))

    for c in candidates:
        pos_str = c["metadata"].get("pos_tones", "")
        neg_str = c["metadata"].get("neg_tones", "")
        for tone in pos_tones:
            if tone in pos_str:
                c["score"] += POS_TONE_BOOST
        for tone in exclude_tones:
            if tone in neg_str:
                c["score"] -= EXCLUDE_TONE_PENALTY

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return {"candidates": candidates}


def node_paginate(state: RAGState) -> dict:
    offset = state.get("offset", 0)
    page = state["candidates"][offset: offset + PAGE_SIZE]
    result: dict = {"results": page}

    if state.get("low_similarity") and offset == 0:
        result["response_type"] = "results_with_warning"
        result["response_text"] = "말씀하신 조건의 영화는 찾기가 힘드네요. 대신 이런 영화는 어떠세요?"
    elif not state.get("response_text"):
        # 이전 노드(apply_refine_filter 등)가 이미 메시지를 설정했으면 유지
        result["response_type"] = "results"
        result["response_text"] = ""

    return result


def node_apply_refine_filter(state: RAGState) -> dict:
    """current_results(이전 candidates)에 조건 필터 적용."""
    candidates = state.get("current_results", [])
    params = state.get("intent_params", {})
    exclude = params.get("exclude", {})
    include = params.get("include", {})

    if not candidates:
        return {
            "candidates": [],
            "offset": 0,
            "response_type": "text",
            "response_text": "먼저 영화를 검색해주세요.",
        }

    filtered = []
    for c in candidates:
        meta = c.get("metadata", {})
        ok = True
        for field, value in exclude.items():
            if value and value in meta.get(REFINE_FIELD_MAP.get(field, field), ""):
                ok = False
                break
        if ok:
            for field, value in include.items():
                if value and value not in meta.get(REFINE_FIELD_MAP.get(field, field), ""):
                    ok = False
                    break
        if ok:
            filtered.append(c)

    if not filtered:
        return {
            "candidates": candidates,
            "offset": 0,
            "response_type": "results_with_warning",
            "response_text": "조건에 맞는 영화가 없어 전체 결과를 보여드려요.",
        }

    return {
        "candidates": filtered,
        "offset": 0,
        "response_type": "results",
        "response_text": "",
    }


def node_llm_answer(state: RAGState, vectorstore: Chroma, client: genai.Client) -> dict:
    """detail / when_to_watch → ChromaDB 조회 후 Gemini 답변 생성."""
    intent = state["intent"]
    movie_title = state.get("intent_params", {}).get("movie_title", "")

    movie = _fetch_movie(movie_title, vectorstore, state.get("current_results", []))
    if not movie:
        return {
            "response_type": "text",
            "response_text": f"'{movie_title}'에 대한 정보를 찾을 수 없어요.",
            "results": [],
        }

    meta = movie.get("metadata", {})
    review = movie.get("page_content", "")
    title = movie.get("movie_title", movie_title)

    if intent == "detail":
        prompt = DETAIL_PROMPT.format(
            title=title,
            genres=meta.get("tmdb_genres", ""),
            director=meta.get("tmdb_director", ""),
            review=review[:500],
        )
    else:  # when_to_watch
        tones_ko = ", ".join(
            TONE_KO.get(t.strip(), t.strip())
            for t in meta.get("pos_tones", "").split(",") if t.strip()
        )
        prompt = WHEN_TO_WATCH_PROMPT.format(
            title=title,
            tones=tones_ko,
            viewing_context=meta.get("viewing_context", ""),
            review=review[:300],
        )

    try:
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        answer = resp.text.strip()
    except Exception as e:
        answer = f"정보를 가져오는 데 실패했습니다: {e}"

    return {
        "response_type": "text",
        "response_text": f"[{title}]\n{answer}",
        "results": [],
    }


def node_direct_response(state: RAGState) -> dict:
    """spoiler / gratitude / not_satisfied / unrelated 고정 응답."""
    responses = {
        "spoiler":       "음.. 그럼 재미없으실걸요? 지금 바로 보시는 걸 추천드립니다.",
        "gratitude":     "별말씀을요~ 언제든 상황에 맞는 영화를 꺼내드리겠습니다.",
        "not_satisfied": "어떤 영화가 보고 싶으신가요? 기분이나 상황을 알려주시면 딱 맞는 영화를 찾아드릴게요.",
        "unrelated":     "관련없는 질문이네요. 어떤 영화를 추천해드릴까요?",
    }
    return {
        "response_type": "text",
        "response_text": responses.get(state["intent"], "어떤 영화를 찾으시나요?"),
        "results": [],
    }


# ── 조건부 엣지 ───────────────────────────────────────────────

def route_by_intent(state: RAGState) -> str:
    intent = state["intent"]
    if intent == "search":
        return "parse_query"
    elif intent == "refine":
        return "apply_refine_filter"
    elif intent in ("detail", "when_to_watch"):
        return "llm_answer"
    else:  # spoiler, gratitude, not_satisfied, unrelated
        return "direct_response"


def _should_retry(state: RAGState) -> str:
    if state["use_filters"] and len(state["candidates"]) < MIN_RESULTS:
        return "retry"
    return "continue"


def _route_after_refine(state: RAGState) -> str:
    """refine 후 직접 텍스트 응답이면 END, 아니면 paginate."""
    if state.get("response_type") == "text":
        return END
    return "paginate"


# ── 그래프 빌드 ───────────────────────────────────────────────

def build_graph(vectorstore: Chroma, client: genai.Client):
    graph = StateGraph(RAGState)

    graph.add_node("classify_intent",     partial(node_classify_intent, client=client))
    graph.add_node("parse_query",         partial(node_parse_query, client=client))
    graph.add_node("vector_search",       partial(node_vector_search, vectorstore=vectorstore))
    graph.add_node("retry_search",        partial(node_retry_search, vectorstore=vectorstore))
    graph.add_node("score_filter",        node_score_filter)
    graph.add_node("rerank",              node_rerank)
    graph.add_node("paginate",            node_paginate)
    graph.add_node("apply_refine_filter", node_apply_refine_filter)
    graph.add_node("llm_answer",          partial(node_llm_answer, vectorstore=vectorstore, client=client))
    graph.add_node("direct_response",     node_direct_response)

    graph.set_entry_point("classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "parse_query":          "parse_query",
            "apply_refine_filter":  "apply_refine_filter",
            "llm_answer":           "llm_answer",
            "direct_response":      "direct_response",
        },
    )

    graph.add_edge("parse_query", "vector_search")
    graph.add_conditional_edges(
        "vector_search",
        _should_retry,
        {"retry": "retry_search", "continue": "score_filter"},
    )
    graph.add_edge("retry_search",  "score_filter")
    graph.add_edge("score_filter",  "rerank")
    graph.add_edge("rerank",        "paginate")
    graph.add_edge("paginate",      END)

    graph.add_conditional_edges("apply_refine_filter", _route_after_refine)

    graph.add_edge("llm_answer",      END)
    graph.add_edge("direct_response", END)

    return graph.compile()


# ── 페이지 이동 (다른거 추천) ──────────────────────────────────

def next_page(state: RAGState) -> RAGState:
    new_offset = state["offset"] + 1
    candidates = state["candidates"]
    if new_offset >= len(candidates):
        print("  더 이상 추천할 영화가 없습니다.")
        return {**state}
    page = candidates[new_offset: new_offset + PAGE_SIZE]
    return {**state, "offset": new_offset, "results": page, "response_type": "results", "response_text": ""}


# ── 출력 ──────────────────────────────────────────────────────

def print_results(state: RAGState):
    response_type = state.get("response_type", "results")

    if response_type == "text":
        print(f"\n  {state.get('response_text', '')}")
        return

    if response_type == "results_with_warning":
        print(f"\n  ⚠  {state.get('response_text', '')}")

    results = state.get("results", [])
    query = state.get("query", "")
    offset = state.get("offset", 0)
    total = len(state.get("candidates", []))
    intent = state.get("intent", "search")

    if not results:
        print("\n  관련 영화를 찾지 못했습니다.")
        return

    label = "검색" if intent == "search" else "필터"
    print(f'\n[{label} 결과] "{query}"  ({offset + 1}~{min(offset + PAGE_SIZE, total)} / 후보 {total}편)')
    print("=" * 65)

    for rank, r in enumerate(results, offset + 1):
        m = r["metadata"]
        bar = "█" * int(r["score"] * 20)
        print(f"  {rank}. {r['movie_title']}  [{r['score']:.3f}] {bar}")
        print(f"     장르   : {m.get('tmdb_genres', '-')}")
        print(f"     감독   : {m.get('tmdb_director', '-')}")
        if m.get("tmdb_cast"):
            print(f"     출연   : {m['tmdb_cast'][:50]}")
        if m.get("tmdb_ott"):
            print(f"     OTT    : {m['tmdb_ott']}")
        if m.get("pos_tones"):
            tones_ko = ", ".join(TONE_KO.get(t, t) for t in m["pos_tones"].split(",") if t.strip())
            print(f"     분위기 : {tones_ko}")
        if m.get("viewing_context"):
            print(f"     시청상황: {m['viewing_context'][:60]}")
        print()

    parsed = state.get("parsed", {})
    if not state.get("use_filters", True) and parsed.get("has_filters"):
        print("  ※ 필터 결과 부족 → 필터 없이 재검색")
    if parsed.get("exclude_tones"):
        ex_ko = ", ".join(TONE_KO.get(t, t) for t in parsed["exclude_tones"])
        print(f"  ※ 제외 분위기 적용: {ex_ko}")


# ── 메인 (대화형 루프) ────────────────────────────────────────

def main():
    print("=" * 60)
    print("[STEP 5] LangGraph RAG 파이프라인 v2")
    print("=" * 60)
    print("\n명령: q=종료  n=다른 추천")
    print("-" * 60)

    print("\nChromaDB 로드 중...")
    vectorstore = load_vectorstore()
    print(f"  {vectorstore._collection.count():,}개 벡터 로드 완료")

    print("Gemini 클라이언트 초기화...")
    client = load_gemini_client()

    print("그래프 빌드 중...")
    graph = build_graph(vectorstore, client)
    print("준비 완료\n")

    state: RAGState | None = None
    messages: list = []

    while True:
        user_input = input("\n입력 → ").strip()
        if not user_input or user_input.lower() == "q":
            print("종료합니다.")
            break

        if user_input.lower() == "n":
            if state is None:
                print("  먼저 검색어를 입력해주세요.")
                continue
            state = next_page(state)
            print_results(state)
            continue

        messages.append({"role": "user", "content": user_input})

        init_state: RAGState = {
            "query": user_input,
            "messages": messages[-10:],
            "current_results": state["candidates"] if state else [],
            "intent": "",
            "intent_params": {},
            "offset": 0,
            "parsed": {},
            "candidates": [],
            "results": [],
            "use_filters": True,
            "low_similarity": False,
            "response_type": "results",
            "response_text": "",
        }

        state = graph.invoke(init_state)
        print_results(state)

        messages.append({
            "role": "assistant",
            "content": state.get("response_text") or f"{len(state.get('results', []))}편 추천",
        })


if __name__ == "__main__":
    main()
