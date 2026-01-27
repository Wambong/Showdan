# events/api/serializers_offers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ..models import Event, OfferThread, OfferMessage
from accounts.models import Currency
from accounts.api.serializers import UserBasicSerializer, CurrencySerializer
from accounts.utils import get_rate
from decimal import Decimal

User = get_user_model()


# ============ Offer Thread Serializers ============

class OfferThreadDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for offer threads"""
    event_info = serializers.SerializerMethodField()
    professional_info = UserBasicSerializer(source='professional', read_only=True)
    creator_info = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    can_message = serializers.SerializerMethodField()

    class Meta:
        model = OfferThread
        fields = (
            'id', 'event', 'event_info', 'professional', 'professional_info',
            'creator_info', 'created_at', 'last_message', 'unread_count', 'can_message'
        )

    def get_event_info(self, obj):
        from .serializers import EventListSerializer
        return EventListSerializer(obj.event, context=self.context).data

    def get_creator_info(self, obj):
        if obj.event and obj.event.created_by:
            return UserBasicSerializer(obj.event.created_by, context=self.context).data
        return None

    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'id': last_msg.id,
                'message': last_msg.message,
                'sender_type': last_msg.sender_type,
                'created_at': last_msg.created_at,
                'status': last_msg.status
            }
        return None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0

        # This is a simple implementation - you might want to track read status
        return obj.messages.count()  # Placeholder

    def get_can_message(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        user = request.user
        event = obj.event

        # Check if user is participant
        if user.id == obj.professional_id or user.id == event.created_by_id:
            # If event is locked, only accepted thread can message
            if event.is_locked and event.accepted_thread_id != obj.id:
                return False
            return True

        return False


# ============ Offer Message Serializers ============

class OfferCreateSerializer(serializers.Serializer):
    """Serializer for creating offers (professional to creator)"""
    proposed_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    proposed_currency = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.all())
    message = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        request = self.context.get('request')
        event_id = self.context.get('event_id')

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_('Authentication required'))

        # Check if user is professional
        if request.user.account_type != User.AccountType.PROFESSIONAL:
            raise serializers.ValidationError(_('Only professionals can make offers'))

        # Check if event exists
        try:
            event = Event.objects.get(id=event_id, is_posted=True)
        except Event.DoesNotExist:
            raise serializers.ValidationError(_('Event not found'))

        # Check if event is locked
        if event.is_locked:
            raise serializers.ValidationError(_('This event is locked'))

        # Check if user is not the creator
        if event.created_by_id == request.user.id:
            raise serializers.ValidationError(_('You cannot make an offer on your own event'))

        data['event'] = event
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        event = validated_data['event']

        # Get or create thread
        thread, created = OfferThread.objects.get_or_create(
            event=event,
            professional=request.user
        )

        # Convert to event currency if possible
        amount = validated_data['proposed_amount']
        from_cur = validated_data['proposed_currency']
        message_text = validated_data.get('message', '')

        event_cur = event.currency
        rate = None
        converted = None

        if event_cur and from_cur:
            rate = get_rate(from_cur, event_cur)
            if rate:
                converted = (amount * rate).quantize(Decimal('0.01'))

        # Create the offer message
        offer_message = OfferMessage.objects.create(
            thread=thread,
            sender=request.user,
            sender_type=OfferMessage.SenderType.PROFESSIONAL,
            message=message_text,
            proposed_amount=amount,
            proposed_currency=from_cur,
            event_currency=event_cur,
            conversion_rate=rate,
            converted_amount=converted,
            status=OfferMessage.Status.PENDING,
        )

        return offer_message


class CounterOfferSerializer(serializers.Serializer):
    """Serializer for counter offers (creator to professional)"""
    proposed_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    message = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        request = self.context.get('request')
        thread_id = self.context.get('thread_id')

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_('Authentication required'))

        # Check if thread exists
        try:
            thread = OfferThread.objects.select_related('event').get(id=thread_id)
        except OfferThread.DoesNotExist:
            raise serializers.ValidationError(_('Thread not found'))

        # Check if user is event creator
        if thread.event.created_by_id != request.user.id:
            raise serializers.ValidationError(_('Only event creator can make counter offers'))

        # Check if event is locked
        if thread.event.is_locked:
            raise serializers.ValidationError(_('This event is locked'))

        data['thread'] = thread
        return data

    def create(self, validated_data):
        thread = validated_data['thread']
        request = self.context.get('request')
        amount = validated_data['proposed_amount']
        message_text = validated_data.get('message', '')

        event_cur = thread.event.currency

        # Create counter offer message
        counter_message = OfferMessage.objects.create(
            thread=thread,
            sender=request.user,
            sender_type=OfferMessage.SenderType.CREATOR,
            message=message_text,
            proposed_amount=amount,
            proposed_currency=event_cur,
            event_currency=event_cur,
            conversion_rate=1 if event_cur else None,
            converted_amount=amount if event_cur else None,
            status=OfferMessage.Status.PENDING,
        )

        return counter_message


class ChatMessageSerializer(serializers.Serializer):
    """Serializer for chat messages"""
    message = serializers.CharField(min_length=1, max_length=2000)

    def validate(self, data):
        request = self.context.get('request')
        thread_id = self.context.get('thread_id')

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_('Authentication required'))

        # Check if thread exists
        try:
            thread = OfferThread.objects.select_related('event').get(id=thread_id)
        except OfferThread.DoesNotExist:
            raise serializers.ValidationError(_('Thread not found'))

        # Check if user is participant
        if request.user.id != thread.professional_id and request.user.id != thread.event.created_by_id:
            raise serializers.ValidationError(_('You are not a participant in this thread'))

        # If event is locked, only accepted thread can send messages
        if thread.event.is_locked and thread.event.accepted_thread_id != thread.id:
            raise serializers.ValidationError(_('Only the accepted offer thread can continue chatting'))

        data['thread'] = thread
        return data

    def create(self, validated_data):
        thread = validated_data['thread']
        request = self.context.get('request')
        message_text = validated_data['message']

        # Determine sender type
        if request.user.account_type == User.AccountType.PROFESSIONAL:
            sender_type = OfferMessage.SenderType.PROFESSIONAL
        else:
            sender_type = OfferMessage.SenderType.CREATOR

        # Create chat message
        chat_message = OfferMessage.objects.create(
            thread=thread,
            sender=request.user,
            sender_type=sender_type,
            message=message_text,
            # No proposed amount for chat messages
        )

        return chat_message


class OfferActionSerializer(serializers.Serializer):
    """Serializer for accepting/rejecting offers"""
    action = serializers.ChoiceField(choices=['accept', 'reject'])
    redirect_url = serializers.CharField(required=False, allow_blank=True)


# ============ Booking Request Serializers ============

class BookingRequestSerializer(serializers.Serializer):
    """Serializer for booking requests from calendar"""
    professional_id = serializers.IntegerField(min_value=1)
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, data):
        request = self.context.get('request')
        professional_id = data['professional_id']
        date = data['date']
        start_time = data['start_time']
        end_time = data['end_time']

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_('Authentication required'))

        # Check if professional exists
        try:
            professional = User.objects.get(
                id=professional_id,
                account_type=User.AccountType.PROFESSIONAL,
                is_active=True
            )
        except User.DoesNotExist:
            raise serializers.ValidationError(_('Professional not found'))

        # Check if user is not the professional
        if request.user.id == professional.id:
            raise serializers.ValidationError(_('You cannot create a booking request with yourself'))

        # Combine date and time
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(
            timezone.datetime.combine(date, start_time), tz
        )
        end_dt = timezone.make_aware(
            timezone.datetime.combine(date, end_time), tz
        )

        # Validate times
        if end_dt <= start_dt:
            raise serializers.ValidationError(_('End time must be after start time'))

        # Check if date is in the past
        if date < timezone.localdate():
            raise serializers.ValidationError(_('You cannot create a booking request in the past'))

        data['professional'] = professional
        data['start_datetime'] = start_dt
        data['end_datetime'] = end_dt

        return data

    def create(self, validated_data):
        request = self.context.get('request')
        professional = validated_data['professional']
        start_dt = validated_data['start_datetime']
        end_dt = validated_data['end_datetime']
        message_text = validated_data.get('message', '')

        # Create event
        event = Event.objects.create(
            name=f"Booking request with {professional.first_name} {professional.last_name}",
            start_datetime=start_dt,
            end_datetime=end_dt,
            location="",
            created_by=request.user,
            currency=request.user.currency if hasattr(request.user, 'currency') and request.user.currency else None,
            is_locked=False,
            is_posted=False,  # Not publicly posted
        )

        # Create thread
        thread, created = OfferThread.objects.get_or_create(
            event=event,
            professional=professional
        )

        # Add initial message if provided
        if message_text:
            OfferMessage.objects.create(
                thread=thread,
                sender=request.user,
                sender_type=OfferMessage.SenderType.CREATOR,
                message=message_text,
            )

        return thread


# ============ Inbox Serializers ============

class InboxFilterSerializer(serializers.Serializer):
    """Serializer for inbox filters"""
    thread = serializers.IntegerField(required=False, min_value=1)
    event = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(
        choices=['pending', 'accepted', 'rejected', 'all'],
        required=False,
        default='all'
    )
    unread_only = serializers.BooleanField(required=False, default=False)
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)


class InboxStatsSerializer(serializers.Serializer):
    """Serializer for inbox statistics"""
    total_threads = serializers.IntegerField()
    unread_threads = serializers.IntegerField()
    pending_offers = serializers.IntegerField()
    accepted_offers = serializers.IntegerField()
    recent_activity = serializers.DateTimeField()