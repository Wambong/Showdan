from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Max, Min
from django.utils import timezone
from datetime import datetime, date, timedelta
from django.shortcuts import get_object_or_404
import calendar

from ..models import Event, EventCategory, BusyTime, OfferThread, OfferMessage
from .serializers_calendar import (
    EventSerializer, EventListSerializer, EventCreateSerializer,
    EventCategorySerializer, EventCategoryTreeSerializer,
    BusyTimeSerializer, BusyTimeCreateSerializer,
    CalendarMonthSerializer, CalendarEventSerializer,
    OfferThreadSerializer, OfferMessageSerializer
)


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ============ Event Categories ============
class EventCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """API for event categories"""
    queryset = EventCategory.objects.all()
    serializer_class = EventCategorySerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['GET'])
    def tree(self, request):
        """Get categories as hierarchical tree"""
        queryset = EventCategory.objects.filter(parent=None)
        serializer = EventCategoryTreeSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['GET'])
    def children(self, request, pk=None):
        """Get children of a specific category"""
        category = self.get_object()
        children = category.children.all()
        serializer = self.get_serializer(children, many=True)
        return Response(serializer.data)


# ============ Events ============
class EventViewSet(viewsets.ModelViewSet):
    """API for events"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['event_type', 'country', 'city', 'is_posted']
    search_fields = ['name', 'location', 'description']
    ordering_fields = ['start_datetime', 'end_datetime', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        queryset = Event.objects.select_related(
            'event_type', 'currency', 'created_by',
            'accepted_thread', 'accepted_thread__professional'
        ).prefetch_related('required_professions')

        # Filter based on user role and context
        if self.action == 'my_events':
            # Events created by the user
            queryset = queryset.filter(created_by=user)
        elif self.action == 'booked_events':
            # Events where professional is booked
            if user.account_type == 'professional':
                queryset = queryset.filter(
                    is_locked=True,
                    accepted_thread__professional=user
                )
            else:
                queryset = queryset.none()
        else:
            # Public events that are posted
            queryset = queryset.filter(is_posted=True)

        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return EventCreateSerializer
        elif self.action in ['list', 'my_events', 'booked_events']:
            return EventListSerializer
        return EventSerializer

    @action(detail=False, methods=['GET'])
    def my_events(self, request):
        """Get events created by current user"""
        page = self.paginate_queryset(self.get_queryset())
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['GET'])
    def booked_events(self, request):
        """Get events booked by professional"""
        page = self.paginate_queryset(self.get_queryset())
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['GET'])
    def upcoming(self, request):
        """Get upcoming events"""
        queryset = self.get_queryset().filter(
            start_datetime__gte=timezone.now()
        ).order_by('start_datetime')

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['GET'])
    def filter_options(self, request):
        """Get filter options for events"""
        from django.db.models import Count

        options = {
            'categories': EventCategorySerializer(
                EventCategory.objects.all(),
                many=True
            ).data,
            'countries': list(Event.objects.filter(
                is_posted=True
            ).exclude(country='').values_list(
                'country', flat=True
            ).distinct()),
            'cities': list(Event.objects.filter(
                is_posted=True
            ).exclude(city='').values_list(
                'city', flat=True
            ).distinct()),
        }
        return Response(options)

    @action(detail=False, methods=['GET'])
    def stats(self, request):
        """Get event statistics for current user"""
        user = request.user

        stats = {
            'total_created': Event.objects.filter(created_by=user).count(),
            'total_booked': Event.objects.filter(
                is_locked=True,
                accepted_thread__professional=user
            ).count() if user.account_type == 'professional' else 0,
            'upcoming': Event.objects.filter(
                Q(created_by=user) | Q(accepted_thread__professional=user),
                start_datetime__gte=timezone.now()
            ).count(),
            'pending_offers': OfferThread.objects.filter(
                event__created_by=user,
                messages__status='pending'
            ).distinct().count(),
        }

        return Response(stats)


# ============ Calendar ============
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def calendar_month_view(request):
    """Get calendar data for a specific month"""
    user = request.user
    today = timezone.localdate()

    # Get year and month from query params
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    # Calculate month range
    first_day = date(year, month, 1)
    _, last_day_num = calendar.monthrange(year, month)
    last_day = date(year, month, last_day_num)

    # Get events for the month
    creator_events = Event.objects.filter(
        created_by=user,
        start_datetime__date__lte=last_day,
        end_datetime__date__gte=first_day
    ).select_related('currency', 'created_by')

    booked_events = Event.objects.none()
    if user.account_type == 'professional':
        booked_events = Event.objects.filter(
            is_locked=True,
            accepted_thread__professional=user,
            start_datetime__date__lte=last_day,
            end_datetime__date__gte=first_day
        ).select_related('currency', 'created_by')

    # Get busy times for the month
    busy_times = BusyTime.objects.filter(
        user=user,
        start_datetime__date__lte=last_day,
        end_datetime__date__gte=first_day
    )

    # Prepare calendar weeks
    cal = calendar.Calendar(firstweekday=0)  # Monday
    weeks = cal.monthdatescalendar(year, month)

    # Month navigation
    prev_month = (date(year, month, 1) - timedelta(days=1)).replace(day=1)
    next_month = (date(year, month, 28) + timedelta(days=10)).replace(day=1)

    response_data = {
        'year': year,
        'month': month,
        'month_name': date(year, month, 1).strftime('%B'),
        'prev_year': prev_month.year,
        'prev_month': prev_month.month,
        'next_year': next_month.year,
        'next_month': next_month.month,
        'today': today.isoformat(),
        'weeks': weeks,
        'events': CalendarEventSerializer(
            creator_events.union(booked_events),
            many=True,
            context={'request': request}
        ).data,
        'busy_times': BusyTimeSerializer(busy_times, many=True).data,
        'is_professional': user.account_type == 'professional',
    }

    return Response(response_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def calendar_events_by_date(request):
    """Get events for a specific date"""
    user = request.user
    date_str = request.GET.get('date')

    if not date_str:
        return Response(
            {'error': 'Date parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get events for the date
    creator_events = Event.objects.filter(
        created_by=user,
        start_datetime__date__lte=target_date,
        end_datetime__date__gte=target_date
    )

    booked_events = Event.objects.none()
    if user.account_type == 'professional':
        booked_events = Event.objects.filter(
            is_locked=True,
            accepted_thread__professional=user,
            start_datetime__date__lte=target_date,
            end_datetime__date__gte=target_date
        )

    events = creator_events.union(booked_events)

    # Get busy times for the date
    busy_times = BusyTime.objects.filter(
        user=user,
        start_datetime__date__lte=target_date,
        end_datetime__date__gte=target_date
    )

    response_data = {
        'date': target_date.isoformat(),
        'events': CalendarEventSerializer(events, many=True).data,
        'busy_times': BusyTimeSerializer(busy_times, many=True).data,
        'day_of_week': target_date.strftime('%A'),
    }

    return Response(response_data)


# ============ Busy Times ============
class BusyTimeViewSet(viewsets.ModelViewSet):
    """API for busy/unavailable times"""
    serializer_class = BusyTimeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        return BusyTime.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return BusyTimeCreateSerializer
        return BusyTimeSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['POST'])
    def delete_day(self, request):
        """Delete busy time for a specific day"""
        user = request.user
        day_str = request.data.get('day')

        if not day_str:
            return Response(
                {'error': 'Day parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_day = date.fromisoformat(day_str)
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find busy times overlapping with the day
        day_start = timezone.make_aware(
            datetime.combine(target_day, datetime.min.time())
        )
        day_end = timezone.make_aware(
            datetime.combine(target_day, datetime.max.time())
        )

        busy_times = BusyTime.objects.filter(
            user=user,
            start_datetime__lte=day_end,
            end_datetime__gte=day_start
        ).order_by('start_datetime')

        deleted_count = 0
        modified_count = 0

        for busy_time in busy_times:
            # Case 1: Fully within the day - delete
            if busy_time.start_datetime >= day_start and busy_time.end_datetime <= day_end:
                busy_time.delete()
                deleted_count += 1

            # Case 2: Starts before, ends during - truncate end
            elif busy_time.start_datetime < day_start and busy_time.end_datetime <= day_end:
                busy_time.end_datetime = day_start - timedelta(seconds=1)
                busy_time.save()
                modified_count += 1

            # Case 3: Starts during, ends after - move start
            elif busy_time.start_datetime >= day_start and busy_time.end_datetime > day_end:
                busy_time.start_datetime = day_end + timedelta(seconds=1)
                busy_time.save()
                modified_count += 1

            # Case 4: Spans the entire day - split into two
            elif busy_time.start_datetime < day_start and busy_time.end_datetime > day_end:
                # Create right segment
                BusyTime.objects.create(
                    user=user,
                    start_datetime=day_end + timedelta(seconds=1),
                    end_datetime=busy_time.end_datetime,
                    is_all_day=busy_time.is_all_day,
                    note=busy_time.note
                )
                # Truncate current to left segment
                busy_time.end_datetime = day_start - timedelta(seconds=1)
                busy_time.save()
                modified_count += 1

        return Response({
            'message': f'Busy time removed for {target_day}',
            'deleted': deleted_count,
            'modified': modified_count,
            'day': target_day.isoformat()
        })

    @action(detail=False, methods=['GET'])
    def date_range(self, request):
        """Get busy times within a date range"""
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        if not start_date_str or not end_date_str:
            return Response(
                {'error': 'Both start_date and end_date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_datetime = timezone.make_aware(
            datetime.combine(start_date, datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            datetime.combine(end_date, datetime.max.time())
        )

        busy_times = BusyTime.objects.filter(
            user=request.user,
            start_datetime__lte=end_datetime,
            end_datetime__gte=start_datetime
        )

        serializer = self.get_serializer(busy_times, many=True)
        return Response(serializer.data)


# ============ Offer Threads and Messages ============
class OfferThreadViewSet(viewsets.ReadOnlyModelViewSet):
    """API for offer threads"""
    serializer_class = OfferThreadSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user

        if user.account_type == 'professional':
            # Professionals see threads where they are the professional
            return OfferThread.objects.filter(
                professional=user
            ).select_related('event', 'professional')
        else:
            # Event creators see threads for their events
            return OfferThread.objects.filter(
                event__created_by=user
            ).select_related('event', 'professional')

    @action(detail=True, methods=['GET'])
    def messages(self, request, pk=None):
        """Get messages for a specific thread"""
        thread = self.get_object()
        messages = thread.messages.all()
        serializer = OfferMessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def inbox_stats(self, request):
        """Get inbox statistics"""
        user = request.user

        if user.account_type == 'professional':
            total = OfferThread.objects.filter(professional=user).count()
            unread = OfferThread.objects.filter(
                professional=user,
                messages__status='pending'
            ).distinct().count()
        else:
            total = OfferThread.objects.filter(event__created_by=user).count()
            unread = OfferThread.objects.filter(
                event__created_by=user,
                messages__status='pending'
            ).distinct().count()

        return Response({
            'total': total,
            'unread': unread,
            'pending_offers': unread
        })


class OfferMessageViewSet(viewsets.ModelViewSet):
    """API for offer messages"""
    serializer_class = OfferMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return OfferMessage.objects.filter(
            Q(thread__event__created_by=user) | Q(thread__professional=user)
        ).select_related('thread', 'sender', 'proposed_currency')

    def perform_create(self, serializer):
        # Set sender_type based on user role
        if self.request.user.account_type == 'professional':
            sender_type = 'professional'
        else:
            sender_type = 'creator'

        serializer.save(
            sender=self.request.user,
            sender_type=sender_type
        )

    @action(detail=True, methods=['POST'])
    def accept(self, request, pk=None):
        """Accept an offer"""
        message = self.get_object()

        # Only event creator can accept offers
        if request.user != message.thread.event.created_by:
            return Response(
                {'error': 'Only event creator can accept offers'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Update message status
        message.status = 'accepted'
        message.save()

        # Lock the event and set accepted professional
        event = message.thread.event
        event.is_locked = True
        event.accepted_thread = message.thread
        event.accepted_professional = message.thread.professional
        event.save()

        # Reject all other pending offers for this event
        OfferMessage.objects.filter(
            thread__event=event,
            status='pending'
        ).exclude(pk=message.pk).update(status='rejected')

        serializer = self.get_serializer(message)
        return Response(serializer.data)

    @action(detail=True, methods=['POST'])
    def reject(self, request, pk=None):
        """Reject an offer"""
        message = self.get_object()

        # Only event creator can reject offers
        if request.user != message.thread.event.created_by:
            return Response(
                {'error': 'Only event creator can reject offers'},
                status=status.HTTP_403_FORBIDDEN
            )

        message.status = 'rejected'
        message.save()

        serializer = self.get_serializer(message)
        return Response(serializer.data)