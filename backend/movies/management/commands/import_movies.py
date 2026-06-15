import random
import pandas as pd
from django.core.management.base import BaseCommand
from movies.models import Movie

TONES = ["amber", "rose", "plum", "indigo", "teal", "forest", "slate"]


def _int(val):
    try:
        v = int(float(str(val).replace(",", "")))
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def _float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _str(val):
    if pd.isna(val):
        return ""
    return str(val).strip()


class Command(BaseCommand):
    help = "movie_db.csv를 Movie 테이블에 임포트 (tmdb_id 기준 upsert)"

    def add_arguments(self, parser):
        parser.add_argument("--csv", default="../data/movie_db.csv")
        parser.add_argument("--clear", action="store_true", help="임포트 전 기존 데이터 전체 삭제")

    def handle(self, *args, **options):
        if options["clear"]:
            count = Movie.objects.count()
            Movie.objects.all().delete()
            self.stdout.write(f"기존 데이터 {count}건 삭제")

        df = pd.read_csv(options["csv"], dtype=str, on_bad_lines="skip")
        self.stdout.write(f"CSV 로드: {len(df)}편")

        created = updated = skipped = 0

        for _, row in df.iterrows():
            tmdb_id = _int(row.get("tmdb_id"))
            if not tmdb_id:
                skipped += 1
                continue

            # 기존 레코드에서 서비스 레이어 필드 보존
            existing = Movie.objects.filter(tmdb_id=tmdb_id).first()
            tone             = existing.tone             if existing and existing.tone             != "slate" else random.choice(TONES)
            combined_reviews = existing.combined_reviews if existing else ""
            llm_4pillar      = existing.llm_4pillar      if existing else ""
            poster_path      = existing.poster_path      if existing else ""

            _, is_new = Movie.objects.update_or_create(
                tmdb_id=tmdb_id,
                defaults={
                    "title_ko":        _str(row.get("title_ko")),
                    "title_original":  _str(row.get("title_original")),
                    "year":            _int(row.get("year")),
                    "genres":          _str(row.get("genres")),
                    "director":        _str(row.get("director")),
                    "cast":            _str(row.get("cast")),
                    "runtime":         _int(row.get("runtime")),
                    "country":         _str(row.get("country")),
                    "language":        _str(row.get("language")),
                    "overview_ko":     _str(row.get("overview_ko")),
                    "tmdb_rating":     _float(row.get("tmdb_rating")),
                    "tmdb_votes":      _int(row.get("tmdb_votes")),
                    "tmdb_popularity": _float(row.get("tmdb_popularity")),
                    "audience_kr":     _int(row.get("audience_kr")),
                    "source_lists":    _str(row.get("source_lists")),
                    "list_count":      _int(row.get("list_count")) or 0,
                    "category":        _str(row.get("category")),
                    "is_major":        str(row.get("is_major", "")).strip().lower() == "true",
                    "ott":             _str(row.get("ott")),
                    "watcha_url":      _str(row.get("watcha_url")),
                    "tone":            tone,
                    "poster_path":     poster_path,
                    "combined_reviews": combined_reviews,
                    "llm_4pillar":     llm_4pillar,
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"완료 — 신규 {created}편 / 업데이트 {updated}편 / skip {skipped}편 "
            f"/ 합계 {Movie.objects.count()}편"
        ))
