import logging
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="movies.Movie")
def sync_movie_to_chroma(sender, instance, **kwargs):
    """Movie 저장 시 Chroma를 자동으로 최신 상태로 갱신."""
    try:
        from .rag import RAGSearch
        RAGSearch.get_instance().upsert_movie(instance)
    except Exception:
        logger.exception("Chroma upsert 실패 (tmdb_id=%s)", instance.tmdb_id)


@receiver(post_delete, sender="movies.Movie")
def remove_movie_from_chroma(sender, instance, **kwargs):
    """Movie 삭제 시 Chroma에서도 해당 벡터를 제거."""
    try:
        from .rag import RAGSearch
        RAGSearch.get_instance().delete_movie(instance.tmdb_id)
    except Exception:
        logger.exception("Chroma delete 실패 (tmdb_id=%s)", instance.tmdb_id)
