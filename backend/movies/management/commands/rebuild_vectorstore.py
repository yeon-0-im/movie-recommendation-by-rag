"""
벡터스토어 전체 재구축 커맨드.

사용법:
  python manage.py rebuild_vectorstore           # 전체 재구축
  python manage.py rebuild_vectorstore --dry-run # 실제 저장 없이 건수만 확인
"""

from django.core.management.base import BaseCommand
from movies.models import Movie


class Command(BaseCommand):
    help = "Django DB의 Movie 데이터를 Chroma 벡터스토어에 전체 동기화"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 저장 없이 처리 가능한 건수만 출력",
        )

    def handle(self, *args, **options):
        from movies.rag import RAGSearch

        dry_run = options["dry_run"]
        movies = Movie.objects.all()
        total = movies.count()
        self.stdout.write(f"대상 영화: {total}편")

        if dry_run:
            skippable = movies.filter(llm_4pillar="", overview_ko="").count()
            self.stdout.write(f"  처리 가능: {total - skippable}편  (텍스트 없어 건너뜀: {skippable}편)")
            self.stdout.write("dry-run 완료 — 실제 저장은 하지 않았습니다.")
            return

        rag = RAGSearch.get_instance()
        ok = skipped = failed = 0

        for movie in movies.iterator():
            text = movie.llm_4pillar or movie.overview_ko or movie.title_ko
            if not text.strip():
                skipped += 1
                continue
            try:
                rag.upsert_movie(movie)
                ok += 1
                if ok % 100 == 0:
                    self.stdout.write(f"  {ok}/{total} 처리 중...")
            except Exception as e:
                failed += 1
                self.stderr.write(f"  실패 tmdb_id={movie.tmdb_id}: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"완료 — 저장: {ok}편  건너뜀: {skipped}편  실패: {failed}편"
            )
        )
