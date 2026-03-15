from django import forms


class ArticleInputForm(forms.Form):
    INPUT_TYPE_RSS = "rss"
    INPUT_TYPE_URLS = "urls"
    INPUT_TYPE_CHOICES = [
        (INPUT_TYPE_RSS, "RSS Feed URL"),
        (INPUT_TYPE_URLS, "Article URLs (one per line)"),
    ]

    input_type = forms.ChoiceField(
        choices=INPUT_TYPE_CHOICES,
        widget=forms.RadioSelect,
        initial=INPUT_TYPE_RSS,
        label="Input Type",
    )

    rss_url = forms.URLField(
        required=False,
        label="RSS Feed URL",
        widget=forms.URLInput(attrs={
            "placeholder": "https://example.com/feed.xml",
            "class": "form-control",
        }),
        help_text="Paste the URL of an RSS or Atom feed",
    )

    article_urls = forms.CharField(
        required=False,
        label="Article URLs",
        widget=forms.Textarea(attrs={
            "rows": 6,
            "placeholder": "https://example.com/article-1\nhttps://example.com/article-2",
            "class": "form-control",
        }),
        help_text="One URL per line (3–10 articles recommended)",
    )

    def clean(self):
        cleaned = super().clean()
        input_type = cleaned.get("input_type")

        if input_type == self.INPUT_TYPE_RSS:
            if not cleaned.get("rss_url"):
                self.add_error("rss_url", "Please provide an RSS feed URL.")
        elif input_type == self.INPUT_TYPE_URLS:
            raw = cleaned.get("article_urls", "").strip()
            if not raw:
                self.add_error("article_urls", "Please provide at least one article URL.")
            else:
                urls = []
                for line in raw.splitlines():
                    u = line.strip()
                    if not u:
                        continue
                    # Add scheme if missing
                    if not u.startswith(("http://", "https://")):
                        u = "https://" + u
                    urls.append(u)
                if len(urls) < 1:
                    self.add_error("article_urls", "Please provide at least one article URL.")
                cleaned["article_urls_list"] = urls

        return cleaned
