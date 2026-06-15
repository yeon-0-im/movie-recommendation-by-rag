from django.urls import path
from . import views

urlpatterns = [
    path("search/", views.SearchView.as_view(), name="search"),
    path("chat/converse/", views.ChatConverseView.as_view(), name="chat-converse"),
    path("chat/followup/", views.ChatFollowupView.as_view(), name="chat-followup"),
    path("movies/", views.MovieListView.as_view(), name="movie-list"),
    path("movies/random/", views.MovieRandomView.as_view(), name="movie-random"),
    path("movies/<int:pk>/", views.MovieDetailView.as_view(), name="movie-detail"),
    # Admin APIs
    path("admin/overview/", views.AdminOverviewView.as_view(), name="admin-overview"),
    path("admin/movies/", views.AdminMoviesView.as_view(), name="admin-movies"),
    path("admin/conversations/", views.AdminConversationsView.as_view(), name="admin-conversations"),
    path("admin/taxonomy/", views.AdminTaxonomyView.as_view(), name="admin-taxonomy"),
]
