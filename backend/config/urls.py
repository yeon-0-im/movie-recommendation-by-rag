from django.contrib import admin
from django.urls import path, include
from movies.views import AdminPageView

admin.site.site_header = "ㅇㅎㅊㅊ 관리자"
admin.site.site_title = "ㅇㅎㅊㅊ"
admin.site.index_title = "관리 페이지"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", AdminPageView.as_view()),
    path("api/", include("movies.urls")),
]
