
from .models import NewsPost

def news_unread_count(request):
    # Always show a number. If not logged in, return 0.
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"news_unread_count": 0}

    unread = (
        NewsPost.objects
        .filter(is_published=True)
        .exclude(reads__user=request.user)
        .count()
    )
    return {"news_unread_count": unread}
