from rest_framework import serializers
from .models import Movie


class MovieListSerializer(serializers.ModelSerializer):
    """목록/카드용 — 프론트엔드가 기대하는 필드명으로 매핑"""
    title    = serializers.CharField(source="title_ko")
    title_en = serializers.CharField(source="title_original")

    class Meta:
        model = Movie
        fields = [
            "id", "title", "title_en", "year",
            "genres", "director", "cast", "runtime",
            "language", "country", "ott", "tone",
            "llm_4pillar", "poster_path",
        ]


class MovieDetailSerializer(serializers.ModelSerializer):
    """상세 화면용 — 전체 필드"""
    title    = serializers.CharField(source="title_ko")
    title_en = serializers.CharField(source="title_original")
    overview = serializers.CharField(source="overview_ko")

    class Meta:
        model = Movie
        fields = [
            "id", "title", "title_en", "year",
            "tmdb_id", "genres", "director", "cast",
            "runtime", "language", "country", "ott",
            "overview", "combined_reviews", "llm_4pillar",
            "tone", "poster_path",
        ]


class SearchResultSerializer(serializers.Serializer):
    """RAG 검색 결과 한 항목"""
    movie = MovieListSerializer()
    similarity = serializers.FloatField(allow_null=True)
    pitch = serializers.CharField(allow_null=True, required=False, default="")


class SearchResponseSerializer(serializers.Serializer):
    """POST /api/search/ 응답 전체"""
    query = serializers.CharField()
    filters = serializers.DictField()
    semantic_query = serializers.CharField()
    results = SearchResultSerializer(many=True)


class ChatOptionSerializer(serializers.Serializer):
    """채팅 튜닝 선택지"""
    label = serializers.CharField()
    index = serializers.IntegerField()


class ChatStartResponseSerializer(serializers.Serializer):
    """POST /api/chat/start/ 응답"""
    ai_question = serializers.CharField()
    options = ChatOptionSerializer(many=True)


class ChatSecondResponseSerializer(serializers.Serializer):
    """POST /api/chat/pick/ 응답 (2차 질문)"""
    ai_question = serializers.CharField()
    options = ChatOptionSerializer(many=True)


class ChatPickResponseSerializer(serializers.Serializer):
    """POST /api/chat/followup/ 응답"""
    ai_message = serializers.CharField()
    results = SearchResultSerializer(many=True)


class ChatConverseResponseSerializer(serializers.Serializer):
    """POST /api/chat/converse/ 응답"""
    type = serializers.CharField()             # "question" | "result" | "chat"
    ai_message = serializers.CharField()
    suggestions = serializers.ListField(child=serializers.CharField(), default=list)
    results = SearchResultSerializer(many=True, default=list)
    session_filters = serializers.DictField(default=dict)  # 누적 필터 — 클라이언트가 다음 턴에 전달
