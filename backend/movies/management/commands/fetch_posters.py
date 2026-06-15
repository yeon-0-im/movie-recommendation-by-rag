"""
TMDB API에서 poster_path를 일괄 수집해 DB에 저장.

실행: python manage.py fetch_posters
      python manage.py fetch_posters --force   # 이미 있는 것도 덮어쓰기
"""

import time
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from movies.models import Movie


TMDB_IMG_BASE = "https://api.themoviedb.org/3/movie"


class Command(BaseCommand):
    help = "TMDB API에서 poster_path를 일괄 수집해 DB에 저장"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="이미 poster_path가 있는 영화도 덮어쓰기"
        )
        parser.add_argument(
            "--batch", type=int, default=40,
            help="초당 요청 수 (기본 40, TMDB 무료 티어 한도)"
        )

    def handle(self, *args, **options):
        api_key = settings.TMDB_API_KEY if hasattr(settings, "TMDB_API_KEY") else ""
        if not api_key:
            import os
            api_key = os.getenv("TMDB_API_KEY", "")
        if not api_key:
            self.stderr.write("TMDB_API_KEY 환경변수가 설정되지 않았습니다.")
            return

        force = options["force"]
        batch_size = options["batch"]

        qs = Movie.objects.all() if force else Movie.objects.filter(poster_path="")
        total = qs.count()
        self.stdout.write(f"poster_path 수집 대상: {total:,}편")

        updated = 0
        failed = 0
        session = requests.Session()

        for i, movie in enumerate(qs.iterator(), 1):
            try:
                url = f"{TMDB_IMG_BASE}/{movie.tmdb_id}"
                resp = session.get(url, params={"api_key": api_key, "language": "ko-KR"}, timeout=5)
                resp.raise_for_status()
                data = resp.json()
                poster = data.get("poster_path", "")
                if poster:
                    movie.poster_path = poster
                    movie.save(update_fields=["poster_path"])
                    updated += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                if i <= 5:
                    self.stderr.write(f"  [{movie.title_ko}] 실패: {e}")

            if i % batch_size == 0:
                self.stdout.write(f"  {i:,}/{total:,} 처리 ({updated:,} 저장, {failed} 실패)")
                time.sleep(1)  # rate limit

        self.stdout.write(self.style.SUCCESS(
            f"\n완료: {updated:,}편 저장, {failed}편 실패 (전체 {total:,}편)"
        ))
