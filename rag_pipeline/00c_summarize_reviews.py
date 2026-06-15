"""
[STEP 0-C] LLM 리뷰 요약 — POS/NEG 분리 파이프라인 (V3)

review_db.csv의 긍정/부정 리뷰를 Gemini 2.0 Flash로 구조화한다.
영화 1편당 API 2회 호출 (POS / NEG 별도).

  POS 출력: property_tags, tones, viewing_context, focused_summary
  NEG 출력: property_tags, tones, focused_summary

  tones는 키워드 리스트로 저장 (수치화 없음).
  강도 구분은 enriched_text 임베딩의 코사인 유사도가 담당.

  무료 티어: 15 RPM / 1,500 req/day → 3,860회 / 약 2.6일 소요
  체크포인트: output/review_summary_cache.json (중단 후 재실행 가능)

사전 준비:
  pip install google-genai
  .env에 GOOGLE_API_KEY 설정

실행: python rag_pipeline/00c_summarize_reviews.py
출력: output/review_summary_cache.json
      data/movie_enriched.csv (7개 컬럼 추가 + enriched_text 재구성)
"""

import json
import os
import re
import time
from pathlib import Path

from google import genai
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

REVIEW_DB     = "data/review_db.csv"
ENRICHED_CSV  = "data/movie_enriched.csv"
CACHE_PATH    = "output/review_summary_cache.json"
SAVE_EVERY    = 10
REQUEST_DELAY = 4.5   # 15 RPM 기준 4초 + 여유
MAX_RETRIES   = 3
TOP_N         = 5

VALID_PROPERTY_TAGS = {"narrative", "visual", "audio", "performance", "pacing"}
VALID_TONES         = {"exhilarating", "suspenseful", "melancholic", "comforting", "intellectual"}

TONE_MAP = {
    "exhilarating": "카타르시스·유쾌함",
    "suspenseful":  "긴장감·스릴",
    "melancholic":  "묵직한 여운·잔잔한 슬픔",
    "comforting":   "따뜻함·힐링",
    "intellectual": "사유를 자극하는",
}

# ── 프롬프트 ────────────────────────────────────────────────────────

POS_PROMPT = """[System Role]
너는 영화의 핵심 유전자를 분석하여 정형화된 데이터(JSON)로 가공하는 구조화 엔지니어링 시스템이야.

[Input Variables]
- 영화 제목: {title_ko}
- 장르: {genres}
- 줄거리: {overview}
- 긍정 리뷰 묶음:
{positive_reviews}

[Core Instruction]
리뷰어들이 극찬하고 매력을 느낀 '요소'와 '정서'에만 집중해.
부정적 언급은 완전히 무시하고, 긍정 관점에서만 날카롭게 유전자를 추출해.

[Tagging Schema]

1. property_tags (최대 2개, 해당 없으면 빈 리스트)
긍정 리뷰에서 지배적으로 언급된 영화의 구성 요소를 선택해.
- "narrative": 인과관계·개연성·주제 의식·대사의 퀄리티·결말의 완성도 [What — 이야기의 내용]
- "visual": 미장센·영상미·색감·촬영·CG/VFX
- "audio": OST·음악·음향이 다른 요소와 독립적으로 언급된 경우만
- "performance": 배우 연기력·캐릭터 매력·케미
- "pacing": 편집 템포·완급 조절·러닝타임 체감 [How — 시간적 흐름]
※ narrative vs pacing: 이야기의 '내용'이 강점이면 narrative, '속도·흐름'이 강점이면 pacing

2. tones (명확히 드러나는 감성만 선택, 최대 3개, 해당 없으면 빈 리스트)
긍정 리뷰에서 명확히 반복되는 정서만 선택해. 확신이 없으면 넣지 마.
- "exhilarating": 카타르시스·통쾌함·유쾌한 웃음·속 시원함 [발산 에너지 — 풀리는 느낌]
- "suspenseful": 긴장감·소름·두근거림·아드레날린 [압박 에너지 — 조여드는 느낌]
- "melancholic": 묵직한 여운·아름다운 슬픔·잔잔한 고독
- "comforting": 따뜻함·힐링·위로·무해함
- "intellectual": 깊은 사유 유도·실험적 형식·여러 번 보게 되는 영화
※ exhilarating vs suspenseful: '풀리는·터지는 느낌'이면 exhilarating, '조여드는·쌓이는 느낌'이면 suspenseful

3. viewing_context (1문장, 50자 내외)
이 영화를 언제 누구와 보면 가장 좋은지 구체적인 상황 1문장.
상황(혼자/연인/가족/친구)과 분위기(저녁/주말/힘들 때/기분전환)를 함께 담을 것.
예시: "혼자 조용한 밤에 감성에 젖고 싶을 때, 또는 연인과 설레는 분위기에서 보기 좋다."

4. focused_summary (1문장, 80자 내외)
단순한 감정 표현("좋았다")은 배제하고, 리뷰어들이 이 영화의 '어떤 구체적 요소' 때문에
극찬했는지 핵심 인과관계를 요약해.
예시: "원색의 감각적인 미장센과 신스웨이브 사운드가 결합하여 눈과 귀를 사로잡는 시각적 쾌감을 선사함."

출력은 순수 JSON만. 마크다운 서식이나 설명 텍스트 없이.
{{
  "property_tags": [],
  "tones": [],
  "viewing_context": "",
  "focused_summary": ""
}}"""

NEG_PROMPT = """[System Role]
너는 영화의 핵심 유전자를 분석하여 정형화된 데이터(JSON)로 가공하는 구조화 엔지니어링 시스템이야.

[Input Variables]
- 영화 제목: {title_ko}
- 장르: {genres}
- 줄거리: {overview}
- 부정 리뷰 묶음:
{negative_reviews}

[Core Instruction]
리뷰어들이 지적한 '진입장벽', '실패 요소', '불만족스러운 정서'에만 집중해.
긍정적 언급은 완전히 무시하고, 부정 관점에서만 날카롭게 유전자를 추출해.

[Tagging Schema]

1. property_tags (최대 2개, 해당 없으면 빈 리스트)
부정 리뷰에서 지배적으로 언급된 실패한 구성 요소를 선택해.
- "narrative": 개연성 부족·허술한 플롯·실망스러운 결말·진부한 대사 [What — 이야기의 내용]
- "visual": 조악한 CG·촌스러운 미장센
- "audio": 음악·음향이 핵심 불만으로 독립적으로 언급된 경우만
- "performance": 어색한 연기·매력 없는 캐릭터·미스캐스팅
- "pacing": 늘어지는 편집·과도하게 빠른 컷·러닝타임 체감 [How — 시간적 흐름]
※ narrative vs pacing: 이야기의 '내용'이 문제면 narrative, '속도·흐름'이 문제면 pacing

2. tones (명확히 드러나는 부정 정서만 선택, 최대 3개, 해당 없으면 빈 리스트)
부정 리뷰어들이 실제로 경험한 불만족 정서만 선택해. 확신이 없으면 넣지 마.
- "exhilarating": 통쾌해야 할 순간이 싱겁거나 용두사미로 끝남
- "suspenseful": 긴장감 없이 지루하거나 결말이 뻔함
- "melancholic": 억지 감동·신파, 또는 보고 나서 지나치게 우울하고 불쾌함
- "comforting": 차갑거나 정서적으로 불쾌한 경험, 보고 나서 기분이 나빠짐
- "intellectual": 불친절하게 난해하여 이해 포기, 또는 너무 단순하고 유치함

3. focused_summary (1문장, 80자 내외)
단순한 감정 표현("나빴다")은 배제하고, 리뷰어들이 이 영화의 '어떤 구체적 요소' 때문에
실망했는지 핵심 인과관계를 요약해.
예시: "서사의 개연성이 부족하고 인물들의 행동이 불친절하여 스토리에 몰입하기 어렵고 지루함."

출력은 순수 JSON만. 마크다운 서식이나 설명 텍스트 없이.
{{
  "property_tags": [],
  "tones": [],
  "focused_summary": ""
}}"""


# ── 캐시 ─────────────────────────────────────────────────────────

def load_cache() -> dict:
    Path("output").mkdir(exist_ok=True)
    if Path(CACHE_PATH).exists():
        return json.loads(Path(CACHE_PATH).read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict):
    Path(CACHE_PATH).write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _is_pos_complete(entry: dict) -> bool:
    pos = entry.get("pos", {})
    return (
        bool(str(pos.get("viewing_context", "")).strip()) and
        bool(str(pos.get("focused_summary", "")).strip())
    )


def _is_neg_complete(entry: dict) -> bool:
    return bool(str(entry.get("neg", {}).get("focused_summary", "")).strip())


def is_complete(entry: dict) -> bool:
    return _is_pos_complete(entry) and _is_neg_complete(entry)


def _empty_pos() -> dict:
    return {"property_tags": [], "tones": [], "viewing_context": "", "focused_summary": ""}


def _empty_neg() -> dict:
    return {"property_tags": [], "tones": [], "focused_summary": ""}


# ── Gemini 호출 ───────────────────────────────────────────────────

def _coerce_list(val, valid_set: set) -> list:
    """LLM 출력이 리스트가 아닐 경우 강제 변환하고 유효 값만 필터링."""
    if isinstance(val, str):
        val = [v.strip() for v in val.split(",") if v.strip()]
    elif not isinstance(val, list):
        val = []
    return [v for v in val if v in valid_set]


def call_gemini(client: genai.Client, prompt: str, mode: str) -> dict | None:
    """mode: 'pos' | 'neg'"""
    required_str = (
        ["viewing_context", "focused_summary"] if mode == "pos"
        else ["focused_summary"]
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite", contents=prompt
            )
            text = response.text.strip()
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                raise ValueError("JSON 블록 없음")
            result = json.loads(m.group())

            missing = [f for f in required_str if not str(result.get(f, "")).strip()]
            if missing:
                raise ValueError(f"필수 필드 누락: {missing}")

            result["property_tags"] = _coerce_list(
                result.get("property_tags", []), VALID_PROPERTY_TAGS
            )
            result["tones"] = _coerce_list(
                result.get("tones", []), VALID_TONES
            )
            return result

        except Exception as e:
            wait = 5 * (2 ** attempt)
            print(f"  [재시도 {attempt + 1}/{MAX_RETRIES}] {e} → {wait}초 대기")
            time.sleep(wait)
    return None


# ── enriched_text 재구성 ──────────────────────────────────────────

def _tones_to_text(tones_csv: str) -> str:
    """pos_tones 쉼표 문자열 → 한국어 키워드 문자열."""
    tones = [t.strip() for t in str(tones_csv).split(",") if t.strip() and t.strip() != "nan"]
    return ", ".join(TONE_MAP[t] for t in tones if t in TONE_MAP)


def rebuild_enriched_text(row: pd.Series) -> str:
    """enriched_text 구성:
    장르 → 추천설명(4pillar) → 줄거리 → 분위기(pos_tones) → 시청상황 → 리뷰(pos 요약)
    NEG 필드는 임베딩 신호 희석 방지를 위해 제외.
    """
    parts = []
    for label, col in [
        ("장르",     "tmdb_genres"),
        ("추천설명", "llm_4pillar"),
        ("줄거리",   "tmdb_overview"),
    ]:
        val = str(row.get(col) or "").strip()
        if val and val != "nan":
            parts.append(f"{label}: {val}")

    tone_text = _tones_to_text(row.get("pos_tones", ""))
    if tone_text:
        parts.append(f"분위기: {tone_text}")

    for label, col in [
        ("시청상황", "viewing_context"),
        ("리뷰",    "focused_summary_pos"),
    ]:
        val = str(row.get(col) or "").strip()
        if val and val != "nan":
            parts.append(f"{label}: {val}")

    return " ".join(parts)


# ── 메인 ─────────────────────────────────────────────────────────

def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[오류] .env에 GOOGLE_API_KEY가 없습니다.")
        return

    client = genai.Client(api_key=api_key)

    # ── 리뷰 로드 ─────────────────────────────────────────────────
    print("review_db.csv 로드 중...")
    review_df = pd.read_csv(
        REVIEW_DB, dtype=str, engine="python", on_bad_lines="skip"
    ).fillna("")
    review_df["rank"] = pd.to_numeric(
        review_df["rank"], errors="coerce"
    ).fillna(99).astype(int)

    grouped: dict[str, dict] = {}
    for tmdb_id, grp in review_df.groupby("tmdb_id"):
        pos = (
            grp[grp["sentiment"] == "positive"]
            .sort_values("rank").head(TOP_N)["clean_text"].tolist()
        )
        neg = (
            grp[grp["sentiment"] == "negative"]
            .sort_values("rank").head(TOP_N)["clean_text"].tolist()
        )
        grouped[str(tmdb_id)] = {
            "positive": [t for t in pos if t.strip()],
            "negative": [t for t in neg if t.strip()],
        }

    # ── 대상 영화 목록 ────────────────────────────────────────────
    enriched_df = pd.read_csv(
        ENRICHED_CSV, engine="python", on_bad_lines="skip"
    ).fillna("")
    enriched_df["tmdb_id"] = pd.to_numeric(
        enriched_df["tmdb_id"], errors="coerce"
    )
    enriched_df = enriched_df[enriched_df["tmdb_id"].notna()]
    enriched_df["tmdb_id"] = enriched_df["tmdb_id"].astype(int)

    cache = load_cache()
    todo = [
        row for _, row in enriched_df.iterrows()
        if not is_complete(cache.get(str(int(row["tmdb_id"])), {}))
    ]
    complete_count = len(enriched_df) - len(todo)
    print(f"전체: {len(enriched_df)}편  |  완료: {complete_count}편  |  남은 작업: {len(todo)}편\n")

    # ── Gemini 호출 ───────────────────────────────────────────────
    def fmt(lst: list[str]) -> str:
        return "\n".join(f"{i+1}. {t}" for i, t in enumerate(lst)) or "없음"

    if not todo:
        print("모든 영화 처리 완료. CSV 업데이트로 진행합니다.")
    else:
        for i, row in enumerate(tqdm(todo, desc="요약 생성"), 1):
            tmdb_id  = str(int(row["tmdb_id"]))
            title    = row.get("movie_title", tmdb_id)
            reviews  = grouped.get(tmdb_id, {"positive": [], "negative": []})
            genres   = str(row.get("tmdb_genres", "") or "").strip() or "정보 없음"
            overview = str(row.get("tmdb_overview", "") or "").strip() or "정보 없음"

            entry = dict(cache.get(tmdb_id, {}))

            # POS
            if not _is_pos_complete(entry):
                if reviews["positive"]:
                    prompt = POS_PROMPT.format(
                        title_ko=title, genres=genres, overview=overview,
                        positive_reviews=fmt(reviews["positive"]),
                    )
                    result = call_gemini(client, prompt, "pos")
                    entry["pos"] = result if result else _empty_pos()
                    if not result:
                        print(f"  [POS 실패] [{tmdb_id}] {title}")
                else:
                    entry["pos"] = _empty_pos()
                time.sleep(REQUEST_DELAY)

            # NEG
            if not _is_neg_complete(entry):
                if reviews["negative"]:
                    prompt = NEG_PROMPT.format(
                        title_ko=title, genres=genres, overview=overview,
                        negative_reviews=fmt(reviews["negative"]),
                    )
                    result = call_gemini(client, prompt, "neg")
                    entry["neg"] = result if result else _empty_neg()
                    if not result:
                        print(f"  [NEG 실패] [{tmdb_id}] {title}")
                else:
                    entry["neg"] = _empty_neg()
                time.sleep(REQUEST_DELAY)

            cache[tmdb_id] = entry

            if i % SAVE_EVERY == 0:
                save_cache(cache)

        save_cache(cache)
        print(f"\n생성 완료: {len(cache)}편")

    # ── movie_enriched.csv 업데이트 ───────────────────────────────
    print("\nmovie_enriched.csv 업데이트 중...")

    def _list_to_str(val) -> str:
        if isinstance(val, list):
            return ",".join(val)
        return str(val) if val else ""

    def _get(tid: int, side: str, key: str) -> str:
        return cache.get(str(tid), {}).get(side, {}).get(key, "")

    enriched_df["pos_property_tags"]  = enriched_df["tmdb_id"].apply(
        lambda t: _list_to_str(_get(t, "pos", "property_tags"))
    )
    enriched_df["pos_tones"]          = enriched_df["tmdb_id"].apply(
        lambda t: _list_to_str(_get(t, "pos", "tones"))
    )
    enriched_df["viewing_context"]    = enriched_df["tmdb_id"].apply(
        lambda t: str(_get(t, "pos", "viewing_context")).strip()
    )
    enriched_df["focused_summary_pos"] = enriched_df["tmdb_id"].apply(
        lambda t: str(_get(t, "pos", "focused_summary")).strip()
    )
    enriched_df["neg_property_tags"]  = enriched_df["tmdb_id"].apply(
        lambda t: _list_to_str(_get(t, "neg", "property_tags"))
    )
    enriched_df["neg_tones"]          = enriched_df["tmdb_id"].apply(
        lambda t: _list_to_str(_get(t, "neg", "tones"))
    )
    enriched_df["focused_summary_neg"] = enriched_df["tmdb_id"].apply(
        lambda t: str(_get(t, "neg", "focused_summary")).strip()
    )
    enriched_df["enriched_text"] = enriched_df.apply(rebuild_enriched_text, axis=1)

    enriched_df.to_csv(ENRICHED_CSV, index=False, encoding="utf-8-sig")

    filled  = (enriched_df["focused_summary_pos"] != "").sum()
    missing = (enriched_df["focused_summary_pos"] == "").sum()
    print(f"focused_summary_pos 완료: {filled}편  |  빈값: {missing}편")
    print(f"\n저장 완료: {ENRICHED_CSV}")
    print(f"다음 단계 → python rag_pipeline/01_chunk.py")


if __name__ == "__main__":
    main()
