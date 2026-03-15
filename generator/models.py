from django.db import models


class ArticleGeneration(models.Model):
    """Records of generated articles for history/review."""

    INPUT_TYPE_RSS = "rss"
    INPUT_TYPE_URLS = "urls"
    INPUT_TYPE_CHOICES = [
        (INPUT_TYPE_RSS, "RSS Feed"),
        (INPUT_TYPE_URLS, "URL List"),
    ]

    input_type = models.CharField(max_length=10, choices=INPUT_TYPE_CHOICES)
    input_source = models.TextField(help_text="RSS URL or newline-separated article URLs")
    source_article_count = models.PositiveIntegerField(default=0)
    generated_title = models.CharField(max_length=500, blank=True)
    generated_article = models.TextField(blank=True)
    jewelry_topic = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_input_type_display()} → {self.jewelry_topic or 'Untitled'} ({self.created_at:%Y-%m-%d %H:%M})"
