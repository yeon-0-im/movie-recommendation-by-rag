from django.contrib import admin
from .models import Movie


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display   = ("title_ko", "year", "genres", "language", "director", "runtime", "ott")
    list_filter    = ("language", "is_major", "category")
    search_fields  = ("title_ko", "title_original", "director", "cast")
    readonly_fields = ("created_at", "updated_at")
    ordering       = ("title_ko",)

    fieldsets = (
        ("기본 정보", {
            "fields": ("title_ko", "title_original", "year", "tmdb_id", "tone", "poster_path")
        }),
        ("TMDB 메타데이터", {
            "fields": ("genres", "director", "cast", "runtime", "language", "country", "overview_ko",
                       "tmdb_rating", "tmdb_votes", "tmdb_popularity")
        }),
        ("수집 메타", {
            "fields": ("audience_kr", "source_lists", "list_count", "category", "is_major",
                       "ott", "watcha_url", "collected_at"),
            "classes": ("collapse",),
        }),
        ("RAG 데이터", {
            "fields": ("combined_reviews", "llm_4pillar"),
            "classes": ("collapse",),
        }),
        ("4-Pillar", {
            "fields": ("context", "sensory", "load"),
            "description": "쉼표로 구분해 다중 태그 입력 가능. 예: 퇴근길·번아웃,머리 비우고 싶을 때",
        }),
        ("시스템", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
