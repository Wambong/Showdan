# events/api/views.py
from rest_framework import viewsets, status, generics, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Min, Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from django.utils.translation import gettext_lazy as _

from ..models import Event, EventCategory, OfferThread, OfferMessage, BusyTime
from accounts.models import Profession
from .serializers import *
from accounts.api.serializers import UserBasicSerializer

User = get_user_model()


# ==================== Pagination Classes ====================

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


# ==================== Event Views ====================

class EventListView(generics.ListAPIView):
    """
    List events with filters (replicates events_list_view)

    GET /api/v1/events/

    Query Parameters:
    - show: 'upcoming', 'past', or 'all' (default: 'upcoming')
    - q: Search query
    - category: EventCategory ID
    - profession: Profession ID (required professions)
    - country: Country filter
    - city: City filter
    - location: Location filter
    - near_me: 'true' or 'false' (requires authentication)
    - min_budget: Minimum event budget
    - max_budget: Maximum event budget
    - order_by: 'start_datetime', '-start_datetime', 'created_at', '-created_at', 'name'
    - page: Page number
    - page_size: Items per page

    Example: /api/v1/events/?show=upcoming&category=1&near_me=true&order_by=start_datetime
    """
    serializer_class = EventListSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPagination

    def get_queryset(self):
        # Base queryset
        now = timezone.now()
        show = self.request.query_params.get('show', 'upcoming')

        base = Event.objects.filter(
            is_posted=True
        ).select_related(
            'event_type', 'currency', 'created_by', 'accepted_professional'
        ).prefetch_related(
            'required_professions'
        ).annotate(
            offers_received_count=Count('offer_threads', distinct=True)
        )

        # Apply time filter
        if show == 'past':
            base = base.filter(end_datetime__lt=now)
            order_by = '-start_datetime'
        elif show == 'all':
            order_by = '-start_datetime'
        else:  # upcoming
            show = 'upcoming'
            base = base.filter(end_datetime__gte=now)
            order_by = 'start_datetime'

        # Store show and order_by in instance for later use
        self.show = show
        self.order_by = self.request.query_params.get('order_by', order_by)

        return base

    def filter_queryset(self, queryset):
        params = self.request.query_params

        # Search query
        q = params.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(location__icontains=q) |
                Q(city__icontains=q) |
                Q(country__icontains=q) |
                Q(created_by__city__icontains=q) |
                Q(created_by__country__icontains=q) |
                Q(event_type__name__icontains=q) |
                Q(required_professions__name__icontains=q)
            )

        # Category filter
        category_id = params.get('category', '').strip()
        if category_id.isdigit():
            queryset = queryset.filter(event_type__id=int(category_id))

        # Profession filter
        profession_id = params.get('profession', '').strip()
        if profession_id.isdigit():
            queryset = queryset.filter(required_professions__id=int(profession_id))

        # Location filters
        country = params.get('country', '').strip()
        if country:
            queryset = queryset.filter(
                Q(country__icontains=country) |
                Q(created_by__country__icontains=country)
            )

        city = params.get('city', '').strip()
        if city:
            queryset = queryset.filter(
                Q(city__icontains=city) |
                Q(created_by__city__icontains=city)
            )

        location = params.get('location', '').strip()
        if location:
            queryset = queryset.filter(location__icontains=location)

        # Near me filter
        near_me = params.get('near_me', '').lower() == 'true'
        if near_me and self.request.user.is_authenticated:
            user = self.request.user
            u_country = (getattr(user, 'country', '') or '').strip()
            u_city = (getattr(user, 'city', '') or '').strip()

            if u_country and u_city:
                queryset = queryset.filter(
                    Q(country__iexact=u_country, city__iexact=u_city) |
                    Q(created_by__country__iexact=u_country, created_by__city__iexact=u_city)
                )
            elif u_country:
                queryset = queryset.filter(
                    Q(country__iexact=u_country) |
                    Q(created_by__country__iexact=u_country)
                )
            elif u_city:
                queryset = queryset.filter(
                    Q(city__iexact=u_city) |
                    Q(created_by__city__iexact=u_city)
                )

        # Budget range filter
        def to_decimal(s):
            if not s:
                return None
            try:
                return Decimal(s)
            except (InvalidOperation, ValueError):
                return None

        min_budget = to_decimal(params.get('min_budget', ''))
        max_budget = to_decimal(params.get('max_budget', ''))

        if min_budget is not None:
            queryset = queryset.filter(event_budget__isnull=False, event_budget__gte=min_budget)

        if max_budget is not None:
            queryset = queryset.filter(event_budget__isnull=False, event_budget__lte=max_budget)

        # Apply ordering
        order_by = params.get('order_by', self.order_by)
        if order_by in ['start_datetime', '-start_datetime', 'created_at', '-created_at', 'name']:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by(self.order_by)

        return queryset.distinct()

    def list(self, request, *args, **kwargs):
        # Get filter options for response
        categories = EventCategory.objects.all().order_by('path')

        # Build profession tree options
        from ..views import _build_profession_tree_options
        profession_options = _build_profession_tree_options()

        # Get budget bounds
        bounds = Event.objects.filter(
            is_posted=True,
            event_budget__isnull=False
        ).aggregate(
            bmin=Min('event_budget'),
            bmax=Max('event_budget')
        )
        bmin = bounds['bmin'] or 0
        bmax = bounds['bmax'] or 10000

        # Get filtered and paginated events
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)

            # Add metadata
            response.data['metadata'] = {
                'show': self.request.query_params.get('show', 'upcoming'),
                'filter_options': {
                    'categories': EventCategorySerializer(categories, many=True).data,
                    'profession_options': [{'id': id, 'label': label} for id, label in profession_options],
                    'budget_range': {
                        'min': int(bmin),
                        'max': int(bmax),
                    }
                },
                'current_filters': {
                    'q': request.query_params.get('q', ''),
                    'category': request.query_params.get('category', ''),
                    'profession': request.query_params.get('profession', ''),
                    'country': request.query_params.get('country', ''),
                    'city': request.query_params.get('city', ''),
                    'location': request.query_params.get('location', ''),
                    'near_me': request.query_params.get('near_me', ''),
                    'min_budget': request.query_params.get('min_budget', ''),
                    'max_budget': request.query_params.get('max_budget', ''),
                    'order_by': request.query_params.get('order_by', ''),
                }
            }
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'events': serializer.data,
            'metadata': {
                'show': self.request.query_params.get('show', 'upcoming'),
                'filter_options': {
                    'categories': EventCategorySerializer(categories, many=True).data,
                    'profession_options': [{'id': id, 'label': label} for id, label in profession_options],
                    'budget_range': {
                        'min': int(bmin),
                        'max': int(bmax),
                    }
                }
            }
        })


class EventDetailView(generics.RetrieveAPIView):
    """
    Get detailed information about an event

    GET /api/v1/events/{id}/
    """
    queryset = Event.objects.filter(is_posted=True).select_related(
        'created_by', 'currency', 'event_type',
        'accepted_thread', 'accepted_thread__professional',
        'accepted_professional'
    ).prefetch_related('required_professions')

    serializer_class = EventDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        data = serializer.data

        # Add additional information
        request_user = request.user
        data['is_creator'] = instance.created_by_id == request_user.id if request_user.is_authenticated else False
        data['is_professional'] = getattr(request_user, 'account_type',
                                          None) == 'professional' if request_user.is_authenticated else False

        # Add accepted professional info if exists
        if instance.is_locked and instance.accepted_thread and instance.accepted_thread.professional:
            accepted_pro = instance.accepted_thread.professional
            data['accepted_professional_full'] = UserBasicSerializer(accepted_pro).data

        return Response(data)


class EventCreateView(generics.CreateAPIView):
    """
    Create a new event

    POST /api/v1/events/create/
    """
    serializer_class = EventCreateUpdateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()


class EventUpdateView(generics.UpdateAPIView):
    """
    Update an existing event

    PUT /api/v1/events/{id}/update/
    """
    serializer_class = EventCreateUpdateSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        # Users can only update their own events
        return Event.objects.filter(created_by=self.request.user, is_posted=True)


class EventDeleteView(generics.DestroyAPIView):
    """
    Delete an event

    DELETE /api/v1/events/{id}/delete/
    """
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        # Users can only delete their own events
        return Event.objects.filter(created_by=self.request.user, is_posted=True)

    def perform_destroy(self, instance):
        # Soft delete by marking as not posted
        instance.is_posted = False
        instance.save()


class UserEventsView(generics.ListAPIView):
    """
    Get events created by the authenticated user

    GET /api/v1/events/my-events/

    Query Parameters:
    - show: 'upcoming', 'past', or 'all' (default: 'upcoming')
    """
    serializer_class = EventListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user
        show = self.request.query_params.get('show', 'upcoming')
        now = timezone.now()

        queryset = Event.objects.filter(
            created_by=user,
            is_posted=True
        ).select_related('event_type', 'currency').prefetch_related('required_professions')

        if show == 'past':
            queryset = queryset.filter(end_datetime__lt=now)
            order_by = '-start_datetime'
        elif show == 'all':
            order_by = '-start_datetime'
        else:  # upcoming
            queryset = queryset.filter(end_datetime__gte=now)
            order_by = 'start_datetime'

        return queryset.order_by(order_by)


# ==================== Event Category Views ====================

class EventCategoryListView(generics.ListAPIView):
    """
    List event categories

    GET /api/v1/events/categories/
    """
    queryset = EventCategory.objects.all().order_by('path')
    serializer_class = EventCategorySerializer
    permission_classes = [AllowAny]
    pagination_class = StandardPagination


class EventCategoryTreeView(generics.ListAPIView):
    """
    Get event category hierarchy tree

    GET /api/v1/events/categories/tree/
    """
    serializer_class = EventCategoryTreeSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return EventCategory.objects.filter(parent=None).order_by('name')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class EventCategoryCreateView(generics.CreateAPIView):
    """
    Create a new event category (admin/staff only)

    POST /api/v1/events/categories/create/
    """
    serializer_class = EventCategorySerializer
    permission_classes = [IsAdminUser]


# ==================== Offer Thread Views ====================

class OfferThreadListView(generics.ListAPIView):
    """
    List offer threads for the authenticated user

    GET /api/v1/events/offer-threads/

    For professionals: threads where they are the professional
    For event creators: threads for their events
    """
    serializer_class = OfferThreadSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user

        if user.account_type == User.AccountType.PROFESSIONAL:
            # Professional sees threads where they are the professional
            return OfferThread.objects.filter(
                professional=user
            ).select_related('event', 'professional').order_by('-created_at')
        else:
            # Event creator sees threads for their events
            return OfferThread.objects.filter(
                event__created_by=user
            ).select_related('event', 'professional').order_by('-created_at')


class OfferThreadDetailView(generics.RetrieveAPIView):
    """
    Get detailed information about an offer thread

    GET /api/v1/events/offer-threads/{id}/
    """
    serializer_class = OfferThreadSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user

        # User can only see threads they're involved in
        if user.account_type == User.AccountType.PROFESSIONAL:
            return OfferThread.objects.filter(professional=user)
        else:
            return OfferThread.objects.filter(event__created_by=user)


class OfferThreadCreateView(generics.CreateAPIView):
    """
    Create a new offer thread (for professionals to apply to events)

    POST /api/v1/events/offer-threads/create/
    """
    serializer_class = OfferThreadSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        event_id = request.data.get('event')
        professional = request.user

        # Check if user is a professional
        if professional.account_type != User.AccountType.PROFESSIONAL:
            return Response(
                {'error': _('Only professionals can create offer threads')},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if event exists and is posted
        try:
            event = Event.objects.get(id=event_id, is_posted=True)
        except Event.DoesNotExist:
            return Response(
                {'error': _('Event not found')},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is the event creator
        if event.created_by == professional:
            return Response(
                {'error': _('You cannot apply to your own event')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if thread already exists
        if OfferThread.objects.filter(event=event, professional=professional).exists():
            return Response(
                {'error': _('You have already applied to this event')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create the thread
        thread = OfferThread.objects.create(event=event, professional=professional)
        serializer = self.get_serializer(thread)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ==================== Offer Message Views ====================

class OfferMessageListView(generics.ListAPIView):
    """
    List messages in an offer thread

    GET /api/v1/events/offer-threads/{thread_id}/messages/
    """
    serializer_class = OfferMessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        thread_id = self.kwargs.get('thread_id')
        user = self.request.user

        # Get thread and check permissions
        thread = get_object_or_404(OfferThread, id=thread_id)

        # Check if user is involved in the thread
        if not (user == thread.professional or user == thread.event.created_by):
            return OfferMessage.objects.none()

        return OfferMessage.objects.filter(
            thread=thread
        ).select_related('sender', 'thread', 'proposed_currency', 'event_currency').order_by('created_at')


class OfferMessageCreateView(generics.CreateAPIView):
    """
    Create a new message in an offer thread

    POST /api/v1/events/offer-threads/{thread_id}/messages/create/
    """
    serializer_class = OfferMessageCreateSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        thread_id = self.kwargs.get('thread_id')
        user = request.user

        # Get thread and check permissions
        thread = get_object_or_404(OfferThread, id=thread_id)

        # Check if user is involved in the thread
        if not (user == thread.professional or user == thread.event.created_by):
            return Response(
                {'error': _('You are not authorized to send messages in this thread')},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if event is still open (not locked)
        if thread.event.is_locked:
            return Response(
                {'error': _('This event is already closed')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create the message
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Add thread and sender info
            serializer.validated_data['thread'] = thread
            serializer.validated_data['sender'] = user

            # Determine sender type
            if user.account_type == User.AccountType.PROFESSIONAL:
                serializer.validated_data['sender_type'] = 'professional'
            else:
                serializer.validated_data['sender_type'] = 'creator'

            # Save the message
            message = serializer.save()

            # Return full message details
            full_serializer = OfferMessageSerializer(message, context={'request': request})
            return Response(full_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OfferMessageUpdateStatusView(generics.UpdateAPIView):
    """
    Update the status of an offer message (accept/reject)
    Only event creator can do this

    PUT /api/v1/events/offer-messages/{id}/update-status/
    """
    serializer_class = OfferMessageSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        # Only return messages from threads where user is the event creator
        return OfferMessage.objects.filter(
            thread__event__created_by=user,
            thread__event__is_locked=False  # Can only update status if event is not locked
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        status_action = request.data.get('status')

        if status_action not in ['accepted', 'rejected']:
            return Response(
                {'error': _('Status must be "accepted" or "rejected"')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update the message status
        instance.status = status_action
        instance.save()

        # If accepted, lock the event and set accepted thread
        if status_action == 'accepted':
            event = instance.thread.event
            event.is_locked = True
            event.accepted_thread = instance.thread
            event.accepted_professional = instance.thread.professional
            event.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# ==================== Busy Time Views ====================

class BusyTimeListView(generics.ListAPIView):
    """
    List busy times for the authenticated user

    GET /api/v1/events/busy-times/
    """
    serializer_class = BusyTimeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user
        return BusyTime.objects.filter(user=user).order_by('-start_datetime')


class BusyTimeCreateView(generics.CreateAPIView):
    """
    Create a new busy time entry

    POST /api/v1/events/busy-times/create/
    """
    serializer_class = BusyTimeSerializer
    permission_classes = [IsAuthenticated]


class BusyTimeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete a busy time entry

    GET /api/v1/events/busy-times/{id}/
    PUT /api/v1/events/busy-times/{id}/
    DELETE /api/v1/events/busy-times/{id}/
    """
    serializer_class = BusyTimeSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        return BusyTime.objects.filter(user=user)


# ==================== Filter Options View ====================

class EventFilterOptionsView(APIView):
    """
    Get filter options for events

    GET /api/v1/events/filter-options/
    """
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = FilterOptionsSerializer({})
        return Response(serializer.data)


# ==================== Quick Stats View ====================

class EventStatsView(APIView):
    """
    Get event statistics for authenticated user

    GET /api/v1/events/stats/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()

        # Events created by user
        user_events = Event.objects.filter(created_by=user, is_posted=True)

        # Events user has applied to (if professional)
        applied_events = 0
        if user.account_type == User.AccountType.PROFESSIONAL:
            applied_events = OfferThread.objects.filter(professional=user).count()

        # Accepted events (if professional)
        accepted_events = 0
        if user.account_type == User.AccountType.PROFESSIONAL:
            accepted_events = Event.objects.filter(
                accepted_professional=user,
                is_locked=True
            ).count()

        stats = {
            'total_events_created': user_events.count(),
            'upcoming_events_created': user_events.filter(end_datetime__gte=now).count(),
            'past_events_created': user_events.filter(end_datetime__lt=now).count(),
            'events_applied_to': applied_events,
            'events_accepted': accepted_events,
            'open_offers': OfferThread.objects.filter(
                event__created_by=user,
                event__is_locked=False
            ).count() if user.account_type != User.AccountType.PROFESSIONAL else 0,
        }

        return Response(stats)