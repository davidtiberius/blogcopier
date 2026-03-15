import json
import logging
from django.conf import settings
from django.http import StreamingHttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from .forms import ArticleInputForm
from .models import ArticleGeneration
from .services.rss_parser import parse_rss_feed
from .services.article_scraper import scrape_articles
from .services.ai_generator import stream_generated_article, pick_topic_and_style

logger = logging.getLogger(__name__)


def index(request):
    form = ArticleInputForm()
    return render(request, "generator/index.html", {"form": form})


@require_http_methods(["POST"])
def generate(request):
    form = ArticleInputForm(request.POST)
    if not form.is_valid():
        return render(request, "generator/index.html", {"form": form})

    input_type = form.cleaned_data["input_type"]

    if input_type == ArticleInputForm.INPUT_TYPE_RSS:
        rss_url = form.cleaned_data["rss_url"]
        try:
            article_urls = parse_rss_feed(rss_url)
        except Exception as exc:
            form.add_error("rss_url", f"Could not parse RSS feed: {exc}")
            return render(request, "generator/index.html", {"form": form})
        input_source = rss_url
    else:
        article_urls = form.cleaned_data["article_urls_list"]
        input_source = "\n".join(article_urls)

    if not article_urls:
        form.add_error(None, "No article URLs found. Please check your input.")
        return render(request, "generator/index.html", {"form": form})

    article_urls = article_urls[:10]

    try:
        articles = scrape_articles(article_urls)
    except Exception as exc:
        logger.exception("Scraping failed")
        form.add_error(None, f"Failed to scrape articles: {exc}")
        return render(request, "generator/index.html", {"form": form})

    if not articles:
        form.add_error(None, "Could not extract content from any of the provided URLs.")
        return render(request, "generator/index.html", {"form": form})

    logger.info("Starting topic selection with %d scraped articles (titles: %s)",
                len(articles), [a.get("title", "?") for a in articles])
    try:
        topic_info = pick_topic_and_style(articles, settings.ANTHROPIC_API_KEY)
        logger.info("Topic selection succeeded: topic=%r, keys=%s",
                     topic_info.get("topic"), list(topic_info.keys()))
    except Exception as exc:
        logger.exception("Topic selection failed")
        form.add_error(None, f"AI error during topic selection: {exc}")
        return render(request, "generator/index.html", {"form": form})

    generation = ArticleGeneration.objects.create(
        input_type=input_type,
        input_source=input_source,
        source_article_count=len(articles),
        jewelry_topic=topic_info["topic"],
    )

    request.session[f"gen_{generation.id}"] = {
        "articles": articles,
        "topic_info": topic_info,
    }

    return redirect("generator:result", generation_id=generation.id)


def result(request, generation_id):
    generation = get_object_or_404(ArticleGeneration, id=generation_id)
    return render(request, "generator/result.html", {"generation": generation})


def stream_article(request, generation_id):
    """Server-Sent Events endpoint that streams the generated article."""
    generation = get_object_or_404(ArticleGeneration, id=generation_id)

    session_key = f"gen_{generation_id}"
    session_data = request.session.get(session_key)

    if not session_data:
        def already_done():
            yield f"data: {json.dumps({'text': generation.generated_article})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingHttpResponse(already_done(), content_type="text/event-stream")

    articles = session_data["articles"]
    topic_info = session_data["topic_info"]

    def event_stream():
        full_text = []
        try:
            for chunk in stream_generated_article(articles, topic_info, settings.ANTHROPIC_API_KEY):
                full_text.append(chunk)
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as exc:
            logger.exception("Streaming generation failed")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            return

        complete_article = "".join(full_text)
        generation.generated_article = complete_article

        lines = complete_article.strip().splitlines()
        if lines:
            first = lines[0].lstrip("#").strip()
            if len(first) < 200:
                generation.generated_title = first
        generation.save()

        del request.session[session_key]
        request.session.modified = True

        yield "data: [DONE]\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def history(request):
    generations = ArticleGeneration.objects.all()[:50]
    return render(request, "generator/history.html", {"generations": generations})
