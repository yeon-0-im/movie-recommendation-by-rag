"""
[STEP 0] 리뷰·메타데이터 병합 → enriched_text 생성

movie_db.csv + review_db.csv 를 합쳐 임베딩용 텍스트를 만든다.
TMDB API 재호출 없음 — build_movie_db.py 가 이미 모든 메타데이터를 수집했기 때문.

  대상: movie_db.csv 중 ott != '' 인 영화 (OTT 보유 영화만)

  enriched_text 구성:
    장르: {genres}  줄거리: {overview_ko}  리뷰: {combined_reviews}

  출력 컬럼 (하위 스크립트 00b_4pillar.py / 01_chunk.py 호환):
    movie_title, tmdb_id, tmdb_genres, tmdb_director, tmdb_cast,
    tmdb_country, tmdb_release_year, tmdb_runtime, tmdb_language, tmdb_ott,
    tmdb_overview, is_major, combined_reviews, enriched_text

실행: python rag_pipeline/00_enrich_tmdb.py
출력: data/movie_enriched.csv
"""

import pandas as pd

MOVIE_DB  = "data/movie_db.csv"
REVIEW_DB = "data/review_db.csv"
OUTPUT_CSV = "data/movie_enriched.csv"
TOP_N = 5  # positive / negative 각 상위 N개


def build_combined_reviews(group: pd.DataFrame) -> str:
    pos = (
        group[group["sentiment"] == "positive"]
        .sort_values("rank")
        .head(TOP_N)["clean_text"]
    )
    neg = (
        group[group["sentiment"] == "negative"]
        .sort_values("rank")
        .head(TOP_N)["clean_text"]
    )
    texts = [t for t in list(pos) + list(neg) if isinstance(t, str) and t.strip()]
    return " | ".join(texts)


def build_enriched_text(row: pd.Series) -> str:
    parts = []
    for label, col in [("장르", "tmdb_genres"), ("줄거리", "tmdb_overview"), ("리뷰", "combined_reviews")]:
        val = str(row.get(col) or "").strip()
        if val and val != "nan":
            parts.append(f"{label}: {val}")
    return " ".join(parts)


def main():
    print("=" * 60)
    print("[STEP 0] 리뷰·메타데이터 병합")
    print("=" * 60)

    # ── movie_db 로드 (OTT 보유 영화만) ──────────────────────────
    movie_df = pd.read_csv(MOVIE_DB, dtype=str, engine="python", on_bad_lines="skip").fillna("")
    movie_df = movie_df[movie_df["ott"] != ""]
    movie_df["tmdb_id"] = pd.to_numeric(movie_df["tmdb_id"], errors="coerce")
    movie_df = movie_df[movie_df["tmdb_id"].notna()]
    movie_df["tmdb_id"] = movie_df["tmdb_id"].astype(int)
    print(f"\nmovie_db (OTT 보유): {len(movie_df):,}편")

    # ── review_db 로드 → combined_reviews 생성 ───────────────────
    review_df = pd.read_csv(REVIEW_DB, dtype=str, engine="python", on_bad_lines="skip").fillna("")
    review_df["tmdb_id"] = pd.to_numeric(review_df["tmdb_id"], errors="coerce")
    review_df = review_df[review_df["tmdb_id"].notna()]
    review_df["tmdb_id"] = review_df["tmdb_id"].astype(int)
    review_df["rank"]    = pd.to_numeric(review_df["rank"], errors="coerce").fillna(99).astype(int)
    print(f"review_db: {len(review_df):,}개 리뷰")

    combined = (
        review_df
        .groupby("tmdb_id", group_keys=False)
        .apply(build_combined_reviews)
        .reset_index()
    )
    combined.columns = ["tmdb_id", "combined_reviews"]
    print(f"리뷰 커버: {len(combined):,}편")

    # ── 병합 ─────────────────────────────────────────────────────
    df = movie_df.merge(combined, on="tmdb_id", how="left")
    df["combined_reviews"] = df["combined_reviews"].fillna("")

    # ── 컬럼 매핑 (하위 스크립트 호환) ───────────────────────────
    df = df.rename(columns={
        "title_ko":    "movie_title",
        "genres":      "tmdb_genres",
        "director":    "tmdb_director",
        "cast":        "tmdb_cast",
        "country":     "tmdb_country",
        "year":        "tmdb_release_year",
        "runtime":     "tmdb_runtime",
        "language":    "tmdb_language",
        "ott":         "tmdb_ott",
        "overview_ko": "tmdb_overview",
    })

    # ── 리뷰 없는 영화 인덱스 제외 ───────────────────────────────
    no_review_df = df[df["combined_reviews"] == ""]
    if not no_review_df.empty:
        print(f"\n리뷰 없음 → {len(no_review_df)}편 인덱스 제외:")
        for _, r in no_review_df.iterrows():
            print(f"  [{r['tmdb_id']}] {r['movie_title']}")
    df = df[df["combined_reviews"] != ""].copy()

    # ── enriched_text 생성 ────────────────────────────────────────
    df["enriched_text"] = df.apply(build_enriched_text, axis=1)

    # ── 저장 ─────────────────────────────────────────────────────
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    no_overview = (df["tmdb_overview"] == "").sum()
    no_text     = (df["enriched_text"].str.strip() == "").sum()
    print(f"\n저장 완료: {OUTPUT_CSV} ({len(df):,}편)")
    print(f"  줄거리 없음  : {no_overview}편  ← fetch_watcha_overview.py 로 보강 가능")
    print(f"  enriched 빈값: {no_text}편")
    print(f"\n다음 단계 → python rag_pipeline/00b_4pillar.py")


if __name__ == "__main__":
    main()
