"""
[STEP 4] RAG 검색(Retrieval) — LangChain 버전

두 가지 검색 모드를 지원합니다:

  1. 유사도 검색 (기본)
     - 리뷰 텍스트 기반 코사인 유사도
     - 감성/분위기 쿼리에 적합
     - 예) "슬프고 감동적인 영화", "아무 생각 없이 볼 수 있는"

  2. 메타데이터 필터 검색 (prefix 입력)
     - ChromaDB metadata를 exact 매칭으로 필터
     - 감독/배우/장르처럼 정확한 값을 알 때 사용
     - 예) /감독:크리스토퍼 놀란
           /배우:송강호
           /장르:SF
           /국가:France
           /연도:2020년 이후
           /언어:한국어
           /OTT:넷플릭스

  왜 두 모드가 필요한가?
  - 유사도 검색: "크리스토퍼 놀란"이 리뷰에 없으면 못 찾음
  - 메타데이터 필터: 정확한 이름/장르를 알면 100% 매칭
  - 두 방식을 목적에 맞게 선택해서 쓰는 것이 올바른 RAG 설계

실행: python3 pipeline/04_rag_search.py
전제: chroma_db/ 존재 (02_embed_store.py 먼저 실행)
"""

import importlib.util
import torch
from langchain_community.embeddings import HuggingFaceBgeEmbeddings, HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# 숫자로 시작하는 파일명은 import 불가 → importlib으로 로드
_spec = importlib.util.spec_from_file_location("query_parser", "rag_pipeline/03_query_parser.py")
_mod  = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
parse_query = _mod.parse_query
load_llm    = _mod.load_llm

# --- BGE-M3 설정 (02_embed_store.py 와 쌍) ---
MODEL_NAME = "BAAI/bge-m3"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "movie_reviews"
EMBEDDING_CLASS = HuggingFaceBgeEmbeddings

# --- HuggingFace 설정 (02_embed_store_huggingface.py 와 쌍) ---
# MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# CHROMA_PATH = "./chroma_db_hf"
# COLLECTION_NAME = "movie_reviews_hf"
# EMBEDDING_CLASS = HuggingFaceEmbeddings

TOP_K = 15
SIMILARITY_THRESHOLD = 0.5  # 이 점수 미만이면 "관련 없음"으로 처리

# 명시적 prefix → ChromaDB metadata 필드명
META_PREFIX = {
    "/감독:":   "tmdb_director",
    "/배우:":   "tmdb_cast",
    "/장르:":   "tmdb_genres",
    "/국가:":   "tmdb_country",
    "/연도:":   "tmdb_release_year",
    "/언어:":   "tmdb_language",
    "/OTT:":   "tmdb_ott",
    "/런타임:":  "tmdb_runtime",
}

# exact 매칭 필드 (ChromaDB $eq 사용) vs substring 매칭 필드 (Python 필터)
EXACT_FIELDS = {"tmdb_director", "tmdb_release_year", "tmdb_language"}

# DB는 ISO 코드로 저장 ("en", "ko", ...) — LLM은 한국어로 출력 → 변환 필요
LANGUAGE_CODE_MAP = {
    "한국어": "ko", "영어": "en", "일본어": "ja", "프랑스어": "fr",
    "스페인어": "es", "중국어": "zh", "이탈리아어": "it", "독일어": "de",
    "포르투갈어": "pt", "힌디어": "hi", "태국어": "th",
}
COUNTRY_CODE_MAP = {
    "한국": "KR", "미국": "US", "영국": "GB", "일본": "JP",
    "프랑스": "FR", "스페인": "ES", "중국": "CN", "이탈리아": "IT",
    "독일": "DE", "캐나다": "CA", "호주": "AU", "인도": "IN",
}


def _normalize_value(field: str, value: str) -> str:
    """LLM이 출력한 한국어 값을 DB 저장 형식(ISO 코드)으로 변환."""
    if field == "tmdb_language":
        return LANGUAGE_CODE_MAP.get(value, value)
    if field == "tmdb_country":
        return COUNTRY_CODE_MAP.get(value, value)
    return value


def _is_excluded(meta: dict, exclude_filters: dict) -> bool:
    """제외 필터 중 하나라도 메타데이터와 매칭되면 True."""
    for field, value in exclude_filters.items():
        if not value:
            continue
        norm = _normalize_value(field, value)
        field_val = meta.get(field, "")
        if field in EXACT_FIELDS:
            if field_val == norm:
                return True
        else:
            if norm in field_val:
                return True
    return False


def get_device() -> str:
    """CUDA → CPU (MPS는 긴 시퀀스 attention 시 버퍼 오버플로 발생)."""
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


# ── 자동 라우팅용 메타데이터 인덱스 ───────────────────────────

def build_meta_index(vectorstore: Chroma) -> dict[str, tuple[str, str]]:
    """
    DB에 저장된 감독/배우 이름을 인덱싱.
    반환: { "이창동": ("tmdb_director", "이창동"), ... }

    장르/국가는 일반 단어와 겹칠 수 있어 자동 감지에서 제외.
    (예: "드라마 같은 영화"에서 "드라마"가 오탐지됨)

    긴 이름을 먼저 저장해 "매튜 매커너히"가 "매튜"보다 우선 매칭되게 함.
    """
    col = vectorstore._collection
    raw = col.get(limit=col.count(), include=["metadatas"])

    candidates = {}  # value → (field, value)

    for meta in raw["metadatas"]:
        # 배우 먼저 (감독이 덮어쓰면서 감독이 우선순위 가짐)
        for actor in meta.get("tmdb_cast", "").split(", "):
            if a := actor.strip():
                candidates[a] = ("tmdb_cast", a)
        # 감독이 배우를 덮어써서 최종적으로 감독 우선
        if director := meta.get("tmdb_director", "").strip():
            candidates[director] = ("tmdb_director", director)

    # 긴 이름이 먼저 검사되도록 정렬 (부분 매칭 방지)
    return dict(sorted(candidates.items(), key=lambda x: len(x[0]), reverse=True))


def detect_meta_query(query: str, index: dict) -> tuple[str, str] | None:
    """
    자연어 쿼리에서 알려진 감독/배우 이름을 자동 감지.
    감지되면 (field, value) 반환, 없으면 None.
    """
    for name, (field, value) in index.items():
        if name in query:
            return field, value
    return None


# ── 유사도 검색 ────────────────────────────────────────────────

def parse_enriched_text(text: str) -> tuple[str, str]:
    """enriched_text에서 줄거리, 리뷰 부분을 분리해 반환."""
    overview, reviews = "", ""
    if "줄거리: " in text:
        s = text.find("줄거리: ") + len("줄거리: ")
        e = text.find("리뷰: ") if "리뷰: " in text else len(text)
        overview = text[s:e].strip()
    if "리뷰: " in text:
        reviews = text[text.find("리뷰: ") + len("리뷰: "):].strip()
    return overview, reviews


def semantic_search(query: str, vectorstore: Chroma) -> list:
    # similarity_search_with_relevance_scores는 LangChain 버전에 따라
    # 낮은 점수를 내부 threshold로 잘라버릴 수 있어서 직접 호출
    raw = vectorstore.similarity_search_with_score(query, k=TOP_K)

    results = []
    for doc, distance in raw:
        similarity = max(0.0, 1.0 - distance / 2.0)
        overview, reviews = parse_enriched_text(doc.page_content)
        results.append({
            "movie": doc.metadata["movie_title"],
            "similarity": similarity,
            "meta": doc.metadata,
            "overview": overview,
            "reviews": reviews,
        })
    return results


# ── 메타데이터 필터 검색 ───────────────────────────────────────

def meta_search(field: str, value: str, vectorstore: Chroma, exclude_filters: dict | None = None) -> list:
    """
    ChromaDB metadata를 기준으로 필터 검색.

    감독(tmdb_director): ChromaDB $eq 필터로 exact 매칭
    배우/장르/국가    : 여러 값이 쉼표로 저장되어 있어
                       ChromaDB가 substring 필터를 지원하지 않으므로
                       전체 조회 후 Python에서 부분 문자열 매칭
    """
    col = vectorstore._collection

    if field in EXACT_FIELDS:
        # 감독/연도/언어: ChromaDB $eq 필터 (exact 매칭, 빠름)
        # LLM 출력값("영어")을 DB 저장 형식("en")으로 정규화
        norm_value = _normalize_value(field, value)
        raw = col.get(
            where={field: norm_value},
            include=["documents", "metadatas"],
        )
    else:
        # 배우/장르/국가/OTT/런타임: 쉼표 구분 다중값 → Python substring 필터
        raw = col.get(limit=col.count(), include=["documents", "metadatas"])
        matched_idx = [
            i for i, m in enumerate(raw["metadatas"])
            if value in m.get(field, "")
        ]
        raw = {
            "documents": [raw["documents"][i] for i in matched_idx],
            "metadatas": [raw["metadatas"][i] for i in matched_idx],
        }

    # 제외 필터 적용
    if exclude_filters:
        keep = [
            i for i, m in enumerate(raw["metadatas"])
            if not _is_excluded(m, exclude_filters)
        ]
        raw = {
            "documents": [raw["documents"][i] for i in keep],
            "metadatas": [raw["metadatas"][i] for i in keep],
        }

    # 영화 단위로 중복 제거 (첫 번째 청크만)
    results = []
    for doc, meta in zip(raw["documents"], raw["metadatas"]):
        results.append({"movie": meta["movie_title"], "meta": meta, "chunk": doc})
        if len(results) >= TOP_K:
            break

    return results



# ── 하이브리드 검색 ────────────────────────────────────────────

def hybrid_search(filters: dict, semantic_query: str, vectorstore: Chroma, exclude_filters: dict | None = None) -> list:
    """
    필터로 후보 영화를 추린 뒤, 그 안에서 유사도 검색.
    "실직 후 볼만한 크리스토퍼 놀란 영화" 같은 혼합 쿼리에 사용.
    """
    col = vectorstore._collection

    # 1단계: 필터로 후보 movie_title 집합 추출
    candidate_titles: set[str] = None

    for field, value in filters.items():
        if field in EXACT_FIELDS:
            raw = col.get(where={field: value}, include=["metadatas"])
        else:
            raw = col.get(limit=col.count(), include=["metadatas"])
            raw["metadatas"] = [m for m in raw["metadatas"] if value in m.get(field, "")]

        titles = {m["movie_title"] for m in raw["metadatas"]}
        candidate_titles = titles if candidate_titles is None else candidate_titles & titles

    if not candidate_titles:
        # 필터 조건에 맞는 영화가 없으면 유사도 검색으로 fallback
        print("  ※ 필터 조건에 맞는 영화가 없어 유사도 검색으로 대체합니다.")
        return semantic_search(semantic_query, vectorstore)

    # 2단계: 유사도 검색 후 후보 집합으로 필터링
    raw_semantic = vectorstore.similarity_search_with_score(
        semantic_query, k=TOP_K * 3  # 넉넉히 뽑아서 후보 안에서 추림
    )

    results = []
    for doc, distance in raw_semantic:
        movie = doc.metadata["movie_title"]
        if movie not in candidate_titles:
            continue
        if exclude_filters and _is_excluded(doc.metadata, exclude_filters):
            continue
        similarity = max(0.0, 1.0 - distance / 2.0)
        overview, reviews = parse_enriched_text(doc.page_content)
        results.append({
            "movie": movie,
            "similarity": similarity,
            "meta": doc.metadata,
            "overview": overview,
            "reviews": reviews,
        })
        if len(results) >= TOP_K:
            break

    return results


def exclude_search(exclude_filters: dict, semantic_query: str, vectorstore: Chroma) -> list:
    """
    EXACT 필드(tmdb_language 등)는 ChromaDB $ne 필터로 검색 단계에서 제외.
    나머지(장르·배우·OTT 등 다중값 필드)는 Python 후처리로 제외.
    post-filter만 쓰면 top-k가 제외 대상으로 가득 차서 결과가 비는 문제를 방지.
    """
    # $ne 조건: LLM 출력값("영어")을 DB 저장 형식("en")으로 변환 후 사용
    ne_conditions = [
        {field: {"$ne": _normalize_value(field, value)}}
        for field, value in exclude_filters.items()
        if value and field in EXACT_FIELDS
    ]
    python_excludes = {
        field: value
        for field, value in exclude_filters.items()
        if value and field not in EXACT_FIELDS
    }

    where = None
    if ne_conditions:
        where = ne_conditions[0] if len(ne_conditions) == 1 else {"$and": ne_conditions}

    kwargs: dict = {"k": TOP_K * 3}
    if where:
        kwargs["filter"] = where

    raw = vectorstore.similarity_search_with_score(semantic_query, **kwargs)

    results = []
    for doc, distance in raw:
        if python_excludes and _is_excluded(doc.metadata, python_excludes):
            continue
        similarity = max(0.0, 1.0 - distance / 2.0)
        overview, reviews = parse_enriched_text(doc.page_content)
        results.append({
            "movie": doc.metadata["movie_title"],
            "similarity": similarity,
            "meta": doc.metadata,
            "overview": overview,
            "reviews": reviews,
        })
        if len(results) >= TOP_K:
            break

    return results


# ── 출력 ───────────────────────────────────────────────────────

def print_semantic_results(query: str, results: list):
    print(f'\n[유사도 검색] "{query}"')
    print("=" * 65)
    shown = 0
    for rank, r in enumerate(results, 1):
        if r["similarity"] < SIMILARITY_THRESHOLD:
            continue
        m = r["meta"]
        bar = "█" * int(r["similarity"] * 20)
        print(f"  {rank}. {r['movie']}  [{r['similarity']:.3f}] {bar}")
        print(f"     장르    : {m.get('tmdb_genres', '-')}")
        print(f"     국적    : {m.get('tmdb_language', '-')}  |  런타임: {m.get('tmdb_runtime', '-')}")
        print(f"     감독    : {m.get('tmdb_director', '-')}  |  출연: {m.get('tmdb_cast', '-')[:50]}")
        if m.get("tmdb_ott"):
            print(f"     OTT     : {m['tmdb_ott']}")
        if r["overview"]:
            print(f"     줄거리  : {r['overview'][:120]}{'...' if len(r['overview']) > 120 else ''}")
        if r["reviews"]:
            print(f"     리뷰    : {r['reviews'][:120]}{'...' if len(r['reviews']) > 120 else ''}")
        print()
        shown += 1
    if shown == 0:
        print("  관련 영화를 찾지 못했습니다. (유사도 0.5 미만)")


def print_meta_results(field: str, value: str, results: list):
    label = {v: k.strip("/").rstrip(":") for k, v in META_PREFIX.items()}
    print(f'\n[메타데이터 검색] {label.get(field, field)}: "{value}" → {len(results)}편')
    print("=" * 65)
    for i, r in enumerate(results, 1):
        m = r["meta"]
        overview, reviews = parse_enriched_text(r["chunk"])
        print(f"  {i}. {r['movie']}")
        print(f"     장르    : {m.get('tmdb_genres', '-')}")
        print(f"     국적    : {m.get('tmdb_language', '-')}  |  런타임: {m.get('tmdb_runtime', '-')}")
        print(f"     감독    : {m.get('tmdb_director', '-')}  |  출연: {m.get('tmdb_cast', '-')[:50]}")
        if m.get("tmdb_ott"):
            print(f"     OTT     : {m['tmdb_ott']}")
        if overview:
            print(f"     줄거리  : {overview[:120]}{'...' if len(overview) > 120 else ''}")
        if reviews:
            print(f"     리뷰    : {reviews[:120]}{'...' if len(reviews) > 120 else ''}")
        print()


TEST_QUERIES = [
    "퇴근하고 지쳐서 아무 생각 없이 보기 좋은 영화",
    "울고 싶을 때 보는 슬프고 감동적인 영화",
    "스릴 있고 긴장감 넘치는 액션 영화",
    "사랑에 빠지고 싶을 때 보는 로맨스 영화",
    "아이와 함께 볼 수 있는 따뜻한 가족 영화",
    "반전이 있고 머리 쓰는 미스터리 스릴러",
    "가볍게 스트레스 풀 수 있는 범죄 코미디",
    "인생 영화, 꼭 봐야 하는 명작들"
]


def main():
    device = get_device()
    print(f"디바이스: {device}")
    print(f"모델 로드 중: {MODEL_NAME} ...")

    embeddings = EMBEDDING_CLASS(
        model_name=MODEL_NAME,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )

    vectorstore = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )
    print(f"DB: {vectorstore._collection.count():,}개 벡터 로드 완료")

    print("LLM 쿼리 파서 로드 중 (Ollama)...")
    llm = load_llm()
    print("준비 완료\n")

    # ── 자동 테스트 ─────────────────────────────────────────
    print("=" * 55)
    print("[자동 테스트] 유사도 검색 쿼리 6개")
    print("=" * 55)
    for query in TEST_QUERIES:
        results = semantic_search(query, vectorstore)
        print_semantic_results(query, results)

    # ── 대화형 검색 ────────────────────────────────────────
    print("\n\n" + "=" * 55)
    print("[직접 검색]")
    print("  자연어 입력  : LLM이 필터/검색어 자동 분리")
    print("  수동 prefix  : /감독:  /배우:  /장르:  /국가:  /연도:  /언어:  /OTT:")
    print("  종료         : q")
    print("=" * 55)

    while True:
        user_input = input("\n검색어 → ").strip()

        if not user_input or user_input.lower() == "q":
            print("종료합니다.")
            break

        # 수동 prefix가 있으면 그대로 처리
        matched_prefix = next((p for p in META_PREFIX if user_input.startswith(p)), None)
        if matched_prefix:
            field = META_PREFIX[matched_prefix]
            value = user_input[len(matched_prefix):]
            results = meta_search(field, value, vectorstore)
            print_meta_results(field, value, results)
            continue

        # LLM 쿼리 파싱
        parsed = parse_query(user_input, llm)
        active_filters  = {k: v for k, v in parsed["filters"].items() if v}
        exclude_filters = {k: v for k, v in parsed.get("exclude_filters", {}).items() if v}
        semantic = parsed["semantic_query"]

        print(f"  → 필터: {active_filters or '없음'}  |  제외: {exclude_filters or '없음'}  |  검색어: \"{semantic or user_input}\"")

        if active_filters and semantic:
            # 혼합: 필터로 후보 추린 뒤 유사도 검색 (제외 필터 함께 적용)
            results = hybrid_search(active_filters, semantic, vectorstore, exclude_filters or None)
            print_semantic_results(user_input, results)
        elif active_filters:
            # 포함 필터만 (제외 필터 함께 적용)
            for field, value in active_filters.items():
                results = meta_search(field, value, vectorstore, exclude_filters or None)
                print_meta_results(field, value, results)
        elif exclude_filters:
            # 제외 필터만: 유사도 검색 후 해당 영화 제거
            results = exclude_search(exclude_filters, semantic or user_input, vectorstore)
            print_semantic_results(user_input, results)
        else:
            # 유사도만
            results = semantic_search(semantic or user_input, vectorstore)
            print_semantic_results(user_input, results)


if __name__ == "__main__":
    main()
