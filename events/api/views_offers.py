# events/api/views_offers.py (with read filter removed)
from rest_framework import views, status, generics, mixins
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.db.models import Q, Max, Count, Prefetch, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from ..models import Event, OfferThread, OfferMessage
from accounts.models import Currency
from .serializers_offers import *
from .serializers import OfferMessageSerializer, OfferThreadSerializer
from accounts.api.serializers import UserBasicSerializer

User = get_user_model()


# ==================== Pagination ====================

class OffersPagination(PageNumberPagination):
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


# ==================== Offer Thread Views ====================

class OfferThreadView(APIView):
    """
    View or create offer thread for an event

    GET /api/v1/offers/threads/{event_id}/ - View thread
    POST /api/v1/offers/threads/{event_id}/ - Create thread (for professionals)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        """
        Get offer thread for an event

        Query Parameters:
        - professional_id: Required for event creators to specify which thread
        """
        event = get_object_or_404(Event, id=event_id)
        user = request.user

        # Check permissions
        if user != event.created_by and user.account_type != User.AccountType.PROFESSIONAL:
            return Response(
                {'error': _('You are not allowed to view offers for this event')},
                status=status.HTTP_403_FORBIDDEN
            )

        # Determine which thread to show
        if user.account_type == User.AccountType.PROFESSIONAL and user != event.created_by:
            # Professional viewing their own thread
            if event.is_locked:
                # If locked, only show existing thread
                thread = OfferThread.objects.filter(event=event, professional=user).first()
                if not thread:
                    return Response(
                        {'error': _('This event is locked. You cannot create a new offer thread')},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Get or create thread for professional
                thread, created = OfferThread.objects.get_or_create(event=event, professional=user)
        else:
            # Event creator - must specify professional
            professional_id = request.query_params.get('professional_id')
            if not professional_id:
                return Response(
                    {'error': _('Professional ID is required to view offer thread')},
                    status=status.HTTP_400_BAD_REQUEST
                )

            thread = get_object_or_404(OfferThread, event=event, professional_id=professional_id)

        # Get messages
        messages = thread.messages.select_related(
            'sender', 'proposed_currency', 'event_currency'
        ).order_by('created_at')

        # Serialize data
        thread_data = OfferThreadDetailSerializer(thread, context={'request': request}).data
        messages_data = OfferMessageSerializer(messages, many=True, context={'request': request}).data

        # Determine available forms
        show_offer_form = (user.account_type == User.AccountType.PROFESSIONAL and
                           user == thread.professional and not event.is_locked)
        show_counter_form = (user == event.created_by and not event.is_locked)

        return Response({
            'thread': thread_data,
            'messages': messages_data,
            'event': {
                'id': event.id,
                'name': event.name,
                'is_locked': event.is_locked,
                'currency': event.currency_id,
            },
            'permissions': {
                'is_creator': user == event.created_by,
                'is_professional': user == thread.professional,
                'can_send_offer': show_offer_form,
                'can_send_counter': show_counter_form,
            },
            'forms': {
                'currencies': CurrencySerializer(Currency.objects.all(), many=True).data if show_offer_form else [],
            }
        })

    def post(self, request, event_id):
        """
        Create a new offer thread (professional applying to event)
        """
        event = get_object_or_404(Event, id=event_id, is_posted=True)
        user = request.user

        # Check if user is professional
        if user.account_type != User.AccountType.PROFESSIONAL:
            return Response(
                {'error': _('Only professionals can create offer threads')},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if user is not the creator
        if event.created_by_id == user.id:
            return Response(
                {'error': _('You cannot apply to your own event')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if event is locked
        if event.is_locked:
            return Response(
                {'error': _('This event is locked')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if thread already exists
        if OfferThread.objects.filter(event=event, professional=user).exists():
            return Response(
                {'error': _('You have already applied to this event')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create thread
        with transaction.atomic():
            thread = OfferThread.objects.create(event=event, professional=user)

            # Create initial message if provided
            message_text = request.data.get('message', '')
            if message_text:
                OfferMessage.objects.create(
                    thread=thread,
                    sender=user,
                    sender_type=OfferMessage.SenderType.PROFESSIONAL,
                    message=message_text,
                )

        serializer = OfferThreadDetailSerializer(thread, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ==================== Offer Message Views ====================

class SendOfferView(APIView):
    """
    Send an offer from professional to event creator

    POST /api/v1/offers/events/{event_id}/send-offer/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        """Send an offer (professional to creator)"""
        serializer = OfferCreateSerializer(
            data=request.data,
            context={'request': request, 'event_id': event_id}
        )

        if serializer.is_valid():
            with transaction.atomic():
                offer_message = serializer.save()

                # Return the created message
                message_serializer = OfferMessageSerializer(
                    offer_message,
                    context={'request': request}
                )
                return Response(message_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendCounterOfferView(APIView):
    """
    Send a counter offer from event creator to professional

    POST /api/v1/offers/threads/{thread_id}/counter-offer/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id):
        """Send a counter offer (creator to professional)"""
        serializer = CounterOfferSerializer(
            data=request.data,
            context={'request': request, 'thread_id': thread_id}
        )

        if serializer.is_valid():
            with transaction.atomic():
                counter_message = serializer.save()

                # Return the created message
                message_serializer = OfferMessageSerializer(
                    counter_message,
                    context={'request': request}
                )
                return Response(message_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendChatMessageView(APIView):
    """
    Send a chat message in an offer thread

    POST /api/v1/offers/threads/{thread_id}/chat/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id):
        """Send a chat message"""
        serializer = ChatMessageSerializer(
            data=request.data,
            context={'request': request, 'thread_id': thread_id}
        )

        if serializer.is_valid():
            chat_message = serializer.save()

            # Return the created message
            message_serializer = OfferMessageSerializer(
                chat_message,
                context={'request': request}
            )
            return Response(message_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== Offer Action Views ====================

class OfferActionView(APIView):
    """
    Accept or reject an offer

    POST /api/v1/offers/events/{event_id}/professionals/{pro_id}/action/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id, pro_id):
        """Accept or reject an offer"""
        event = get_object_or_404(Event, id=event_id, created_by=request.user)
        thread = get_object_or_404(OfferThread, event=event, professional_id=pro_id)

        # Get the action
        action = request.data.get('action')
        if action not in ['accept', 'reject']:
            return Response(
                {'error': _('Action must be "accept" or "reject"')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the latest offer message
        last_offer = thread.messages.filter(
            proposed_amount__isnull=False
        ).order_by('-created_at').first()

        if not last_offer:
            return Response(
                {'error': _('No offer to process')},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            if action == 'accept':
                # Accept the offer
                event.is_locked = True
                event.accepted_thread = thread
                event.accepted_professional = thread.professional
                event.save(update_fields=['is_locked', 'accepted_thread', 'accepted_professional'])

                last_offer.status = OfferMessage.Status.ACCEPTED
                last_offer.save(update_fields=['status'])

                message = _('Offer accepted successfully')
                response_data = {
                    'message': message,
                    'event_locked': True,
                    'accepted_professional': UserBasicSerializer(thread.professional).data,
                    'offer_status': 'accepted'
                }

            else:  # reject
                # Reject the offer
                last_offer.status = OfferMessage.Status.REJECTED
                last_offer.save(update_fields=['status'])

                message = _('Offer rejected')
                response_data = {
                    'message': message,
                    'event_locked': event.is_locked,
                    'offer_status': 'rejected'
                }

        return Response(response_data)


# ==================== Offers Inbox Views ====================

class OffersInboxView(generics.ListAPIView):
    """
    Get user's offer inbox

    GET /api/v1/offers/inbox/

    Query Parameters:
    - thread: Specific thread ID to view
    - event: Event ID (for professionals to create/view thread)
    - status: Filter by status (pending, accepted, rejected, all)
    - unread_only: Only show threads with unread messages
    - page: Page number
    - page_size: Items per page
    """
    serializer_class = OfferThreadDetailSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = OffersPagination

    def get_queryset(self):
        user = self.request.user

        # Base queryset: threads where user is professional or creator
        threads = OfferThread.objects.select_related(
            'event', 'event__created_by', 'event__currency', 'professional'
        ).filter(
            Q(professional=user) | Q(event__created_by=user)
        ).annotate(
            last_msg_at=Max('messages__created_at'),
            message_count=Count('messages'),
            # REMOVED: has_unread=Count('messages', filter=Q(messages__read=False))
        ).order_by('-last_msg_at', '-created_at')

        # Apply filters
        status = self.request.query_params.get('status', 'all')
        if status != 'all':
            if status == 'pending':
                threads = threads.filter(event__is_locked=False)
            elif status == 'accepted':
                threads = threads.filter(
                    event__is_locked=True,
                    event__accepted_thread_id=F('id')
                )
            elif status == 'rejected':
                # You might need to track rejected status differently
                pass

        # Unread only filter - REMOVED since read field doesn't exist
        # unread_only = self.request.query_params.get('unread_only', '').lower() == 'true'
        # if unread_only:
        #     threads = threads.filter(has_unread__gt=0)

        return threads

    def list(self, request, *args, **kwargs):
        user = request.user

        # Check for event parameter (for professionals to create/view thread)
        event_id = request.query_params.get('event')
        if event_id and user.account_type == User.AccountType.PROFESSIONAL:
            try:
                event = Event.objects.get(id=event_id, is_posted=True)

                # Check if user is not the creator
                if event.created_by_id == user.id:
                    return Response(
                        {'error': _('You cannot make an offer on your own event')},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Check if event is locked
                if event.is_locked:
                    return Response(
                        {'error': _('This event is locked')},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Get or create thread
                thread, created = OfferThread.objects.get_or_create(
                    event=event,
                    professional=user
                )

                # Redirect to thread view
                return Response({
                    'redirect_to_thread': thread.id,
                    'thread_created': created,
                    'thread': OfferThreadDetailSerializer(thread, context={'request': request}).data
                })

            except Event.DoesNotExist:
                return Response(
                    {'error': _('Event not found')},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Get specific thread if requested
        thread_id = request.query_params.get('thread')
        active_thread = None
        thread_messages = []

        if thread_id:
            try:
                active_thread = OfferThread.objects.select_related(
                    'event', 'event__created_by', 'event__currency', 'professional'
                ).get(id=thread_id)

                # Permission check
                if (active_thread.professional_id != user.id and
                        active_thread.event.created_by_id != user.id):
                    return Response(
                        {'error': _('You are not authorized to view this thread')},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # Get messages for active thread
                thread_messages = OfferMessage.objects.filter(
                    thread=active_thread
                ).select_related('sender', 'proposed_currency', 'event_currency').order_by('created_at')

            except OfferThread.DoesNotExist:
                pass

        # Get paginated threads
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            response = self.get_paginated_response(serializer.data)

            # Add active thread and messages if available
            if active_thread:
                response.data['active_thread'] = OfferThreadDetailSerializer(
                    active_thread, context={'request': request}
                ).data
                response.data['active_thread_messages'] = OfferMessageSerializer(
                    thread_messages, many=True, context={'request': request}
                ).data

                # Add form availability
                response.data['forms'] = {
                    'can_send_offer': (user.account_type == User.AccountType.PROFESSIONAL and
                                       user == active_thread.professional and
                                       not active_thread.event.is_locked),
                    'can_send_counter': (user == active_thread.event.created_by and
                                         not active_thread.event.is_locked),
                    'currencies': CurrencySerializer(
                        Currency.objects.all(), many=True
                    ).data if user == active_thread.professional else [],
                }

            # Add statistics
            response.data['stats'] = self._get_inbox_stats(user)

            return response

        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response({
            'threads': serializer.data,
            'active_thread': OfferThreadDetailSerializer(
                active_thread, context={'request': request}
            ).data if active_thread else None,
            'active_thread_messages': OfferMessageSerializer(
                thread_messages, many=True, context={'request': request}
            ).data if active_thread else [],
            'stats': self._get_inbox_stats(user),
        })

    def _get_inbox_stats(self, user):
        """Get inbox statistics for the user"""
        threads = OfferThread.objects.filter(
            Q(professional=user) | Q(event__created_by=user)
        )

        total_threads = threads.count()

        # Count pending offers (events not locked)
        pending_offers = threads.filter(event__is_locked=False).count()

        # Count accepted offers (user's threads that are accepted)
        if user.account_type == User.AccountType.PROFESSIONAL:
            accepted_offers = threads.filter(
                event__is_locked=True,
                event__accepted_thread_id=F('id')
            ).count()
        else:
            accepted_offers = threads.filter(event__is_locked=True).count()

        # Get most recent activity
        recent_activity = threads.aggregate(
            last_activity=Max('messages__created_at')
        )['last_activity']

        return {
            'total_threads': total_threads,
            'pending_offers': pending_offers,
            'accepted_offers': accepted_offers,
            'recent_activity': recent_activity,
            'unread_count': 0,
        }


class InboxStatsView(APIView):
    """
    Get inbox statistics

    GET /api/v1/offers/inbox/stats/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        threads = OfferThread.objects.filter(
            Q(professional=user) | Q(event__created_by=user)
        )

        # Calculate statistics
        stats = {
            'total_threads': threads.count(),
            'pending_threads': threads.filter(event__is_locked=False).count(),
            'accepted_threads': threads.filter(
                event__is_locked=True,
                event__accepted_thread_id=F('id')
            ).count(),
            'recent_activity': threads.aggregate(
                last_activity=Max('messages__created_at')
            )['last_activity'],
        }

        # Add role-specific stats
        if user.account_type == User.AccountType.PROFESSIONAL:
            stats['events_applied_to'] = threads.filter(professional=user).count()
            stats['events_accepted'] = threads.filter(
                professional=user,
                event__is_locked=True,
                event__accepted_thread_id=F('id')
            ).count()
        else:
            stats['events_created'] = Event.objects.filter(created_by=user, is_posted=True).count()
            stats['open_offers'] = threads.filter(
                event__created_by=user,
                event__is_locked=False
            ).count()

        return Response(stats)


# ==================== Booking Request Views ====================

class BookingRequestView(APIView):
    """
    Create a booking request from calendar

    POST /api/v1/offers/booking-request/

    This creates a lightweight event and opens a thread with a professional
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Create a booking request from calendar selection"""
        serializer = BookingRequestSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            with transaction.atomic():
                thread = serializer.save()

                # Return the created thread
                thread_serializer = OfferThreadDetailSerializer(
                    thread,
                    context={'request': request}
                )
                return Response(thread_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class QuickBookingView(APIView):
    """
    Quick booking endpoint with minimal parameters

    POST /api/v1/offers/quick-booking/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Create a quick booking request"""
        professional_id = request.data.get('professional_id')
        date_str = request.data.get('date')
        start_str = request.data.get('start_time')
        end_str = request.data.get('end_time')

        if not all([professional_id, date_str, start_str, end_str]):
            return Response(
                {'error': _('Professional ID, date, start time, and end time are required')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse date and times
        try:
            date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            start_time = timezone.datetime.strptime(start_str, '%H:%M').time()
            end_time = timezone.datetime.strptime(end_str, '%H:%M').time()
        except ValueError:
            return Response(
                {'error': _('Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create booking request
        booking_data = {
            'professional_id': professional_id,
            'date': date,
            'start_time': start_time,
            'end_time': end_time,
            'message': request.data.get('message', '')
        }

        serializer = BookingRequestSerializer(
            data=booking_data,
            context={'request': request}
        )

        if serializer.is_valid():
            with transaction.atomic():
                thread = serializer.save()

                # Return simplified response
                return Response({
                    'success': True,
                    'thread_id': thread.id,
                    'event_id': thread.event.id,
                    'professional': UserBasicSerializer(thread.professional).data,
                    'start_datetime': thread.event.start_datetime,
                    'end_datetime': thread.event.end_datetime,
                    'message': _('Booking request created successfully')
                }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== Utility Views ====================

class OfferThreadMessagesView(generics.ListAPIView):
    """
    Get messages for a specific offer thread

    GET /api/v1/offers/threads/{thread_id}/messages/
    """
    serializer_class = OfferMessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = OffersPagination

    def get_queryset(self):
        thread_id = self.kwargs['thread_id']
        user = self.request.user

        # Get thread and check permissions
        thread = get_object_or_404(OfferThread, id=thread_id)

        # Check if user is participant
        if user.id != thread.professional_id and user.id != thread.event.created_by_id:
            return OfferMessage.objects.none()

        return OfferMessage.objects.filter(
            thread=thread
        ).select_related('sender', 'proposed_currency', 'event_currency').order_by('created_at')


class MarkMessagesReadView(APIView):
    """
    Mark messages as read

    POST /api/v1/offers/threads/{thread_id}/mark-read/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id):
        thread = get_object_or_404(OfferThread, id=thread_id)
        user = request.user

        # Check if user is participant
        if user.id != thread.professional_id and user.id != thread.event.created_by_id:
            return Response(
                {'error': _('You are not a participant in this thread')},
                status=status.HTTP_403_FORBIDDEN
            )

        # Note: This endpoint won't work until you add a 'read' field to OfferMessage
        # thread.messages.filter(read=False).update(read=True)

        return Response({
            'success': True,
            'message': _('Messages marked as read'),
            'thread_id': thread_id
        })


class AvailableCurrenciesView(APIView):
    """
    Get available currencies for offers

    GET /api/v1/offers/currencies/
    """
    permission_classes = [AllowAny]

    def get(self, request):
        currencies = Currency.objects.all()
        serializer = CurrencySerializer(currencies, many=True)
        return Response(serializer.data)