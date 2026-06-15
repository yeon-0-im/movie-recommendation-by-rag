"""
[STEP 3] LLM 쿼리 파서 (Ollama + EXAONE 3.5:2.4b)

자연어 쿼리를 분석해 filters + semantic_query로 분리합니다.

  왜 LLM 파서가 필요한가?
  - 규칙 기반: "이창동"이 감독인지 배우인지 판단 불가
  - LLM: 문맥으로 역할을 이해하고 적절한 필드에 배치

  few-shot 프롬프트:
  - 소형 모델(2.4B)은 예시를 줘야 JSON 형식을 정확히 따름
  - 예시 3개로 감독/유사도/혼합 세 유형 커버

  parse_query() 반환값:
  {
    "filters": {
      "tmdb_director": "크리스토퍼 놀란",  ← None이면 필터 미적용
      "tmdb_cast": None,
      "tmdb_genres": None,
      "tmdb_release_year": None,
      "tmdb_language": None,
      "tmdb_ott": None
    },
    "semantic_query": "실직 후 위로가 되는 영화"  ← 빈 문자열이면 유사도 검색 미적용
  }
"""

import json
import re
from langchain_ollama import ChatOllama

# --- 설정값 ---
OLLAMA_MODEL = "exaone3.5:2.4b"

FEW_SHOT_PROMPT = """영화 검색 쿼리에서 필터와 검색어를 추출해 JSON으로만 출력하세요.

필터 규칙:
- tmdb_director: 감독 이름 (사람 이름일 때만)
- tmdb_cast: 배우 이름 (사람 이름일 때만)
- tmdb_genres: 표준 장르만 (드라마/액션/코미디/로맨스/스릴러/공포/SF/판타지/애니메이션/다큐멘터리/범죄/모험 중 하나). 학교폭력·직장·복수 같은 소재/테마는 genres가 아닌 semantic_query로 처리
- tmdb_release_year: 출시 연도 (숫자만)
- tmdb_language: 언어 (한국어/영어/일본어/프랑스어/중국어 중 하나). "일본 영화"→"일본어", "프랑스 영화"→"프랑스어", "한국 영화"→"한국어", "미국 영화"→"영어"
- tmdb_ott: 스트리밍 서비스 (Netflix/Disney Plus/Watcha 등 영어 브랜드명)
- 국가·언어 정보는 tmdb_director가 아닌 tmdb_language에 넣을 것
- exclude_filters: "제외", "빼고", "말고" 같은 표현이 있을 때, 제외할 조건을 위 필드 형식으로 지정. 포함 조건은 filters, 제외 조건은 exclude_filters에 각각 넣을 것

예시1)
입력: "이창동 영화"
출력: {"filters": {"tmdb_director": "이창동", "tmdb_cast": null, "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": null, "tmdb_ott": null}, "exclude_filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": null, "tmdb_ott": null}, "semantic_query": ""}

예시2)
입력: "퇴근 후 스트레스 풀기 좋은 영화"
출력: {"filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": null, "tmdb_ott": null}, "exclude_filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": null, "tmdb_ott": null}, "semantic_query": "퇴근 후 스트레스 풀기 좋은 영화"}

예시3)
입력: "넷플릭스에서 볼 수 있는 2020년 이후 공포 영화"
출력: {"filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": "공포", "tmdb_release_year": "2020", "tmdb_language": null, "tmdb_ott": "Netflix"}, "exclude_filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": null, "tmdb_ott": null}, "semantic_query": "공포 영화"}

예시4)
입력: "송강호 나오는 감동적인 한국 영화"
출력: {"filters": {"tmdb_director": null, "tmdb_cast": "송강호", "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": "한국어", "tmdb_ott": null}, "exclude_filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": null, "tmdb_ott": null}, "semantic_query": "감동적인 영화"}

예시5)
입력: "미국영화 제외하고 감동적인 영화"
출력: {"filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": null, "tmdb_ott": null}, "exclude_filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": "영어", "tmdb_ott": null}, "semantic_query": "감동적인 영화"}

예시6)
입력: "미국영화 제외"
출력: {"filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": null, "tmdb_ott": null}, "exclude_filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": "영어", "tmdb_ott": null}, "semantic_query": ""}

예시7)
입력: "액션 빼고 스트레스 풀 수 있는 영화"
출력: {"filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": null, "tmdb_release_year": null, "tmdb_language": null, "tmdb_ott": null}, "exclude_filters": {"tmdb_director": null, "tmdb_cast": null, "tmdb_genres": "액션", "tmdb_release_year": null, "tmdb_language": null, "tmdb_ott": null}, "semantic_query": "스트레스 풀 수 있는 영화"}

입력: "{query}"
출력:"""

_EMPTY_FILTERS = {
    "tmdb_director": None,
    "tmdb_cast": None,
    "tmdb_genres": None,
    "tmdb_release_year": None,
    "tmdb_language": None,
    "tmdb_ott": None,
}

EMPTY_RESULT = {
    "filters": dict(_EMPTY_FILTERS),
    "exclude_filters": dict(_EMPTY_FILTERS),
    "semantic_query": "",
}


def parse_query(query: str, llm: ChatOllama) -> dict:
    """
    자연어 쿼리 → {filters, semantic_query}.
    파싱 실패 시 전체를 semantic_query로 처리 (안전한 폴백).
    """
    prompt = FEW_SHOT_PROMPT.replace("{query}", query)
    response = llm.invoke(prompt).content

    # 응답에서 JSON 블록 추출
    raw = re.search(r"\{.*\}", response, re.DOTALL)
    if not raw:
        return {**EMPTY_RESULT, "semantic_query": query}

    try:
        parsed = json.loads(raw.group())
    except json.JSONDecodeError:
        return {**EMPTY_RESULT, "semantic_query": query}

    def _clean(raw_filters: dict) -> dict:
        return {k: (v if v and v != "null" else None) for k, v in raw_filters.items()}

    clean_filters = _clean(parsed.get("filters", {}))
    clean_excludes = _clean(parsed.get("exclude_filters", {}))
    semantic = parsed.get("semantic_query", query).strip()

    return {"filters": clean_filters, "exclude_filters": clean_excludes, "semantic_query": semantic}


def load_llm() -> ChatOllama:
    return ChatOllama(model=OLLAMA_MODEL, temperature=0)


# ── 단독 실행 시 테스트 ───────────────────────────────────────

TEST_QUERIES = [
    "이창동 영화",
    "퇴근 후 스트레스 풀기 좋은 영화",
    "실직 후 볼만한 크리스토퍼 놀란 영화",
    "송강호 나오는 감동적인 영화",
    "넷플릭스에서 볼 수 있는 2019년 한국 스릴러",
]

if __name__ == "__main__":
    print("=" * 60)
    print(f"[STEP 4] 쿼리 파서 테스트  모델: {OLLAMA_MODEL}")
    print("=" * 60)

    llm = load_llm()
    print("모델 로드 완료\n")

    for query in TEST_QUERIES:
        result = parse_query(query, llm)
        active_filters = {k: v for k, v in result["filters"].items() if v}
        print(f"쿼리   : {query}")
        print(f"필터   : {active_filters if active_filters else '없음'}")
        print(f"검색어 : {result['semantic_query'] or '없음'}")
        print("-" * 50)
