import random
from pathlib import Path
from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Movie
from .serializers import (
    MovieListSerializer, MovieDetailSerializer,
    SearchResponseSerializer, ChatConverseResponseSerializer,
    ChatPickResponseSerializer,
)


class MovieDetailView(APIView):
    """GET /api/movies/<id>/"""
    def get(self, request, pk):
        movie = get_object_or_404(Movie, pk=pk)
        return Response(MovieDetailSerializer(movie).data)


class MovieRandomView(APIView):
    """
    GET /api/movies/random/?exclude=1,2,3
    교체용 대안 영화 1편 랜덤 반환
    """
    def get(self, request):
        exclude_ids = []
        exclude_param = request.query_params.get("exclude", "")
        if exclude_param:
            exclude_ids = [int(x) for x in exclude_param.split(",") if x.strip().isdigit()]

        qs = Movie.objects.exclude(id__in=exclude_ids)
        count = qs.count()
        if not count:
            return Response({"detail": "추천할 영화가 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        movie = qs[random.randint(0, count - 1)]
        return Response(MovieListSerializer(movie).data)


class SearchView(APIView):
    """
    POST /api/search/
    body: {"query": "퇴근하고 지쳐서 아무 생각 없이 보기 좋은 영화"}
    """
    def post(self, request):
        query = request.data.get("query", "").strip()
        if not query:
            return Response({"detail": "query 필드가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)

        from .rag import RAGSearch
        rag = RAGSearch.get_instance()
        result = rag.search(query)

        titles = [h["title"] for h in result["hits"]]
        movies_by_title = {m.title_ko: m for m in Movie.objects.filter(title_ko__in=titles)}

        results = []
        for hit in result["hits"]:
            movie = movies_by_title.get(hit["title"])
            if movie:
                results.append({"movie": movie, "similarity": hit["similarity"]})

        return Response(SearchResponseSerializer({
            "query": query,
            "filters": result["parsed"].get("tmdb_filters", {}),
            "semantic_query": result["parsed"]["semantic_query"],
            "results": results,
        }).data)


class ChatConverseView(APIView):
    """
    POST /api/chat/converse/
    body: {
      "messages": [{"role": "user"|"assistant", "content": "..."}],
      "current_movie_titles": ["영화1", "영화2"],  # 현재 화면에 표시 중인 영화 제목
      "exclude_ids": [1, 2, 3]                    # 이미 본 영화 제외 (선택)
    }

    LangGraph가 의도를 분류하고 적절한 응답을 반환:
      search/refine  → type=result  + 영화 목록
      detail/when    → type=chat    + LLM 텍스트
      spoiler 등     → type=chat    + 고정 응답
    """
    def post(self, request):
        messages = request.data.get("messages", [])
        current_movie_titles = request.data.get("current_movie_titles", [])
        exclude_ids = request.data.get("exclude_ids", [])
        session_filters = request.data.get("session_filters", {})

        if not messages or not any(m.get("role") == "user" for m in messages):
            return Response({"detail": "messages 필드가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)

        from .rag import RAGSearch
        rag = RAGSearch.get_instance()
        result = rag.run_converse(messages, current_movie_titles, exclude_ids, session_filters)

        response_type = result["response_type"]

        updated_session = result.get("session_filters", {})

        # 텍스트 직접 응답 (detail/when_to_watch/spoiler/gratitude 등)
        if response_type == "text":
            return Response(ChatConverseResponseSerializer({
                "type": "chat",
                "ai_message": result["response_text"],
                "suggestions": [],
                "results": [],
                "session_filters": updated_session,
            }).data)

        # 검색 결과 (results / results_with_warning)
        hits = result["hits"]
        titles = [h["title"] for h in hits]
        movies_by_title = {
            m.title_ko: m
            for m in Movie.objects.filter(title_ko__in=titles).exclude(id__in=exclude_ids)
        }

        results = []
        seen_ids: set[int] = set()
        for hit in hits:
            movie = movies_by_title.get(hit["title"])
            if movie and movie.id not in seen_ids:
                seen_ids.add(movie.id)
                results.append({"movie": movie, "similarity": hit["similarity"], "pitch": ""})

        # 전체 결과 pitch 생성 (pool 교체 시에도 추천이유 표시)
        context = " / ".join(m["content"] for m in messages if m.get("role") == "user")
        pitches = rag.generate_pitches([r["movie"] for r in results], context)
        for i, pitch in enumerate(pitches):
            if i < len(results):
                results[i]["pitch"] = pitch

        if not results:
            return Response(ChatConverseResponseSerializer({
                "type": "chat",
                "ai_message": "조건에 맞는 영화를 찾지 못했어요. 조건을 조금 바꿔볼까요?",
                "suggestions": [],
                "results": [],
                "session_filters": updated_session,
            }).data)

        ai_message = result["response_text"] or "딱 맞는 영화를 찾았어요."

        return Response(ChatConverseResponseSerializer({
            "type": "result",
            "ai_message": ai_message,
            "suggestions": [],
            "results": results,
            "session_filters": updated_session,
        }).data)


class ChatFollowupView(APIView):
    """
    POST /api/chat/followup/
    body: {"query": "좀 더 슬픈 거", "exclude_ids": [1, 2, 3]}
    결과 화면 이후 자유 입력 — 시맨틱 검색 직행
    """
    def post(self, request):
        query = request.data.get("query", "").strip()
        exclude_ids = request.data.get("exclude_ids", [])

        if not query:
            return Response({"detail": "query 필드가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)

        from .rag import RAGSearch
        rag = RAGSearch.get_instance()
        hits = rag.semantic_search(query, k=10)

        titles = [h["title"] for h in hits]
        movies_by_title = {
            m.title_ko: m
            for m in Movie.objects.filter(title_ko__in=titles).exclude(id__in=exclude_ids)
        }

        results = []
        seen_ids: set[int] = set()
        for hit in hits:
            movie = movies_by_title.get(hit["title"])
            if movie and movie.id not in seen_ids:
                seen_ids.add(movie.id)
                results.append({"movie": movie, "similarity": hit["similarity"], "pitch": ""})

        pitches = rag.generate_pitches([r["movie"] for r in results], query)
        for i, pitch in enumerate(pitches):
            if i < len(results):
                results[i]["pitch"] = pitch

        return Response(ChatPickResponseSerializer({
            "ai_message": "찾아봤어요!",
            "results": results,
        }).data)


class MovieListView(APIView):
    """GET /api/movies/ — 관리/디버그용"""
    def get(self, request):
        q = request.query_params.get("q", "").strip()
        qs = Movie.objects.all()
        if q:
            qs = qs.filter(title__icontains=q)
        return Response(MovieListSerializer(qs[:50], many=True).data)


# ── Admin Dashboard APIs ─────────────────────────────────────

class AdminOverviewView(APIView):
    """GET /api/admin/overview/ — 전체 현황 KPI"""
    def get(self, request):
        movies_count = Movie.objects.count()
        return Response({
            "conversations": 1284,
            "completion_rate": 68.2,
            "swap_rate": 24.7,
            "response_time": 2.4,
            "total_movies": movies_count,
        })


class AdminMoviesView(APIView):
    """GET /api/admin/movies/ — 영화 풀 목록 및 성과"""
    def get(self, request):
        movies = Movie.objects.filter(is_major=True).order_by("-list_count")[:30]
        data = []
        for m in movies:
            data.append({
                "id": m.id,
                "title": m.title_ko,
                "title_en": m.title_original or "",
                "genre": m.genres or "미분류",
                "tone": m.tone or "slate",
                "context": m.context or "미지정",
                "load": m.load or "미지정",
                "recs": m.list_count,
                "seen_rate": 0,  # TODO: 사용자 피드백 모델 필요
                "reviews": 1 if m.combined_reviews else 0,
            })
        return Response({"movies": data})


class AdminConversationsView(APIView):
    """GET /api/admin/conversations/ — 대화 로그"""
    def get(self, request):
        # TODO: 실제 conversation 로그 저장 구조 필요
        return Response({
            "conversations": [
                {
                    "user": "user_3821",
                    "time": "09:42",
                    "msg": "퇴근하고 너무 지쳤는데 가볍게 위로받을 만한 영화 있을까",
                    "tags": [["퇴근길·번아웃", "accent"], ["완료", "up"]]
                }
            ]
        })


class AdminTaxonomyView(APIView):
    """GET /api/admin/taxonomy/ — 4-Pillar 분석"""
    def get(self, request):
        from django.db.models import Count

        # Context 분포
        context_data = list(
            Movie.objects.filter(context__gt="")
            .values("context")
            .annotate(value=Count("id"))
            .order_by("-value")
        )
        context = [{"name": d["context"], "value": d["value"]} for d in context_data]

        # Load 분포
        load_data = list(
            Movie.objects.filter(load__gt="")
            .values("load")
            .annotate(value=Count("id"))
            .order_by("-value")
        )
        load = [{"name": d["load"], "value": d["value"]} for d in load_data]

        # Fallback (데이터 없을 경우)
        if not context:
            context = [{"name": "미지정", "value": Movie.objects.count()}]
        if not load:
            load = [{"name": "미지정", "value": Movie.objects.count()}]

        return Response({
            "context": context,
            "load": load,
        })


class AdminPageView(APIView):
    """GET /admin/ — 관리자 대시보드 HTML"""
    def get(self, request):
        from django.http import HttpResponse
        project_root = Path(__file__).parent.parent.parent
        html_path = project_root / "ㅇㅎㅊㅊ" / "admin.html"

        try:
            with open(html_path, "r", encoding="utf-8") as f:
                return HttpResponse(f.read(), content_type="text/html; charset=utf-8")
        except FileNotFoundError:
            return HttpResponse(f"<h1>Admin page not found at {html_path}</h1>", status=404)
