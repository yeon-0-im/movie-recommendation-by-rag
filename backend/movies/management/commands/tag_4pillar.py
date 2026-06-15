"""
4-Pillar 자동 태깅 파이프라인.

흐름:
  combined_reviews
    → Gemini (strictly context-bound 추출)
    → context / sensory / load 태그
    → Movie 모델 저장 → signal → ChromaDB 메타데이터 동기화

사용법:
  python manage.py tag_4pillar                  # 태그 없는 영화만 처리
  python manage.py tag_4pillar --all            # 전체 재처리
  python manage.py tag_4pillar --limit 50       # 최대 N편만
  python manage.py tag_4pillar --dry-run        # 실제 저장 없이 출력만
"""

import json
import time
import re
from django.core.management.base import BaseCommand
from movies.models import Movie
from django.conf import settings


TAG_PROMPT = """\
아래는 영화 "{title}"의 사용자 리뷰 모음입니다.
리뷰에 **명시적으로 언급된 내용에만** 근거해 태그를 추출하세요.
리뷰에 없는 내용을 추론하거나 영화 장르·일반 상식으로 판단하지 마세요.

[유효 태그 목록 — 이 목록 밖의 값은 절대 출력 금지]

context (시청 상황):
  퇴근길·번아웃 | 이별 직후 | 이별 후 회복기 | 머리 비우고 싶을 때
  답답함을 뚫고 싶을 때 | 동기부여가 필요할 때 | 강렬함이 필요할 때
  가볍게 웃고 싶을 때 | 주말 여유 | 혼자 집에서

sensory (감각적 특징):
  압도적 미장센 | 스타일리시 액션 | 감각적인 색감 | 따뜻한 색감
  사운드트랙 맛집 | 타란티노 스타일 | 몽환적 분위기

load (인지부하):
  Low-Load | Fast-paced | High-Load

[추출 규칙]
1. 리뷰에 "치맥이랑 딱" → context: ["머리 비우고 싶을 때", "가볍게 웃고 싶을 때"]
2. 리뷰에 "영상미가 압도적" → sensory: ["압도적 미장센"]
3. 리뷰에 "긴장해서 생각 못 함" → load: "Fast-paced"
4. 리뷰에 언급 없으면 빈 배열 또는 ""
5. context는 최대 3개, sensory는 최대 2개

[리뷰]
{reviews}

[출력] JSON만 출력하세요. 설명 금지.
{{"context": [], "sensory": [], "load": ""}}
"""

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


def _parse_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _extract_tags(client, model: str, movie: Movie, chroma_doc: str = "") -> dict | None:
    # 우선순위: combined_reviews → llm_4pillar → ChromaDB document
    reviews = (movie.combined_reviews or movie.llm_4pillar or chroma_doc or "").strip()
    if not reviews:
        return None

    prompt = TAG_PROMPT.format(
        title=movie.title_ko,
        reviews=reviews[:2000],  # 토큰 제한: 최대 2000자
    )

    try:
        resp = client.models.generate_content(model=model, contents=prompt)
        raw = _parse_json(resp.text)
    except Exception as e:
        raise RuntimeError(f"Gemini 호출 실패: {e}") from e

    # 유효값 검증 (closed vocabulary 강제)
    context = [t for t in raw.get("context", []) if t in VALID_CONTEXTS][:3]
    sensory = [t for t in raw.get("sensory", []) if t in VALID_SENSORY][:2]
    load    = raw.get("load", "") if raw.get("load") in VALID_LOADS else ""

    return {
        "context": ",".join(context),
        "sensory": ",".join(sensory),
        "load":    load,
    }


class Command(BaseCommand):
    help = "리뷰 기반 4-Pillar 태그 자동 추출 (Gemini)"

    def add_arguments(self, parser):
        parser.add_argument("--all",      action="store_true", help="기존 태그 포함 전체 재처리")
        parser.add_argument("--limit",    type=int, default=0,  help="최대 처리 편수 (0=제한 없음)")
        parser.add_argument("--dry-run",  action="store_true",  help="저장 없이 출력만")
        parser.add_argument("--delay",    type=float, default=3.0, help="API 호출 간격(초), 기본 3.0")

    def handle(self, *args, **options):
        from google import genai
        from movies.rag import RAGSearch
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        model  = settings.RAG_GEMINI_MODEL

        # ChromaDB에서 tmdb_id → document 맵 미리 로드
        self.stdout.write("ChromaDB 문서 로딩 중...")
        rag = RAGSearch.get_instance()
        chroma_result = rag.vectorstore._collection.get(include=["documents", "metadatas"])
        chroma_docs = {
            int(meta["tmdb_id"]): doc
            for meta, doc in zip(chroma_result["metadatas"], chroma_result["documents"])
            if meta.get("tmdb_id")
        }
        self.stdout.write(f"ChromaDB 문서: {len(chroma_docs)}편 로드됨")

        qs = Movie.objects.all()
        if not options["all"]:
            qs = qs.filter(context="", sensory="", load="")
        if options["limit"]:
            qs = qs[:options["limit"]]

        total = qs.count()
        self.stdout.write(f"대상: {total}편  dry-run={options['dry_run']}")

        ok = skipped = failed = 0

        for movie in qs.iterator():
            chroma_doc = chroma_docs.get(movie.tmdb_id, "")
            try:
                tags = _extract_tags(client, model, movie, chroma_doc)
            except RuntimeError as e:
                self.stderr.write(f"  ✗ {movie.title_ko}: {e}")
                failed += 1
                time.sleep(options["delay"] * 2)
                continue

            if tags is None:
                skipped += 1
                continue

            self.stdout.write(
                f"  {movie.title_ko} | ctx={tags['context'] or '-'} "
                f"| sensory={tags['sensory'] or '-'} | load={tags['load'] or '-'}"
            )

            if not options["dry_run"]:
                Movie.objects.filter(pk=movie.pk).update(
                    context=tags["context"],
                    sensory=tags["sensory"],
                    load=tags["load"],
                )
                # update()는 signal 안 발생 → 직접 ChromaDB 동기화
                movie.context = tags["context"]
                movie.sensory = tags["sensory"]
                movie.load    = tags["load"]
                try:
                    rag.upsert_movie(movie)
                except Exception as e:
                    self.stderr.write(f"    ChromaDB 동기화 실패: {e}")

            ok += 1
            time.sleep(options["delay"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\n완료 — 태깅: {ok}편  리뷰 없음: {skipped}편  실패: {failed}편"
            )
        )
