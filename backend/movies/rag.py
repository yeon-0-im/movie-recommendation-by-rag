"""
RAG 검색 모듈 — 앱 시작 시 한 번만 로드, 이후 싱글턴으로 재사용

흐름:
  자연어 쿼리
    → classify_intent (Gemini)
    → [search] parse_query → vector_search → score_filter → rerank → paginate
    → [refine/merge] merge_filter → vector_search → paginate
    → [refine/reset] reset_filter → reset_respond (텍스트 응답만, 검색 없음)
    → [detail/when_to_watch] llm_answer
    → [spoiler/gratitude/not_satisfied/unrelated] direct_response
"""

import json
import logging
import re
import statistics
import torch
from functools import partial
from typing import TypedDict

logger = logging.getLogger(__name__)

from django.conf import settings
from google import genai
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_ollama import ChatOllama  # Ollama 품질 비교용
from langgraph.graph import END, StateGraph

# ── 상수 ──────────────────────────────────────────────────────
VALID_TONES = {"exhilarating", "suspenseful", "melancholic", "comforting", "intellectual"}

# 4-Pillar 유효값
VALID_CONTEXTS = {
    "퇴근길·번아웃", "이별 직후", "이별 후 회복기",
    "머리 비우고 싶을 때", "답답함을 뚫고 싶을 때",
    "동기부여가 필요할 때", "강렬함이 필요할 때",
    "가볍게 웃고 싶을 때", "주말 여유", "혼자 집에서",
}
VALID_SENSORY = {
    "압도적 미장센", "스타일리시 액션", "감각적인 색감",
    "따뜻한 색감", "사운드트랙 맛집", "타란티노 스타일", "몽환적 분위기",
}
VALID_LOADS = {"Low-Load", "Fast-paced", "High-Load"}

# 4-Pillar 점수 부스트 (tone과 동일 방식)
CONTEXT_BOOST  = 0.08
SENSORY_BOOST  = 0.05
LOAD_BOOST     = 0.03

# 장르 제외 안전망용 정규식 (모듈 레벨 — 매 호출마다 컴파일 방지)
_RE_EXCL_KW  = re.compile(r'제외|빼고|말고|빼줘|빼주세요|싫어|별로|안 ?좋아')
_RE_GENRE_KW = re.compile(r'(애니메이션|공포|액션|코미디|로맨스|드라마|SF|판타지|스릴러|다큐멘터리|범죄|모험)')

# Chroma 필드명 → REFINE_FIELD_MAP 키 역매핑 (세션 include 저장 시 사용)
CHROMA_TO_REFINE: dict[str, str] = {v: k for k, v in {
    "language": "tmdb_language", "country": "tmdb_country", "genres": "tmdb_genres",
    "director": "tmdb_director", "cast": "tmdb_cast", "ott": "tmdb_ott",
    "release_year": "tmdb_release_year",
}.items()}
TMDB_EXACT_FIELDS = {"tmdb_director", "tmdb_release_year", "tmdb_language"}
TMDB_PYTHON_FIELDS = {"tmdb_cast", "tmdb_genres", "tmdb_ott"}

TONE_KO = {
    "exhilarating": "카타르시스·유쾌함",
    "suspenseful":  "긴장감·스릴",
    "melancholic":  "묵직한 여운·잔잔한 슬픔",
    "comforting":   "따뜻함·힐링",
    "intellectual": "사유를 자극하는",
}

REFINE_FIELD_MAP = {
    "language":     "tmdb_language",
    "country":      "tmdb_country",
    "genres":       "tmdb_genres",
    "director":     "tmdb_director",
    "cast":         "tmdb_cast",
    "ott":          "tmdb_ott",
    "tone":         "pos_tones",
    "release_year": "tmdb_release_year",
}

# ChromaDB tmdb_language: ISO 639-1 코드 ("ko", "en", ...)
# Gemini는 한국어명·영어명·국가명 등 다양한 형식으로 출력 → 변환 필요
LANGUAGE_CODE_MAP = {
    # 한국어 언어명
    "한국어": "ko", "영어": "en", "일본어": "ja", "프랑스어": "fr",
    "스페인어": "es", "중국어": "zh", "이탈리아어": "it", "독일어": "de",
    "포르투갈어": "pt", "힌디어": "hi", "태국어": "th",
    # 영어 언어명 (Gemini가 영어로 출력하는 경우)
    "Korean": "ko", "English": "en", "Japanese": "ja", "French": "fr",
    "Spanish": "es", "Chinese": "zh", "Italian": "it", "German": "de",
    "Portuguese": "pt", "Hindi": "hi", "Thai": "th",
}

# ChromaDB tmdb_country: ISO 3166-1 alpha-2 코드 ("KR", "US", ...)
# 단독 또는 콤마 구분("KR, US") 형태로 저장 → substring 매칭으로 검사
COUNTRY_CODE_MAP = {
    # 한국어 국가명
    "한국": "KR", "미국": "US", "영국": "GB", "일본": "JP",
    "프랑스": "FR", "스페인": "ES", "중국": "CN", "이탈리아": "IT",
    "독일": "DE", "캐나다": "CA", "호주": "AU", "인도": "IN",
    # 영어 국가명
    "Korea": "KR", "South Korea": "KR", "United States": "US",
    "Japan": "JP", "France": "FR", "China": "CN", "Germany": "DE",
    "United Kingdom": "GB", "Australia": "AU", "India": "IN",
}

def _normalize_refine_value(field: str, value: str) -> str:
    if field == "language":
        mapped = LANGUAGE_CODE_MAP.get(value) or LANGUAGE_CODE_MAP.get(value.capitalize())
        return mapped if mapped else value
    if field == "country":
        mapped = COUNTRY_CODE_MAP.get(value) or COUNTRY_CODE_MAP.get(value.title())
        return mapped if mapped else value.upper()
    return value

# ── 통합 프롬프트 (의도 분류 + 쿼리 파싱 단일 LLM 호출) ────────

UNIFIED_PARSER_PROMPT = """\
영화 추천 챗봇의 입력 분석기입니다. 사용자 입력을 분석해 아래 JSON 하나로만 출력하세요.

[현재 추천 중인 영화]
{current_titles}

[사용자 입력]: "{query}"

[출력 형식]
{{
  "intent": "...",
  "filter_action": "...",
  "semantic_query": "...",
  "tmdb_filters": {{}},
  "intent_exclude": {{}},
  "pos_tones": [],
  "exclude_tones": [],
  "context_tags": [],
  "sensory_tags": [],
  "load_tag": "",
  "movie_title": "",
  "question": ""
}}

─────────────────────────────────────────────────────
[1] intent
─────────────────────────────────────────────────────
search        : 새로운 영화 추천 요청
refine        : 현재 결과에 조건 추가·제외 (구체적 속성 언급)
detail        : 특정 영화 줄거리·소개 요청
when_to_watch : 특정 영화를 언제/누구와 보면 좋은지
movie_question: 특정 영화에 대한 자유 질문 (detail/when_to_watch 외 모든 영화 관련 대화)
              ※ current_titles에 있는 영화 이름이 질문에 포함되면 → 반드시 movie_question
                 예: "슈퍼배드랑 공부랑 무슨 상관이야?" → 슈퍼배드에 대한 movie_question (새 search 아님)
spoiler       : 스포일러·결말 요청
gratitude     : 감사·칭찬
not_satisfied : 속성 언급 없는 막연한 불만 ("별로야", "재미없어")
unrelated     : 영화 무관 질문

[refine vs not_satisfied]
구체적 속성(언어·장르·배우·OTT) 하나라도 → refine / 아무 속성 없이 불만 → not_satisfied

─────────────────────────────────────────────────────
[2] filter_action
─────────────────────────────────────────────────────
overwrite : search → 기존 필터 완전 교체
merge     : refine + 조건 추가·제외 → 기존 필터에 누적
reset     : refine + 필터 전체 초기화 표현 → 모든 조건 삭제 후 재검색
merge     : 그 외 intent → 상태 유지

[reset 트리거]: "처음부터", "다시 처음으로", "초기화", "조건 다 빼줘", "전부 빼줘", "아무 조건 없이"

─────────────────────────────────────────────────────
[3] 필드 작성 규칙
─────────────────────────────────────────────────────
semantic_query:
  search → OTT·언어·장르 제거 후 핵심 감성·상황만
  refine·기타 → "" (이전 검색어 재사용)

tmdb_filters (포함 조건만 — 제외 조건 절대 금지):
  tmdb_director | tmdb_cast | tmdb_genres | tmdb_release_year | tmdb_language | tmdb_ott
  tmdb_language 값: 한국어/영어/일본어/프랑스어/중국어
  tmdb_ott 값: Netflix/Disney Plus/Watcha 등 영어 브랜드명
  tmdb_genres 값: 드라마/액션/코미디/로맨스/스릴러/공포/SF/판타지/애니메이션/다큐멘터리/범죄/모험

[제외 표현 절대 규칙]
"X 제외" "X 빼고" "X 말고" "X 빼줘" "X 싫어" "X 별로" "X 안 좋아"
→ X는 반드시 intent_exclude에 넣고, tmdb_filters에 절대 넣지 말 것

intent_exclude (제외 조건 — REFINE 키 사용):
  language: "한국어"/"영어"/... | country: "한국"/"미국"/... | genres: 장르명
  director | cast | ott | tone

pos_tones / exclude_tones (감정 분위기):
  exhilarating | suspenseful | melancholic | comforting | intellectual

context_tags (사용자 상황 — 해당되는 것 모두):
  퇴근길·번아웃 | 이별 직후 | 이별 후 회복기 | 머리 비우고 싶을 때
  답답함을 뚫고 싶을 때 | 동기부여가 필요할 때 | 강렬함이 필요할 때
  가볍게 웃고 싶을 때 | 주말 여유 | 혼자 집에서
  (해당 없으면 [])

sensory_tags (감각적 선호 — 언급 시에만):
  압도적 미장센 | 스타일리시 액션 | 감각적인 색감 | 따뜻한 색감
  사운드트랙 맛집 | 타란티노 스타일 | 몽환적 분위기
  (언급 없으면 [])

load_tag (인지부하 — 명확히 언급 시에만):
  Low-Load | Fast-paced | High-Load
  (언급 없으면 "")

movie_title: detail/when_to_watch/movie_question 대상 영화 제목
  "이 영화"·"첫번째"·"그거" → {first_title}

question: movie_question 원문

─────────────────────────────────────────────────────
[예시]
─────────────────────────────────────────────────────
입력: "퇴근 후 지쳐서 힐링 영화"
출력: {{"intent":"search","filter_action":"overwrite","semantic_query":"퇴근 후 지친 사람에게 힐링되는 영화","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":["comforting"],"exclude_tones":[],"context_tags":["퇴근길·번아웃"],"sensory_tags":[],"load_tag":"Low-Load","movie_title":"","question":""}}

입력: "이별하고 혼자 집에서 눈물 쏟을 영화"
출력: {{"intent":"search","filter_action":"overwrite","semantic_query":"이별 후 감정을 쏟아낼 수 있는 영화","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":["melancholic"],"exclude_tones":[],"context_tags":["이별 직후","혼자 집에서"],"sensory_tags":[],"load_tag":"","movie_title":"","question":""}}

입력: "답답해서 시원하게 터지는 액션 영화"
출력: {{"intent":"search","filter_action":"overwrite","semantic_query":"통쾌하게 터지는 액션 영화","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":["exhilarating"],"exclude_tones":[],"context_tags":["답답함을 뚫고 싶을 때"],"sensory_tags":["스타일리시 액션"],"load_tag":"Fast-paced","movie_title":"","question":""}}

입력: "영상미 뛰어난 감각적인 영화"
출력: {{"intent":"search","filter_action":"overwrite","semantic_query":"영상미와 색감이 뛰어난 영화","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"context_tags":[],"sensory_tags":["압도적 미장센","감각적인 색감"],"load_tag":"","movie_title":"","question":""}}

입력: "주말에 가볍게 볼 영화"
출력: {{"intent":"search","filter_action":"overwrite","semantic_query":"주말에 편하게 볼 수 있는 영화","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":["comforting"],"exclude_tones":[],"context_tags":["주말 여유","머리 비우고 싶을 때"],"sensory_tags":[],"load_tag":"Low-Load","movie_title":"","question":""}}

입력: "넷플릭스 공포영화 추천해줘"
출력: {{"intent":"search","filter_action":"overwrite","semantic_query":"공포영화","tmdb_filters":{{"tmdb_ott":"Netflix"}},"intent_exclude":{{}},"pos_tones":["suspenseful"],"exclude_tones":[],"movie_title":"","question":""}}

입력: "크리스토퍼 놀란 긴장감 있는 영화"
출력: {{"intent":"search","filter_action":"overwrite","semantic_query":"긴장감 넘치는 스릴러","tmdb_filters":{{"tmdb_director":"크리스토퍼 놀란"}},"intent_exclude":{{}},"pos_tones":["suspenseful"],"exclude_tones":[],"movie_title":"","question":""}}

입력: "힐링되는데 신파 아닌 영화"
출력: {{"intent":"search","filter_action":"overwrite","semantic_query":"잔잔하고 따뜻한 힐링 영화","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":["comforting"],"exclude_tones":["melancholic"],"movie_title":"","question":""}}

입력: "1990년대 이전 고전 명작 추천해줘"
출력: {{"intent":"search","filter_action":"overwrite","semantic_query":"1980~90년대 시대를 초월한 고전 명작 영화","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"movie_title":"","question":""}}

입력: "한국영화 빼고"
출력: {{"intent":"refine","filter_action":"merge","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{"language":"한국어","country":"한국"}},"pos_tones":[],"exclude_tones":[],"movie_title":"","question":""}}

입력: "애니메이션 제외"
출력: {{"intent":"refine","filter_action":"merge","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{"genres":"애니메이션"}},"pos_tones":[],"exclude_tones":[],"movie_title":"","question":""}}

입력: "공포 빼줘"
출력: {{"intent":"refine","filter_action":"merge","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{"genres":"공포"}},"pos_tones":[],"exclude_tones":[],"movie_title":"","question":""}}

입력: "넷플릭스 것만"
출력: {{"intent":"refine","filter_action":"merge","semantic_query":"","tmdb_filters":{{"tmdb_ott":"Netflix"}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"movie_title":"","question":""}}

입력: "처음부터 다시"
출력: {{"intent":"refine","filter_action":"reset","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"movie_title":"","question":""}}

입력: "기생충 자세히 알려줘"
출력: {{"intent":"detail","filter_action":"merge","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"movie_title":"기생충","question":""}}

입력: "기생충 왜 유명해?"
출력: {{"intent":"movie_question","filter_action":"merge","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"movie_title":"기생충","question":"기생충 왜 유명해?"}}

입력: "이 영화 언제 보면 좋아?"
출력: {{"intent":"when_to_watch","filter_action":"merge","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"movie_title":"{first_title}","question":""}}

입력: "슈퍼배드랑 공부랑 무슨 상관이야?"  ※ current_titles에 슈퍼배드 있음
출력: {{"intent":"movie_question","filter_action":"merge","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"movie_title":"슈퍼배드","question":"슈퍼배드랑 공부랑 무슨 상관이야?"}}

입력: "퍼펙트 데이즈가 왜 여기 나와?"  ※ current_titles에 퍼펙트 데이즈 있음
출력: {{"intent":"movie_question","filter_action":"merge","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"movie_title":"퍼펙트 데이즈","question":"퍼펙트 데이즈가 왜 여기 나와?"}}

입력: "이 영화가 왜 추천됐어?"
출력: {{"intent":"movie_question","filter_action":"merge","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"movie_title":"{first_title}","question":"이 영화가 왜 추천됐어?"}}

입력: "별로야"
출력: {{"intent":"not_satisfied","filter_action":"merge","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"movie_title":"","question":""}}

입력: "고마워!"
출력: {{"intent":"gratitude","filter_action":"merge","semantic_query":"","tmdb_filters":{{}},"intent_exclude":{{}},"pos_tones":[],"exclude_tones":[],"movie_title":"","question":""}}

입력: "{query}"
출력:\
"""

PITCH_PROMPT = """지금 사용자 상황: {context}

아래 영화 {n}편에 대해, 위 상황의 사람에게 왜 지금 이 영화가 딱인지 각각 정확히 2문장으로 설명하세요.

규칙:
- 반드시 사용자 상황과 연결하여 쓰세요
- "이 영화는", "특히", "또한" 같은 뻔한 도입어 금지
- 부정적 단서(~하지만, ~수도 있다) 없이 긍정적 이유만
- 문장 2개, 각 40자 이내로 임팩트 있게

{movies}

출력 형식 (반드시 아래 형식 그대로, {n}개 모두 출력):
{format}"""

DETAIL_PROMPT = """\
아래 영화에 대해 2-3문장으로 소개해주세요. 친근하고 자연스러운 어투로.
결말·반전·스포일러가 될 수 있는 내용은 절대 포함하지 마세요.

영화: {title}
장르: {genres}
감독: {director}
리뷰: {review}

답변:\
"""

WHEN_TO_WATCH_PROMPT = """\
아래 영화는 언제, 어떤 상황에서 보면 좋을지 2문장으로 추천해주세요. 친근하고 자연스러운 어투로.
결말·스포일러가 될 수 있는 내용은 언급하지 마세요.

영화: {title}
분위기: {tones}
시청 상황: {viewing_context}
리뷰 발췌: {review}

답변:\
"""

MOVIE_QA_PROMPT = """\
아래 영화에 대한 질문에 친근하고 자연스러운 어투로 2-3문장으로 답해주세요.
제공된 정보를 바탕으로 자신 있게 답변하세요.
출처는 자연스럽게 언급해도 되지만, "리뷰에는 없었지만 영화정보에서 찾았습니다" 같은 한계 표현은 절대 쓰지 마세요.
결말·반전·스포일러가 될 수 있는 내용은 질문에 포함되어 있어도 답하지 말고, 스포일러 없이 답할 수 있는 부분만 답해주세요.

영화: {title} ({year})
장르: {genres}
감독: {director}
출연: {cast}
분위기: {tones}
리뷰: {review}

질문: {question}

답변:\
"""


# ── LangGraph 상태 ─────────────────────────────────────────────

class RAGState(TypedDict):
    query: str
    messages: list
    current_results: list   # 이전 검색 candidates (refine/detail 컨텍스트)
    intent: str
    intent_params: dict
    filter_action: str      # "merge" | "overwrite" | "reset" — Filter Action Router 분기
    offset: int
    parsed: dict
    candidates: list
    results: list
    use_filters: bool
    low_similarity: bool
    response_type: str      # "results" | "results_with_warning" | "text"
    response_text: str
    exclude_tmdb_ids: list  # 벡터 검색에서 제외할 tmdb_id 목록
    session_filters: dict   # {"exclude": {...}, "include": {...}} — 대화 전반 누적 필터
    # 4-Pillar
    context_tags: list      # 매칭할 상황 태그 (부스트 용)
    sensory_tags: list      # 매칭할 감각 태그 (부스트 용)
    load_tag: str           # 매칭할 인지부하 태그


# ── 공통 헬퍼 ─────────────────────────────────────────────────

def _get_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def _parse_gemini_json(raw: str, fallback: dict) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return fallback
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return fallback


def _build_exact_where(
    tmdb_filters: dict,
    exclude_exact: dict | None = None,
    exclude_tmdb_ids: list | None = None,
) -> dict | None:
    """include ($eq) + exclude ($ne / $nin) 조건을 ChromaDB where 절로 변환."""
    conditions = [
        {field: {"$eq": value}}
        for field, value in tmdb_filters.items()
        if field in TMDB_EXACT_FIELDS and value
    ]
    if exclude_exact:
        conditions += [
            {field: {"$ne": value}}
            for field, value in exclude_exact.items()
            if field in TMDB_EXACT_FIELDS and value
        ]
    if exclude_tmdb_ids:
        conditions.append({"tmdb_id": {"$nin": exclude_tmdb_ids}})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def _do_search(
    semantic_query: str,
    vectorstore: Chroma,
    where: dict | None,
    tmdb_python_filters: dict | None,
    pos_tones: list | None,
    k: int,
) -> list[dict]:
    kwargs = {"k": k}
    if where:
        kwargs["filter"] = where

    raw = vectorstore.similarity_search_with_score(semantic_query, **kwargs)
    seen: set[str] = set()
    results = []
    for doc, distance in raw:
        title = doc.metadata["movie_title"]
        if title in seen:
            continue
        seen.add(title)
        meta = doc.metadata

        if tmdb_python_filters and not all(v in meta.get(f, "") for f, v in tmdb_python_filters.items()):
            continue
        if pos_tones and not any(t in meta.get("pos_tones", "") for t in pos_tones):
            continue

        results.append({
            "movie_title": title,
            "score": max(0.0, 1.0 - distance / 2.0),
            "metadata": meta,
            "page_content": doc.page_content,
        })
    return results


def _apply_score_filter(candidates: list, std_multiplier: float, min_candidates: int) -> list:
    if not candidates:
        return []
    scores = [c["score"] for c in candidates]
    max_score = max(scores)
    std = statistics.stdev(scores) if len(scores) > 1 else 0.0
    threshold = max_score - std_multiplier * std
    filtered = [c for c in candidates if c["score"] >= threshold]
    if len(filtered) < min_candidates:
        filtered = candidates[:min_candidates] if len(candidates) >= min_candidates else candidates
    return filtered


# ── LangGraph 노드 ─────────────────────────────────────────────

def _node_unified_intent_parser(state: RAGState, client: genai.Client, model: str) -> dict:
    """의도 분류 + 쿼리 파싱을 단일 Gemini 호출로 처리 (기존 classify_intent + parse_query 통합)."""
    current_results = state.get("current_results", [])
    current_titles = [c["movie_title"] for c in current_results[:5]]
    first_title = current_titles[0] if current_titles else ""
    titles_str = ", ".join(current_titles) or "없음"

    prompt = UNIFIED_PARSER_PROMPT.format(
        query=state["query"],
        current_titles=titles_str,
        first_title=first_title,
    )
    raw: dict = {}
    try:
        resp = client.models.generate_content(model=model, contents=prompt)
        raw = _parse_gemini_json(resp.text, {})
    except Exception as e:
        logger.warning("[unified_parser] Gemini 오류, search fallback: %s", e)

    # ── intent / filter_action ────────────────────────────────
    _VALID_INTENTS = {"search", "refine", "detail", "when_to_watch", "movie_question",
                      "spoiler", "gratitude", "not_satisfied", "unrelated"}
    intent = raw.get("intent", "search")
    if intent not in _VALID_INTENTS:
        intent = "search"

    filter_action = raw.get("filter_action", "merge")
    if filter_action not in {"merge", "overwrite", "reset"}:
        filter_action = "merge"
    if intent == "search":
        filter_action = "overwrite"

    # ── 필터 파싱 ─────────────────────────────────────────────
    tmdb_filters = {k: v for k, v in raw.get("tmdb_filters", {}).items() if v}
    if "tmdb_language" in tmdb_filters:
        tmdb_filters["tmdb_language"] = LANGUAGE_CODE_MAP.get(
            tmdb_filters["tmdb_language"], tmdb_filters["tmdb_language"]
        )
    intent_exclude = {k: v for k, v in raw.get("intent_exclude", {}).items() if v}
    pos_tones     = [t for t in raw.get("pos_tones", [])     if t in VALID_TONES]
    exclude_tones = [t for t in raw.get("exclude_tones", []) if t in VALID_TONES]
    # 4-Pillar
    context_tags  = [t for t in raw.get("context_tags", [])  if t in VALID_CONTEXTS]
    sensory_tags  = [t for t in raw.get("sensory_tags", [])  if t in VALID_SENSORY]
    load_tag      = raw.get("load_tag", "") if raw.get("load_tag") in VALID_LOADS else ""

    # ── 안전망: "X 제외/빼고" 패턴인데 genres가 tmdb_filters에 잘못 들어간 경우 교정 ──
    q = state["query"]
    genre_match = _RE_GENRE_KW.search(q)
    if _RE_EXCL_KW.search(q) and genre_match:
        matched = genre_match.group(1)
        if tmdb_filters.get("tmdb_genres") == matched:
            tmdb_filters.pop("tmdb_genres")
            intent_exclude.setdefault("genres", matched)
            if intent in ("search", "not_satisfied"):
                intent, filter_action = "refine", "merge"
            logger.info("[unified_parser] 안전망 교정: '%s' tmdb_filters→intent_exclude", matched)

    # intent_exclude의 EXACT 필드 → ChromaDB $ne
    exclude_exact: dict = {}
    if "language" in intent_exclude:
        lang_code = _normalize_refine_value("language", intent_exclude["language"])
        if lang_code:
            exclude_exact["tmdb_language"] = lang_code

    semantic_query = raw.get("semantic_query", "").strip() or (state["query"] if intent == "search" else "")
    movie_title = raw.get("movie_title", "")
    question    = raw.get("question", "")

    # ── intent_params (llm_answer 노드가 사용) ─────────────────
    if intent in ("detail", "when_to_watch"):
        intent_params: dict = {"movie_title": movie_title}
    elif intent == "movie_question":
        intent_params = {"movie_title": movie_title, "question": question}
    else:
        intent_params = {}

    parsed = {
        "semantic_query": semantic_query,
        "tmdb_filters":   tmdb_filters,
        "pos_tones":      pos_tones,
        "exclude_tones":  exclude_tones,
        "has_filters":    bool(tmdb_filters or pos_tones),
        "intent_exclude": intent_exclude,
        "exclude_exact":  exclude_exact,
        "context_tags":   context_tags,
        "sensory_tags":   sensory_tags,
        "load_tag":       load_tag,
    }

    logger.info("[unified_parser] query=%r  intent=%s  filter_action=%s  context=%s  sensory=%s",
                state["query"], intent, filter_action, context_tags, sensory_tags)
    return {
        "intent":        intent,
        "intent_params": intent_params,
        "filter_action": filter_action,
        "parsed":        parsed,
        "use_filters":   parsed["has_filters"],
        "context_tags":  context_tags,
        "sensory_tags":  sensory_tags,
        "load_tag":      load_tag,
    }


def _node_vector_search(state: RAGState, vectorstore: Chroma, search_k: int) -> dict:
    parsed = state["parsed"]
    exclude_exact = parsed.get("exclude_exact", {})
    exclude_ids = state.get("exclude_tmdb_ids") or None

    if state["use_filters"]:
        where = _build_exact_where(parsed["tmdb_filters"], exclude_exact or None, exclude_ids)
        py_filters = {f: v for f, v in parsed["tmdb_filters"].items() if f in TMDB_PYTHON_FIELDS and v}
        pos_tones = parsed.get("pos_tones") or None
    else:
        where = _build_exact_where({}, exclude_exact or None, exclude_ids)
        py_filters, pos_tones = None, None

    return {"candidates": _do_search(parsed["semantic_query"], vectorstore, where, py_filters, pos_tones, search_k)}


def _node_retry_search(state: RAGState, vectorstore: Chroma, search_k: int) -> dict:
    parsed = state.get("parsed", {})
    exclude_exact = parsed.get("exclude_exact", {})
    exclude_ids = state.get("exclude_tmdb_ids") or None
    # EXACT 필드($eq) — 언어·감독·연도는 retry에서도 유지 (tone·OTT·장르만 완화)
    exact_include = {f: v for f, v in parsed.get("tmdb_filters", {}).items()
                    if f in TMDB_EXACT_FIELDS and v}
    where = _build_exact_where(exact_include, exclude_exact or None, exclude_ids)
    results = _do_search(parsed.get("semantic_query", ""), vectorstore, where, None, None, search_k)
    return {"candidates": results, "use_filters": False}


def _node_score_filter(state: RAGState, std_multiplier: float, min_candidates: int, low_sim_threshold: float) -> dict:
    candidates = state["candidates"]
    if not candidates:
        return {"candidates": [], "low_similarity": False}

    max_score = max(c["score"] for c in candidates)
    low_similarity = max_score < low_sim_threshold
    filtered = _apply_score_filter(candidates, std_multiplier, min_candidates)
    return {"candidates": filtered, "low_similarity": low_similarity}


def _node_rerank(state: RAGState, pos_boost: float, exclude_penalty: float) -> dict:
    candidates = [dict(c) for c in state["candidates"]]
    parsed = state["parsed"]
    pos_tones     = set(parsed.get("pos_tones", []))
    exclude_tones = set(parsed.get("exclude_tones", []))
    context_tags  = set(state.get("context_tags", []))
    sensory_tags  = set(state.get("sensory_tags", []))
    load_tag      = state.get("load_tag", "")

    for c in candidates:
        meta    = c["metadata"]
        pos_str = meta.get("pos_tones", "")
        neg_str = meta.get("neg_tones", "")

        # Tone 부스트 (기존)
        for tone in pos_tones:
            if tone in pos_str:
                c["score"] += pos_boost
        for tone in exclude_tones:
            if tone in neg_str:
                c["score"] -= exclude_penalty

        # 4-Pillar 부스트
        ctx_str     = meta.get("ohcc_context", "")
        sensory_str = meta.get("ohcc_sensory", "")
        meta_load   = meta.get("ohcc_load", "")

        for tag in context_tags:
            if tag in ctx_str:
                c["score"] += CONTEXT_BOOST
        for tag in sensory_tags:
            if tag in sensory_str:
                c["score"] += SENSORY_BOOST
        if load_tag and load_tag == meta_load:
            c["score"] += LOAD_BOOST

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # intent_exclude Python-side 필터
    intent_exclude = parsed.get("intent_exclude", {})
    if intent_exclude:
        before = len(candidates)
        candidates = [c for c in candidates if _passes_refine(c["metadata"], intent_exclude, {})]
        logger.info("[rerank] intent_exclude=%s  %d→%d", intent_exclude, before, len(candidates))

    return {"candidates": candidates}


def _node_paginate(state: RAGState, page_size: int) -> dict:
    offset = state.get("offset", 0)
    page = state["candidates"][offset: offset + page_size]
    result: dict = {"results": page}

    if state.get("low_similarity") and offset == 0:
        result["response_type"] = "results_with_warning"
        result["response_text"] = "말씀하신 조건의 영화는 찾기가 힘드네요. 대신 이런 영화는 어떠세요?"
    elif not state.get("response_text"):
        result["response_type"] = "results"
        result["response_text"] = ""

    return result


def _passes_refine(meta: dict, exclude: dict, include: dict) -> bool:
    for field, value in exclude.items():
        norm = _normalize_refine_value(field, value)
        if norm and norm in meta.get(REFINE_FIELD_MAP.get(field, field), ""):
            return False
    for field, value in include.items():
        norm = _normalize_refine_value(field, value)
        if norm and norm not in meta.get(REFINE_FIELD_MAP.get(field, field), ""):
            return False
    return True


def _node_overwrite_filter(state: RAGState) -> dict:
    """search 경로: unified_parser 결과로 session_filters를 완전히 교체 (Overwrite Node)."""
    parsed = state.get("parsed", {})
    # tmdb_filters(Chroma명) → session include(REFINE키)로 변환해 저장
    session_include = {CHROMA_TO_REFINE[k]: v for k, v in parsed.get("tmdb_filters", {}).items()
                       if k in CHROMA_TO_REFINE}
    new_session = {
        "exclude":        parsed.get("intent_exclude", {}),
        "include":        session_include,
        "semantic_query": parsed.get("semantic_query", ""),
        "candidates":     [],
    }
    logger.info("[overwrite_filter] session=%s", new_session)
    return {"session_filters": new_session}


def _node_merge_filter(state: RAGState) -> dict:
    """refine/merge: 세션 필터와 병합한 뒤 vector_search 준비 (Merge Node)."""
    parsed  = dict(state.get("parsed", {}))
    session = state.get("session_filters") or {}

    # 제외 병합 (REFINE키)
    merged_exclude = {**session.get("exclude", {}), **parsed.get("intent_exclude", {})}

    # 포함 병합: session.include(REFINE키) + parsed.tmdb_filters(Chroma명)
    merged_include = dict(session.get("include", {}))
    for chroma_field, value in parsed.get("tmdb_filters", {}).items():
        refine_key = CHROMA_TO_REFINE.get(chroma_field)
        if refine_key:
            merged_include[refine_key] = value

    # 이전 시맨틱 쿼리 사용 (refine은 검색 주제를 바꾸지 않음)
    prev_query = session.get("semantic_query") or state.get("query", "")

    # 병합 include → Chroma tmdb_filters
    merged_tmdb: dict = {}
    for field, value in merged_include.items():
        norm         = _normalize_refine_value(field, value)
        chroma_field = REFINE_FIELD_MAP.get(field)
        if chroma_field and chroma_field in (TMDB_EXACT_FIELDS | TMDB_PYTHON_FIELDS):
            merged_tmdb[chroma_field] = norm

    # pos_tones (세션 tone 누적)
    pos_tones = list(parsed.get("pos_tones", []))
    if "tone" in merged_include:
        tone_val = merged_include["tone"]
        if tone_val in VALID_TONES and tone_val not in pos_tones:
            pos_tones.insert(0, tone_val)

    # exclude_exact (ChromaDB $ne — EXACT 필드만)
    exclude_exact: dict = {}
    if "language" in merged_exclude:
        lang_code = _normalize_refine_value("language", merged_exclude["language"])
        if lang_code:
            exclude_exact["tmdb_language"] = lang_code

    updated_parsed = {
        **parsed,
        "semantic_query": prev_query,
        "tmdb_filters":   merged_tmdb,
        "intent_exclude": merged_exclude,
        "exclude_exact":  exclude_exact,
        "pos_tones":      pos_tones,
        "has_filters":    bool(merged_tmdb or pos_tones or merged_exclude),
    }
    new_session = {
        "exclude":        merged_exclude,
        "include":        merged_include,
        "semantic_query": prev_query,
        "candidates":     session.get("candidates", []),
    }
    logger.info("[merge_filter] query=%r  exclude=%s  tmdb=%s",
                prev_query, merged_exclude, merged_tmdb)
    return {
        "session_filters": new_session,
        "parsed":          updated_parsed,
        "use_filters":     bool(merged_tmdb or exclude_exact or pos_tones),
        "offset":          0,
    }


def _node_reset_filter(state: RAGState) -> dict:
    """refine/reset: 필터 초기화 후 이전 쿼리로 vector_search 재검색 준비 (Reset Node)."""
    session    = state.get("session_filters") or {}
    prev_query = session.get("semantic_query") or state.get("query", "")
    parsed = {
        "semantic_query": prev_query,
        "tmdb_filters":  {},
        "pos_tones":     [],
        "exclude_tones": [],
        "has_filters":   False,
        "intent_exclude":{},
        "exclude_exact": {},
    }
    logger.info("[reset_filter] 필터 초기화 후 재검색  query=%r", prev_query)
    return {
        "session_filters": {"exclude": {}, "include": {}, "semantic_query": prev_query, "candidates": []},
        "parsed":          parsed,
        "use_filters":     False,
        "offset":          0,
        "response_text":   "조건을 초기화하고 다시 찾아봤어요.",
    }


def _node_llm_answer(state: RAGState, vectorstore: Chroma, client: genai.Client, model: str) -> dict:
    intent = state["intent"]
    movie_title = state.get("intent_params", {}).get("movie_title", "")
    current_results = state.get("current_results", [])

    # current_results 우선, 없으면 ChromaDB 검색
    movie = next((c for c in current_results if c.get("movie_title") == movie_title), None)
    if not movie:
        try:
            raw = vectorstore.similarity_search_with_score(
                movie_title, k=3, filter={"movie_title": {"$eq": movie_title}}
            )
            if raw:
                doc, _ = raw[0]
                movie = {"movie_title": doc.metadata["movie_title"],
                         "metadata": doc.metadata, "page_content": doc.page_content}
        except Exception:
            pass

    if not movie:
        return {"response_type": "text", "response_text": f"'{movie_title}'에 대한 정보를 찾을 수 없어요.", "results": []}

    meta = movie.get("metadata", {})
    review = movie.get("page_content", "")
    title = movie.get("movie_title", movie_title)

    tones_ko = ", ".join(
        TONE_KO.get(t.strip(), t.strip())
        for t in meta.get("pos_tones", "").split(",") if t.strip()
    )

    if intent == "detail":
        prompt = DETAIL_PROMPT.format(
            title=title, genres=meta.get("tmdb_genres", ""),
            director=meta.get("tmdb_director", ""), review=review[:500],
        )
    elif intent == "when_to_watch":
        prompt = WHEN_TO_WATCH_PROMPT.format(
            title=title, tones=tones_ko,
            viewing_context=meta.get("viewing_context", ""), review=review[:300],
        )
    else:  # movie_question
        question = state.get("intent_params", {}).get("question", state.get("query", ""))
        prompt = MOVIE_QA_PROMPT.format(
            title=title,
            year=meta.get("tmdb_release_year", ""),
            genres=meta.get("tmdb_genres", ""),
            director=meta.get("tmdb_director", ""),
            cast=meta.get("tmdb_cast", "")[:60],
            tones=tones_ko,
            review=review[:500],
            question=question,
        )

    try:
        resp = client.models.generate_content(model=model, contents=prompt)
        answer = resp.text.strip()
    except Exception as e:
        answer = f"정보를 가져오는 데 실패했습니다: {e}"

    return {"response_type": "text", "response_text": f"[{title}]\n{answer}", "results": []}


def _node_cache_candidates(state: RAGState) -> dict:
    """rerank 직후: 전체 후보 풀을 session_filters에 저장 — 다음 refine 시 재검색 없이 필터링."""
    session = dict(state.get("session_filters") or {})
    session["candidates"] = state.get("candidates", [])
    logger.info("[cache_candidates] 후보 %d개 캐싱", len(session["candidates"]))
    return {"session_filters": session}



def _node_direct_response(state: RAGState) -> dict:
    responses = {
        "spoiler":       "결말과 스포일러는 알려드리기 곤란해요~. 직접 보시는 게 훨씬 더 좋을 거예요 😊",
        "gratitude":     "별말씀을요~ 언제든 상황에 맞는 영화를 꺼내드리겠습니다.",
        "not_satisfied": "어떤 영화가 보고 싶으신가요? 기분이나 상황을 알려주시면 딱 맞는 영화를 찾아드릴게요.",
        "unrelated":     "관련없는 질문이네요. 어떤 영화를 추천해드릴까요?",
    }
    return {"response_type": "text",
            "response_text": responses.get(state["intent"], "어떤 영화를 찾으시나요?"),
            "results": []}


# ── 조건부 엣지 ───────────────────────────────────────────────

def _route_by_intent(state: RAGState) -> str:
    intent = state["intent"]
    if intent == "search":
        return "overwrite_filter"
    elif intent == "refine":
        action = state.get("filter_action", "merge")
        return "reset_filter" if action == "reset" else "merge_filter"
    elif intent in ("detail", "when_to_watch", "movie_question"):
        return "llm_answer"
    else:
        return "direct_response"


def _should_retry(state: RAGState, min_results: int) -> str:
    if state["use_filters"] and len(state["candidates"]) < min_results:
        return "retry"
    return "continue"



# ── 그래프 빌드 ───────────────────────────────────────────────

def _build_converse_graph(
    vectorstore: Chroma,
    client: genai.Client,
    model: str,
    search_k: int,
    std_multiplier: float,
    min_candidates: int,
    pos_boost: float,
    exclude_penalty: float,
    low_sim_threshold: float,
    page_size: int,
    min_results: int = 4,
):
    g = StateGraph(RAGState)

    # ── 노드 등록 ──────────────────────────────────────────────
    g.add_node("unified_intent_parser", partial(_node_unified_intent_parser, client=client, model=model))
    g.add_node("overwrite_filter",      _node_overwrite_filter)   # Overwrite Node
    g.add_node("merge_filter",          _node_merge_filter)        # Merge Node
    g.add_node("reset_filter",          _node_reset_filter)        # Reset Node
    g.add_node("vector_search",         partial(_node_vector_search, vectorstore=vectorstore, search_k=search_k))
    g.add_node("retry_search",          partial(_node_retry_search, vectorstore=vectorstore, search_k=search_k))
    g.add_node("score_filter",          partial(_node_score_filter, std_multiplier=std_multiplier,
                                                min_candidates=min_candidates, low_sim_threshold=low_sim_threshold))
    g.add_node("rerank",                partial(_node_rerank, pos_boost=pos_boost, exclude_penalty=exclude_penalty))
    g.add_node("paginate",              partial(_node_paginate, page_size=page_size))
    g.add_node("cache_candidates",      _node_cache_candidates)
    g.add_node("llm_answer",            partial(_node_llm_answer, vectorstore=vectorstore, client=client, model=model))
    g.add_node("direct_response",       _node_direct_response)

    g.set_entry_point("unified_intent_parser")

    # ── Intent Router (unified_intent_parser 출력 기반 직접 분기) ──
    g.add_conditional_edges("unified_intent_parser", _route_by_intent, {
        "overwrite_filter": "overwrite_filter",
        "merge_filter":     "merge_filter",
        "reset_filter":     "reset_filter",
        "llm_answer":       "llm_answer",
        "direct_response":  "direct_response",
    })

    # 모든 filter 노드 → vector_search (실선 — 항상 검색)
    g.add_edge("overwrite_filter", "vector_search")
    g.add_edge("merge_filter",     "vector_search")
    g.add_edge("reset_filter",     "vector_search")

    # ── 공통 검색 후처리 ───────────────────────────────────────
    g.add_conditional_edges("vector_search",
                            partial(_should_retry, min_results=min_results),
                            {"retry": "retry_search", "continue": "score_filter"})
    g.add_edge("retry_search",     "score_filter")
    g.add_edge("score_filter",     "rerank")
    g.add_edge("rerank",           "cache_candidates")
    g.add_edge("cache_candidates", "paginate")
    g.add_edge("paginate",         END)

    g.add_edge("llm_answer",      END)
    g.add_edge("direct_response", END)

    return g.compile()


# ── RAGSearch 싱글턴 ───────────────────────────────────────────

class RAGSearch:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        device = _get_device()
        self.top_k           = settings.RAG_TOP_K
        self.search_k        = settings.RAG_SEARCH_K
        self.std_multiplier  = settings.RAG_STD_MULTIPLIER
        self.min_candidates  = settings.RAG_MIN_CANDIDATES
        self.pos_boost       = settings.RAG_POS_TONE_BOOST
        self.exclude_penalty = settings.RAG_EXCLUDE_TONE_PENALTY
        self.low_sim_threshold = settings.RAG_LOW_SIM_THRESHOLD
        self.page_size       = settings.RAG_PAGE_SIZE

        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.RAG_EMBED_MODEL,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )
        self.vectorstore = Chroma(
            persist_directory=settings.RAG_CHROMA_PATH,
            embedding_function=self.embeddings,
            collection_name=settings.RAG_COLLECTION_NAME,
        )
        self.gemini = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.gemini_model = settings.RAG_GEMINI_MODEL
        # self.pitch_model = settings.RAG_PITCH_GEMINI_MODEL  # Gemini pitch
        from langchain_ollama import ChatOllama
        self.llm = ChatOllama(model=settings.RAG_OLLAMA_MODEL, temperature=0)  # Ollama pitch

        self.graph = _build_converse_graph(
            vectorstore=self.vectorstore,
            client=self.gemini,
            model=self.gemini_model,
            search_k=self.search_k,
            std_multiplier=self.std_multiplier,
            min_candidates=self.min_candidates,
            pos_boost=self.pos_boost,
            exclude_penalty=self.exclude_penalty,
            low_sim_threshold=self.low_sim_threshold,
            page_size=self.page_size,
        )

    # ── 기존 검색 API (SearchView / ChatFollowupView용) ────────

    def parse_query(self, query: str) -> dict:
        """SearchView용 — UNIFIED_PARSER_PROMPT로 쿼리 파싱."""
        prompt = UNIFIED_PARSER_PROMPT.format(query=query, current_titles="없음", first_title="")
        try:
            resp = self.gemini.models.generate_content(model=self.gemini_model, contents=prompt)
            pj = _parse_gemini_json(resp.text, {})
        except Exception:
            pj = {}

        semantic = pj.get("semantic_query", "").strip() or query
        tmdb_filters = {k: v for k, v in pj.get("tmdb_filters", {}).items() if v}
        if "tmdb_language" in tmdb_filters:
            tmdb_filters["tmdb_language"] = LANGUAGE_CODE_MAP.get(
                tmdb_filters["tmdb_language"], tmdb_filters["tmdb_language"]
            )
        pos_tones = [t for t in pj.get("pos_tones", []) if t in VALID_TONES]
        exclude_tones = [t for t in pj.get("exclude_tones", []) if t in VALID_TONES]
        return {
            "semantic_query": semantic, "tmdb_filters": tmdb_filters,
            "pos_tones": pos_tones, "exclude_tones": exclude_tones,
            "has_filters": bool(tmdb_filters or pos_tones),
        }

    def semantic_search(self, query: str, k: int = 0) -> list[dict]:
        k = k or self.top_k
        results = _do_search(query, self.vectorstore, None, None, None, k * 3)
        filtered = _apply_score_filter(results, self.std_multiplier, min(k, self.min_candidates))
        return [{"title": c["movie_title"], "similarity": c["score"]} for c in filtered[:k]]

    def search(self, query: str) -> dict:
        parsed = self.parse_query(query)
        where = _build_exact_where(parsed["tmdb_filters"])
        py_filters = {f: v for f, v in parsed["tmdb_filters"].items() if f in TMDB_PYTHON_FIELDS and v}

        candidates = _do_search(
            parsed["semantic_query"], self.vectorstore,
            where, py_filters, parsed.get("pos_tones") or None,
            self.search_k,
        )
        if len(candidates) < 4 and parsed["has_filters"]:
            candidates = _do_search(parsed["semantic_query"], self.vectorstore, None, None, None, self.search_k)

        candidates = _apply_score_filter(candidates, self.std_multiplier, self.min_candidates)

        # rerank
        pos_set = set(parsed.get("pos_tones", []))
        ex_set = set(parsed.get("exclude_tones", []))
        for c in candidates:
            for tone in pos_set:
                if tone in c["metadata"].get("pos_tones", ""):
                    c["score"] += self.pos_boost
            for tone in ex_set:
                if tone in c["metadata"].get("neg_tones", ""):
                    c["score"] -= self.exclude_penalty
        candidates.sort(key=lambda x: x["score"], reverse=True)

        hits = [{"title": c["movie_title"], "similarity": c["score"]} for c in candidates[: self.top_k]]
        return {"parsed": parsed, "hits": hits}

    # ── 새 대화형 API (ChatConverseView용) ─────────────────────

    def run_converse(
        self,
        messages: list,
        current_movie_titles: list | None = None,
        exclude_ids: list | None = None,
        session_filters: dict | None = None,
    ) -> dict:
        """
        LangGraph 파이프라인 실행.
        반환:
          response_type: "results" | "results_with_warning" | "text"
          response_text: str
          intent: str
          hits: [{"title": str, "similarity": float}]
          candidates: list  # 다음 refine을 위한 전체 후보
          session_filters: dict  # 다음 턴에 넘길 누적 필터
        """
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )
        current_results = self._fetch_candidates_by_titles(current_movie_titles or [])

        state = {
            "query": last_user,
            "messages": messages[-10:],
            "current_results": current_results,
            "intent": "",
            "intent_params": {},
            "filter_action": "merge",
            "offset": 0,
            "parsed": {},
            "candidates": [],
            "results": [],
            "use_filters": True,
            "low_similarity": False,
            "response_type": "results",
            "response_text": "",
            "exclude_tmdb_ids": list(exclude_ids) if exclude_ids else [],
            "session_filters": session_filters or {"exclude": {}, "include": {}},
        }

        result = self.graph.invoke(state)

        # session_filters는 overwrite/merge/reset_filter 노드에서 업데이트됨
        updated_session = result.get("session_filters") or session_filters or {}
        intent = result.get("intent", "search")

        hits = [
            {"title": r["movie_title"], "similarity": r["score"]}
            for r in result.get("results", [])
        ]
        return {
            "response_type": result.get("response_type", "results"),
            "response_text": result.get("response_text", ""),
            "intent": intent,
            "hits": hits,
            "candidates": result.get("candidates", []),
            "session_filters": updated_session,
        }

    def _fetch_candidates_by_titles(self, titles: list[str]) -> list[dict]:
        """titles 목록을 ChromaDB에서 일괄 조회. refine/detail 컨텍스트용."""
        if not titles:
            return []
        try:
            where = ({"movie_title": {"$eq": titles[0]}} if len(titles) == 1
                     else {"$or": [{"movie_title": {"$eq": t}} for t in titles]})
            raw = self.vectorstore.similarity_search_with_score(
                titles[0], k=len(titles) * 3, filter=where
            )
            meta_by_title = {}
            for doc, _ in raw:
                t = doc.metadata["movie_title"]
                if t not in meta_by_title:
                    meta_by_title[t] = {"metadata": doc.metadata, "page_content": doc.page_content}

            return [
                {
                    "movie_title": t,
                    "score": 1.0 - i * 0.01,  # 순서 보존용 placeholder
                    "metadata": meta_by_title[t]["metadata"],
                    "page_content": meta_by_title[t]["page_content"],
                }
                for i, t in enumerate(titles) if t in meta_by_title
            ]
        except Exception:
            return []

    # ── Chroma 동기화 ─────────────────────────────────────────

    def upsert_movie(self, movie) -> None:
        """Django Movie 인스턴스를 Chroma에 upsert (저장/수정 시 자동 호출)."""
        text = movie.llm_4pillar or movie.overview_ko or movie.title_ko
        if not text.strip():
            return

        doc_id = str(movie.tmdb_id)
        # 기존 ChromaDB 메타데이터 보존 (pos_tones, neg_tones 등 초기 임포트 데이터)
        existing_meta = {}
        try:
            result = self.vectorstore._collection.get(
                ids=[doc_id], include=["metadatas"]
            )
            if result["metadatas"]:
                existing_meta = result["metadatas"][0]
        except Exception:
            pass

        metadata = {
            **existing_meta,   # 기존 데이터 먼저 복사
            "tmdb_id":           movie.tmdb_id,
            "movie_title":       movie.title_ko,
            "tmdb_director":     movie.director,
            "tmdb_genres":       movie.genres,
            "tmdb_cast":         movie.cast,
            "tmdb_release_year": str(movie.year) if movie.year else "",
            "tmdb_runtime":      str(movie.runtime) if movie.runtime else "",
            "tmdb_country":      movie.country,
            "tmdb_language":     movie.language,
            "tmdb_ott":          movie.ott,
            # 4-Pillar
            "ohcc_context": movie.context or "",
            "ohcc_sensory":  movie.sensory  or "",
            "ohcc_load":     movie.load     or "",
        }
        # None 값 제거 (Chroma 메타데이터는 None 허용 안 함)
        metadata = {k: v for k, v in metadata.items() if v is not None}

        self.vectorstore._collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata],
            embeddings=[self.embeddings.embed_query(text)],
        )
        logger.info("Chroma upsert: %s (tmdb_id=%s)", movie.title_ko, movie.tmdb_id)

    def delete_movie(self, tmdb_id: int) -> None:
        """Chroma에서 영화 벡터 삭제 (Django 레코드 삭제 시 자동 호출)."""
        self.vectorstore._collection.delete(ids=[str(tmdb_id)])
        logger.info("Chroma delete: tmdb_id=%s", tmdb_id)

    # ── Pitch 생성 (Ollama) ────────────────────────────────────

    def generate_pitches(self, movies: list, context: str) -> list:
        if not movies:
            return []
        n = len(movies)

        def _f(m, key):
            return (m.get(key, "") if isinstance(m, dict) else getattr(m, key, "")) or ""

        movies_text = "\n".join(
            f"{i+1}. {_f(m, 'title_ko')} ({_f(m, 'year')}) "
            f"— {_f(m, 'genres')} — {_f(m, 'llm_4pillar')[:80]}"
            for i, m in enumerate(movies)
        )
        format_lines = "\n".join(f"{i+1}: [2문장]" for i in range(n))
        prompt = PITCH_PROMPT.format(context=context, n=n, movies=movies_text, format=format_lines)
        try:
            # resp = self.gemini.models.generate_content(model=self.pitch_model, ...)  # Gemini pitch
            raw = self.llm.invoke(prompt).content  # Ollama pitch

            # (?m): 멀티라인 모드 — 각 줄 시작의 "1:", "2.", "3：" 등을 구분자로 분할
            num_pat = "|".join(str(i + 1) for i in range(n))
            parts = re.split(rf'(?m)^\s*(?:{num_pat})\s*[:.：]\s*', raw)

            if len(parts) < 2:
                logger.warning("[generate_pitches] 파싱 실패 — LLM 원문: %r", raw[:200])
                return [""] * n

            pitches = []
            for i in range(n):
                if i + 1 < len(parts):
                    text = parts[i + 1].strip()
                    text = re.sub(r"^\*\*[^*]+\*\*\s*", "", text)  # **제목** 제거
                    text = re.sub(r"^\[[^\]]+\]\s*", "", text)      # [제목] 제거
                    text = text.split("\n")[0].strip()               # 다음 번호 전까지만
                    pitches.append(text)
                else:
                    pitches.append("")
            logger.info("[generate_pitches] 완료 %d편 (비어있음: %d)",
                        n, sum(1 for p in pitches if not p))
            return pitches
        except Exception as e:
            logger.warning("[generate_pitches] Gemini 호출 실패 (pitch 생략): %s", e)
            return [""] * n
