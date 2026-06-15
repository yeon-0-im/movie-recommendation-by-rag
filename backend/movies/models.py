from django.db import models


class Movie(models.Model):
    # 식별자
    tmdb_id = models.IntegerField(unique=True, verbose_name="TMDB ID")

    # 제목
    title_ko       = models.TextField(verbose_name="한국어 제목")
    title_original = models.TextField(blank=True, verbose_name="원어 제목")

    # 기본 메타
    year     = models.IntegerField(null=True, blank=True, verbose_name="개봉연도")
    genres   = models.CharField(max_length=200, blank=True, verbose_name="장르")
    director = models.TextField(blank=True, verbose_name="감독")
    cast     = models.TextField(blank=True, verbose_name="출연진")
    runtime  = models.IntegerField(null=True, blank=True, verbose_name="상영시간(분)")
    country  = models.CharField(max_length=200, blank=True, verbose_name="제작국")
    language = models.CharField(max_length=10, blank=True, verbose_name="언어")

    # 줄거리
    overview_ko = models.TextField(blank=True, verbose_name="한국어 줄거리")

    # TMDB 지표
    tmdb_rating     = models.FloatField(null=True, blank=True, verbose_name="TMDB 평점")
    tmdb_votes      = models.IntegerField(null=True, blank=True, verbose_name="TMDB 투표수")
    tmdb_popularity = models.FloatField(null=True, blank=True, verbose_name="TMDB 인기도")
    audience_kr     = models.IntegerField(null=True, blank=True, verbose_name="국내 누적 관객수")

    # 수집 메타
    source_lists = models.TextField(blank=True, verbose_name="출처 리스트")
    list_count   = models.IntegerField(default=0, verbose_name="등장 리스트 수")
    category     = models.CharField(max_length=100, blank=True, verbose_name="수집 카테고리")
    is_major     = models.BooleanField(default=True, verbose_name="메이저 여부")
    watcha_url   = models.URLField(blank=True, verbose_name="왓챠피디아 URL")
    collected_at = models.DateTimeField(null=True, blank=True, verbose_name="수집 일시")

    # 서비스 레이어
    poster_path      = models.CharField(max_length=200, blank=True, verbose_name="포스터 경로")
    tone             = models.CharField(max_length=20, default="slate", verbose_name="포스터 톤")
    combined_reviews = models.TextField(blank=True, verbose_name="수집 리뷰")
    llm_4pillar      = models.TextField(blank=True, verbose_name="4-Pillar 설명")
    ott              = models.CharField(max_length=200, blank=True, verbose_name="OTT")

    # 4-Pillar
    # context, sensory는 쉼표 구분 다중값 가능 (예: "퇴근길·번아웃,머리 비우고 싶을 때")
    CONTEXT_CHOICES = [
        ("퇴근길·번아웃",         "퇴근길·번아웃"),
        ("이별 직후",             "이별 직후"),
        ("이별 후 회복기",         "이별 후 회복기"),
        ("머리 비우고 싶을 때",    "머리 비우고 싶을 때"),
        ("답답함을 뚫고 싶을 때",  "답답함을 뚫고 싶을 때"),
        ("동기부여가 필요할 때",   "동기부여가 필요할 때"),
        ("강렬함이 필요할 때",     "강렬함이 필요할 때"),
        ("가볍게 웃고 싶을 때",    "가볍게 웃고 싶을 때"),
        ("주말 여유",              "주말 여유"),
        ("혼자 집에서",            "혼자 집에서"),
    ]
    SENSORY_CHOICES = [
        ("압도적 미장센",   "압도적 미장센"),
        ("스타일리시 액션", "스타일리시 액션"),
        ("감각적인 색감",   "감각적인 색감"),
        ("따뜻한 색감",     "따뜻한 색감"),
        ("사운드트랙 맛집", "사운드트랙 맛집"),
        ("타란티노 스타일", "타란티노 스타일"),
        ("몽환적 분위기",   "몽환적 분위기"),
    ]
    LOAD_CHOICES = [
        ("Low-Load",   "Low-Load"),
        ("Fast-paced", "Fast-paced"),
        ("High-Load",  "High-Load"),
    ]

    context = models.CharField(
        max_length=200, blank=True, default="",
        verbose_name="추천 컨텍스트 (쉼표 구분 다중값)"
    )
    sensory = models.CharField(
        max_length=200, blank=True, default="",
        verbose_name="감각 태그 (쉼표 구분 다중값)"
    )
    load = models.CharField(
        max_length=20, blank=True, default="",
        choices=[("", "미지정")] + LOAD_CHOICES,
        verbose_name="인지부하"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "영화"
        verbose_name_plural = "영화 목록"
        ordering = ["title_ko"]

    def __str__(self):
        return f"{self.title_ko} ({self.year})" if self.year else self.title_ko
