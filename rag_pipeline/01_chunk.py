"""
[STEP 1] 문서 준비 — 영화 1편 = 벡터 1개

청킹을 하지 않습니다.

  왜 청킹하지 않는가?
  - 이 RAG의 목적은 "쿼리에 어울리는 영화"를 찾는 것이지,
    "쿼리와 유사한 텍스트 조각"을 찾는 게 아님
  - 200자 청크로 쪼개면 "재밌는 영화" 한 마디가 장르/맥락 없이
    쿼리와 매칭돼 엉뚱한 영화가 올라오는 문제가 생김
  - BGE-M3 최대 ~8,000 토큰 ≈ 한글 약 4,500자
    평균 1,732자이므로 대부분 1개 벡터에 충분히 담김

실행: python rag_pipeline/01_chunk.py
출력: output/movie_chunks.json
"""

import json
import re
from pathlib import Path

import pandas as pd

SOURCE_CSV  = "data/movie_enriched.csv"
TEXT_COLUMN = "enriched_text"
MIN_LEN     = 10
MAX_CHARS   = 4500  # BGE-M3 토큰 한도(8192) 기준 한글 안전 상한

TMDB_COLS = [
    "tmdb_director", "tmdb_genres", "tmdb_cast", "tmdb_country",
    "tmdb_release_year", "tmdb_runtime", "tmdb_language", "tmdb_ott",
]

# ChromaDB 메타데이터에 추가 저장할 컬럼 (enriched_text에는 미포함)
# pos_tones / neg_tones: $contains 필터용 키워드 리스트 (쉼표 구분 문자열)
# focused_summary_neg: 리랭킹 텍스트 필터용
META_EXTRA = [
    "pos_property_tags", "pos_tones",
    "neg_property_tags", "neg_tones",
    "focused_summary_neg",
]

OUTPUT_PATH = "output/movie_chunks.json"

_MD_RE = re.compile(r"\*{1,2}([^*]+)\*{1,2}")  # **텍스트** / *텍스트*


def _clean_text(text: str) -> str:
    """4-Pillar LLM 출력에 남은 마크다운 잔재 제거."""
    text = _MD_RE.sub(r"\1", text)           # ** ** / * * 제거
    text = re.sub(r"\*+", "", text)          # 남은 * 제거
    text = re.sub(r"설명:\s*", "", text)     # 반복된 '설명:' 접두어 제거
    text = re.sub(r"\s{2,}", " ", text)      # 연속 공백 정리
    return text.strip()


def main():
    print("=" * 60)
    print("[STEP 1] 문서 준비 (영화 1편 = 벡터 1개)")
    print("=" * 60)

    df = pd.read_csv(SOURCE_CSV, on_bad_lines="skip", engine="python")
    df["tmdb_id"] = pd.to_numeric(df["tmdb_id"], errors="coerce")
    print(f"\n원본 데이터: {len(df):,}편")

    available_tmdb = [c for c in TMDB_COLS if c in df.columns]
    available_extra = [c for c in META_EXTRA if c in df.columns]

    all_docs  = []
    skipped   = 0
    truncated = 0

    for _, row in df.iterrows():
        text = row.get(TEXT_COLUMN, "")
        if not isinstance(text, str) or len(text.strip()) < MIN_LEN:
            skipped += 1
            continue

        text = _clean_text(text)

        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS]
            truncated += 1

        tmdb_id = int(row["tmdb_id"]) if pd.notna(row.get("tmdb_id")) else 0

        all_docs.append({
            "id":          str(tmdb_id),        # tmdb_id를 고유 키로 사용
            "tmdb_id":     tmdb_id,
            "movie_title": row["movie_title"],
            "text":        text,
            "char_count":  len(text),
            **{col: str(row[col]) for col in available_tmdb if pd.notna(row.get(col))},
            **{col: str(row[col]) for col in available_extra if pd.notna(row.get(col))},
        })

    lengths = [d["char_count"] for d in all_docs]
    print(f"문서 수    : {len(all_docs):,}편  (스킵: {skipped}편 / 길이 초과 truncate: {truncated}편)")
    print(f"텍스트 길이: 평균 {sum(lengths)//len(lengths):,}자  최소 {min(lengths):,}자  최대 {max(lengths):,}자")

    Path("output").mkdir(exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)

    print(f"\n저장 완료: {OUTPUT_PATH}")
    print(f"다음 단계 → python rag_pipeline/02_embed_store.py")


if __name__ == "__main__":
    main()
