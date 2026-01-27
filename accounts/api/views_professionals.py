# accounts/api/views_professionals.py
from rest_framework import views, status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.db.models import Q, Avg, Count, Min, Max
from django.shortcuts import get_object_or_404

from ..models import Profession, Language, Currency
from .serializers_professionals import *
from .serializers import PublicProfileSerializer

User = get_user_model()


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
        })


class ProfessionalsListView(generics.ListAPIView):
    """
    List professionals with filters

    GET /api/v1/professionals/

    Query Parameters:
    - q: Search query (name, nickname, location, professions)
    - profession: Profession ID filter
    - min_price: Minimum cost per hour
    - max_price: Maximum cost per hour
    - languages: List of language IDs (communication languages)
    - gender: 'male' or 'female'
    - order_by: 'rating', '-rating', 'price', '-price', 'experience', '-experience', 'name', '-name'
    - page: Page number
    - page_size: Items per page (1-100)

    Example: /api/v1/professionals/?q=music&profession=2&min_price=50&max_price=200&order_by=-rating
    """
    serializer_class = ProfessionalListSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPagination

    def get_queryset(self):
        queryset = User.objects.filter(
            account_type=User.AccountType.PROFESSIONAL,
            is_active=True
        ).prefetch_related('professions', 'communication_languages').select_related('currency')

        # Apply filters from query parameters
        params = self.request.query_params

        # Search query
        q = params.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(nickname__icontains=q) |
                Q(city__icontains=q) |
                Q(country__icontains=q) |
                Q(professions__name__icontains=q)
            )

        # Profession filter
        profession_id = params.get('profession')
        if profession_id and profession_id.isdigit():
            queryset = queryset.filter(professions__id=int(profession_id))

        # Price range filters
        min_price = params.get('min_price')
        if min_price:
            try:
                queryset = queryset.filter(cost_per_hour__gte=float(min_price))
            except (ValueError, TypeError):
                pass

        max_price = params.get('max_price')
        if max_price:
            try:
                queryset = queryset.filter(cost_per_hour__lte=float(max_price))
            except (ValueError, TypeError):
                pass

        # Language filters
        lang_ids = params.getlist('languages', [])
        if lang_ids:
            lang_ids_int = []
            for lang_id in lang_ids:
                if str(lang_id).isdigit():
                    lang_ids_int.append(int(lang_id))
            if lang_ids_int:
                queryset = queryset.filter(communication_languages__id__in=lang_ids_int)

        # Gender filter
        gender = params.get('gender')
        if gender in ['male', 'female']:
            queryset = queryset.filter(gender=gender)

        # Remove duplicates
        queryset = queryset.distinct()

        # Add annotations for ratings
        queryset = queryset.annotate(
            avg_rating=Avg('reviews_received__rating'),
            review_count=Count('reviews_received')
        )

        # Apply ordering
        order_by = params.get('order_by', '-avg_rating')
        if order_by == 'rating':
            queryset = queryset.order_by('avg_rating')
        elif order_by == '-rating':
            queryset = queryset.order_by('-avg_rating')
        elif order_by == 'price':
            queryset = queryset.order_by('cost_per_hour')
        elif order_by == '-price':
            queryset = queryset.order_by('-cost_per_hour')
        elif order_by == 'experience':
            queryset = queryset.order_by('years_of_experience')
        elif order_by == '-experience':
            queryset = queryset.order_by('-years_of_experience')
        elif order_by == 'name':
            queryset = queryset.order_by('first_name', 'last_name')
        elif order_by == '-name':
            queryset = queryset.order_by('-first_name', '-last_name')
        else:
            # Default: order by rating descending
            queryset = queryset.order_by('-avg_rating')

        return queryset

    def list(self, request, *args, **kwargs):
        # Get the filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ProfessionalDetailView(generics.RetrieveAPIView):
    """
    Get detailed information about a professional

    GET /api/v1/professionals/{id}/
    """
    queryset = User.objects.filter(
        account_type=User.AccountType.PROFESSIONAL,
        is_active=True
    ).prefetch_related(
        'professions',
        'communication_languages',
        'event_languages'
    ).select_related('currency')

    serializer_class = ProfessionalListSerializer
    permission_classes = [AllowAny]
    lookup_field = 'pk'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # Get additional data
        data = serializer.data

        # Add related data
        data['similar_professionals'] = self._get_similar_professionals(instance)
        data['recent_reviews'] = self._get_recent_reviews(instance)

        return Response(data)

    def _get_similar_professionals(self, professional):
        """Get professionals with similar professions"""
        profession_ids = list(professional.professions.values_list('id', flat=True))

        if not profession_ids:
            return []

        similar = User.objects.filter(
            account_type=User.AccountType.PROFESSIONAL,
            is_active=True,
            professions__id__in=profession_ids
        ).exclude(pk=professional.pk).distinct()[:8]

        return ProfessionalListSerializer(similar, many=True, context={'request': self.request}).data

    def _get_recent_reviews(self, professional):
        """Get recent reviews for the professional"""
        from ..models import Review
        from .serializers import ReviewSerializer

        reviews = Review.objects.filter(
            professional=professional
        ).select_related('reviewer').order_by('-created_at')[:5]

        return ReviewSerializer(reviews, many=True, context={'request': self.request}).data


class FilterOptionsView(generics.RetrieveAPIView):
    """
    Get filter options for professionals search

    GET /api/v1/professionals/filter-options/
    """
    serializer_class = FilterOptionsSerializer
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer({})
        return Response(serializer.data)


class TopProfessionalsView(generics.ListAPIView):
    """
    Get top-rated professionals

    GET /api/v1/professionals/top/

    Query Parameters:
    - limit: Number of professionals to return (default: 10, max: 50)
    - profession: Filter by profession ID
    """
    serializer_class = ProfessionalListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        limit = min(int(self.request.query_params.get('limit', 10)), 50)
        profession_id = self.request.query_params.get('profession')

        queryset = User.objects.filter(
            account_type=User.AccountType.PROFESSIONAL,
            is_active=True
        ).prefetch_related('professions').select_related('currency')

        # Filter by profession if specified
        if profession_id and profession_id.isdigit():
            queryset = queryset.filter(professions__id=int(profession_id))

        # Get top rated
        queryset = queryset.annotate(
            avg_rating=Avg('reviews_received__rating'),
            review_count=Count('reviews_received')
        ).filter(
            avg_rating__gte=4.0,  # Only include professionals with rating >= 4
            review_count__gte=3  # Minimum 3 reviews
        ).order_by('-avg_rating', '-review_count')[:limit]

        return queryset


class RecommendedProfessionalsView(generics.ListAPIView):
    """
    Get recommended professionals for authenticated user

    GET /api/v1/professionals/recommended/

    Returns professionals based on:
    1. User's location (city/country)
    2. User's favorite professions (if any)
    3. Top-rated professionals
    """
    serializer_class = ProfessionalListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user

        # Start with all active professionals
        queryset = User.objects.filter(
            account_type=User.AccountType.PROFESSIONAL,
            is_active=True
        ).exclude(pk=user.pk).prefetch_related('professions').select_related('currency')

        # Filter by user's location if available
        if user.city or user.country:
            location_filters = Q()
            if user.city:
                location_filters |= Q(city__iexact=user.city)
            if user.country:
                location_filters |= Q(country__iexact=user.country)

            # Get professionals from same location
            location_professionals = queryset.filter(location_filters)

            # Get professionals from favorite professions
            if user.account_type == User.AccountType.PROFESSIONAL and user.professions.exists():
                profession_ids = list(user.professions.values_list('id', flat=True))
                profession_professionals = queryset.filter(professions__id__in=profession_ids)

                # Combine both querysets
                queryset = (location_professionals | profession_professionals).distinct()
            else:
                queryset = location_professionals

        # Add ratings and order
        queryset = queryset.annotate(
            avg_rating=Avg('reviews_received__rating'),
            review_count=Count('reviews_received')
        ).order_by('-avg_rating', '-review_count')

        return queryset


class ProfessionTreeView(generics.RetrieveAPIView):
    """
    Get profession hierarchy tree

    GET /api/v1/professions/tree/
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        from ..views import _build_profession_tree_options

        options = _build_profession_tree_options()

        # Convert to hierarchical structure
        tree = self._build_tree(options)

        return Response(tree)

    def _build_tree(self, options):
        """Convert flat list to hierarchical tree"""
        professions = Profession.objects.all().select_related('parent')

        # Build a map of profession by ID
        prof_map = {p.id: p for p in professions}

        # Build tree
        def build_node(prof_id):
            prof = prof_map.get(prof_id)
            if not prof:
                return None

            node = {
                'id': prof.id,
                'name': prof.name,
                'path': prof.path,
                'children': []
            }

            # Find children
            children = [p for p in professions if p.parent_id == prof_id]
            for child in children:
                child_node = build_node(child.id)
                if child_node:
                    node['children'].append(child_node)

            return node

        # Find root nodes (no parent)
        roots = [p for p in professions if p.parent is None]
        tree = []

        for root in roots:
            node = build_node(root.id)
            if node:
                tree.append(node)

        return tree


class PriceRangeView(generics.RetrieveAPIView):
    """
    Get price range for professionals

    GET /api/v1/professionals/price-range/

    Query Parameters:
    - profession: Filter by profession ID (optional)
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        profession_id = request.query_params.get('profession')

        queryset = User.objects.filter(
            account_type=User.AccountType.PROFESSIONAL,
            is_active=True,
            cost_per_hour__isnull=False
        )

        # Filter by profession if specified
        if profession_id and profession_id.isdigit():
            queryset = queryset.filter(professions__id=int(profession_id))

        bounds = queryset.aggregate(
            min_price=Min('cost_per_hour'),
            max_price=Max('cost_per_hour')
        )

        return Response({
            'min': bounds['min_price'] or 0,
            'max': bounds['max_price'] or 1000,
            'currency': 'USD'  # Default, you might want to get this from user preferences
        })