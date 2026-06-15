"""
[STEP 0-B] 4-Pillar LLM 전처리 (Ollama + EXAONE 3.5:2.4b)

각 영화에 대해 LLM이 검색 친화적인 자연어 설명을 생성합니다.

  4-Pillar란?
  - 감성/무드  : 어떤 감정 상태일 때 어울리는가
  - 소재/테마  : 어떤 주제를 다루는가
  - 관람 상황  : 어떤 상황에서 보기 좋은가
  - 스타일     : 어떤 특성의 영화인가

  왜 필요한가?
  - "퇴근 후 지쳐서 볼 영화" 쿼리와 영화 리뷰 사이의 언어적 간극을 메움
  - 리뷰가 "재밌는 영화" 한 줄뿐이어도 LLM이 전체 맥락을 해석해 설명 생성

  체크포인트:
  - output/4pillar_cache.json 에 저장, 50편마다 자동 저장
  - 중단 후 재실행하면 이어서 진행

실행: python3 pipeline/00b_4pillar.py
출력: aggregated_movie_enriched.csv (llm_4pillar 컬럼 추가 + enriched_text 갱신)
"""

import json
import time
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from langchain_ollama import ChatOllama

# --- 설정값 ---
OLLAMA_MODEL = "exaone3.5:2.4b"
SOURCE_CSV = "data/movie_enriched.csv"
CACHE_PATH = "output/4pillar_cache.json"
SAVE_EVERY = 50

PROMPT = """다음 영화를 검색할 때 유용한 설명을 두 문장으로 작성하세요.
어떤 감성/무드일 때 어울리는지, 어떤 소재/테마인지, 어떤 상황에서 볼만한지, 어떤 스타일인지 포함하세요.
영화 제목은 언급하지 말고 특성만 설명하세요.

예시)
장르: 로맨스, 드라마
줄거리: 평범한 두 남녀가 우연히 만나 사랑에 빠지는 이야기
리뷰: 감동적이고 눈물나는 영화, 연인 생각나는 영화
설명: 사랑에 빠지고 싶거나 감성적인 기분일 때 보기 좋은 잔잔한 멜로 영화다. 연인과 함께 보면 더 좋고, 혼자 보면 설레고 외로운 감정을 동시에 느낄 수 있다.

장르: {genres}
줄거리: {overview}
리뷰: {reviews}
설명:"""


def load_cache() -> dict:
    if Path(CACHE_PATH).exists():
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def generate(row: pd.Series, llm: ChatOllama) -> str:
    genres = str(row.get("tmdb_genres") or "")
    overview = str(row.get("tmdb_overview") or "")[:300]
    reviews = str(row.get("combined_reviews") or "")[:200]

    if not genres and not overview and not reviews:
        return ""

    prompt = PROMPT.format(genres=genres, overview=overview, reviews=reviews)
    try:
        result = llm.invoke(prompt).content.strip()
        # 두 문장 이상이면 앞 두 문장만 사용
        sentences = [s.strip() for s in result.replace("\\n", " ").split(". ") if s.strip()]
        return ". ".join(sentences[:2]) + ("." if sentences else "")
    except Exception as e:
        print(f"  [오류] {row['movie_title']}: {e}")
        return ""


def rebuild_enriched_text(row: pd.Series) -> str:
    parts = []
    genres = str(row.get("tmdb_genres") or "")
    overview = str(row.get("tmdb_overview") or "")
    pillar = str(row.get("llm_4pillar") or "")
    reviews = str(row.get("combined_reviews") or "")

    if genres and genres != "nan":
        parts.append(f"장르: {genres}")
    if pillar and pillar != "nan":
        parts.append(f"추천설명: {pillar}")
    if overview and overview != "nan":
        parts.append(f"줄거리: {overview}")
    if reviews and reviews != "nan":
        parts.append(f"리뷰: {reviews}")
    return " ".join(parts)


def main():
    print("=" * 60)
    print(f"[STEP 0-B] 4-Pillar 전처리  모델: {OLLAMA_MODEL}")
    print("=" * 60)

    df = pd.read_csv(SOURCE_CSV, on_bad_lines="skip", engine="python")
    print(f"\n대상 영화: {len(df):,}편")

    cache = load_cache()
    already = len(cache)
    todo = [row for _, row in df.iterrows() if row["movie_title"] not in cache]
    print(f"완료: {already:,}편  |  남은 작업: {len(todo):,}편\n")

    if not todo:
        print("모든 영화 처리 완료. enriched_text 갱신 중...")
    else:
        llm = ChatOllama(model=OLLAMA_MODEL, temperature=0)
        print("모델 로드 완료\n")

        for i, row in enumerate(tqdm(todo, desc="4-Pillar 생성"), 1):
            desc = generate(row, llm)
            cache[row["movie_title"]] = desc

            if i % SAVE_EVERY == 0:
                save_cache(cache)

        save_cache(cache)
        print(f"\n생성 완료: {len(cache):,}편")

    # llm_4pillar 컬럼 추가 및 enriched_text 갱신
    df["llm_4pillar"] = df["movie_title"].map(cache).fillna("")
    df["enriched_text"] = df.apply(rebuild_enriched_text, axis=1)
    df.to_csv(SOURCE_CSV, index=False, encoding="utf-8-sig")

    print(f"\nCSV 저장 완료: {SOURCE_CSV}")
    print(f"\n다음 단계 → python3 pipeline/01_chunk.py && python3 pipeline/02_embed_store.py")


if __name__ == "__main__":
    main()
