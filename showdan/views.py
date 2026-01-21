from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q, Min, Max

from accounts.models import Profession, Language

User = get_user_model()


def _build_profession_tree_options():
    """
    Returns a list of tuples: (id, label_with_indent)
    where children are indented under their parents.
    """
    all_items = list(Profession.objects.select_related("parent").all())

    children_map = {}
    roots = []

    for p in all_items:
        pid = p.parent_id
        if pid is None:
            roots.append(p)
        children_map.setdefault(pid, []).append(p)

    # sort siblings by name (keeps descendants under their parent)
    for pid, items in children_map.items():
        items.sort(key=lambda x: (x.name or "").lower())

    roots.sort(key=lambda x: (x.name or "").lower())

    out = []

    def walk(node, depth):
        # indent using spaces (works inside <option>)
        indent = "\u00A0" * (depth * 4)  # 4 non-breaking spaces per level
        label = f"{indent}{node.name}"
        out.append((node.id, label))

        for ch in children_map.get(node.id, []):
            walk(ch, depth + 1)

    for r in roots:
        walk(r, 0)

    return out


def home_view(request):
    qs = (
        User.objects
        .filter(account_type="professional", is_active=True)
        .prefetch_related("professions", "communication_languages")
        .select_related("currency")
    )

    # ----------------------------
    # GET params
    # ----------------------------
    q = (request.GET.get("q") or "").strip()
    profession_id = (request.GET.get("profession") or "").strip()
    min_price = request.GET.get("min_price") or ""
    max_price = request.GET.get("max_price") or ""
    lang_ids = request.GET.getlist("lang")  # multiple
    gender = request.GET.get("gender") or ""  # optional

    # Search (name, nickname, location, professions)
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(nickname__icontains=q) |
            Q(city__icontains=q) |
            Q(country__icontains=q) |
            Q(professions__name__icontains=q)
        )

    # ✅ Profession only
    if profession_id.isdigit():
        qs = qs.filter(professions__id=int(profession_id))

    # Price range
    if min_price:
        try:
            qs = qs.filter(cost_per_hour__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            qs = qs.filter(cost_per_hour__lte=float(max_price))
        except ValueError:
            pass

    # Languages (communication_languages)
    lang_ids_int = [int(x) for x in lang_ids if x.isdigit()]
    if lang_ids_int:
        qs = qs.filter(communication_languages__id__in=lang_ids_int)

    # Gender (only if field exists)
    if gender and hasattr(User, "gender"):
        qs = qs.filter(gender=gender)

    qs = qs.distinct()

    pros = (
        qs.annotate(avg_rating=Avg("reviews_received__rating"))
          .annotate(review_count=Count("reviews_received"))
          .order_by("-id")
    )

    # Options for UI
    profession_options = _build_profession_tree_options()
    languages = Language.objects.all().order_by("name")

    # Slider bounds
    bounds = qs.aggregate(pmin=Min("cost_per_hour"), pmax=Max("cost_per_hour"))
    pmin = bounds["pmin"] or 0
    pmax = bounds["pmax"] or 600

    return render(request, "home.html", {
        "pros": pros,

        "profession_options": profession_options,
        "languages": languages,

        "f_q": q,
        "f_profession": profession_id,
        "f_min_price": min_price,
        "f_max_price": max_price,
        "f_lang_ids": lang_ids_int,
        "f_gender": gender,

        "pmin": int(pmin) if pmin is not None else 0,
        "pmax": int(pmax) if pmax is not None else 600,
    })
