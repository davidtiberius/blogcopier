from django.urls import path
from . import views

app_name = "generator"

urlpatterns = [
    path("", views.index, name="index"),
    path("generate/", views.generate, name="generate"),
    path("stream/<int:generation_id>/", views.stream_article, name="stream"),
    path("history/", views.history, name="history"),
    path("result/<int:generation_id>/", views.result, name="result"),
]
