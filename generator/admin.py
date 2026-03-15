from django.contrib import admin
from .models import ArticleGeneration


@admin.register(ArticleGeneration)
class ArticleGenerationAdmin(admin.ModelAdmin):
    list_display = ("id", "jewelry_topic", "input_type", "source_article_count", "created_at")
    list_filter = ("input_type", "created_at")
    search_fields = ("jewelry_topic", "generated_title", "input_source")
    readonly_fields = ("created_at",)
