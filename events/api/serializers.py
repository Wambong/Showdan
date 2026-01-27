# events/api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models import Event, EventCategory, OfferThread, OfferMessage, BusyTime
from accounts.models import Profession, Currency
from accounts.api.serializers import (
    UserBasicSerializer, ProfessionSerializer, CurrencySerializer
)

User = get_user_model()


# ============ Event Category Serializers ============

class EventCategorySerializer(serializers.ModelSerializer):
    """Serializer for EventCategory model"""
    depth = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = EventCategory
        fields = ('id', 'name', 'parent', 'path', 'depth', 'children_count')

    def get_depth(self, obj):
        return obj.get_depth()

    def get_children_count(self, obj):
        return obj.children.count()


class EventCategoryTreeSerializer(serializers.ModelSerializer):
    """Serializer for hierarchical event category tree"""
    children = serializers.SerializerMethodField()

    class Meta:
        model = EventCategory
        fields = ('id', 'name', 'path', 'children')

    def get_children(self, obj):
        children = obj.children.all().order_by('name')
        return EventCategoryTreeSerializer(children, many=True).data


# ============ Event Serializers ============

class EventListSerializer(serializers.ModelSerializer):
    """Serializer for listing events"""
    created_by_info = UserBasicSerializer(source='created_by', read_only=True)
    event_type_info = EventCategorySerializer(source='event_type', read_only=True)
    currency_info = CurrencySerializer(source='currency', read_only=True)
    required_professions_info = ProfessionSerializer(source='required_professions', many=True, read_only=True)
    accepted_professional_info = UserBasicSerializer(source='accepted_professional', read_only=True)

    # Calculated fields
    offers_received_count = serializers.SerializerMethodField()
    time_status = serializers.SerializerMethodField()
    is_upcoming = serializers.SerializerMethodField()
    is_creator = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            'id', 'name', 'location', 'country', 'city',
            'start_datetime', 'end_datetime',
            'event_type', 'event_type_info',
            'required_professions', 'required_professions_info',
            'currency', 'currency_info',
            'event_budget', 'advance_payment',
            'is_locked', 'is_posted',
            'created_by', 'created_by_info',
            'accepted_thread', 'accepted_professional', 'accepted_professional_info',
            'created_at',
            'offers_received_count', 'time_status', 'is_upcoming', 'is_creator'
        )

    def get_offers_received_count(self, obj):
        return obj.offer_threads.count()

    def get_time_status(self, obj):
        now = timezone.now()
        if obj.end_datetime < now:
            return 'past'
        elif obj.start_datetime > now:
            return 'upcoming'
        else:
            return 'ongoing'

    def get_is_upcoming(self, obj):
        return obj.end_datetime >= timezone.now()

    def get_is_creator(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.created_by_id == request.user.id
        return False


class EventDetailSerializer(EventListSerializer):
    """Serializer for detailed event view"""
    creator_full_info = UserBasicSerializer(source='created_by', read_only=True)

    class Meta(EventListSerializer.Meta):
        fields = EventListSerializer.Meta.fields + (
            'creator_full_info',
        )


class EventCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating events"""

    class Meta:
        model = Event
        fields = (
            'name', 'location', 'country', 'city',
            'start_datetime', 'end_datetime',
            'event_type', 'required_professions',
            'currency', 'event_budget', 'advance_payment'
        )

    def validate(self, data):
        # Ensure end time is after start time
        if data.get('end_datetime') and data.get('start_datetime'):
            if data['end_datetime'] <= data['start_datetime']:
                raise serializers.ValidationError(
                    {'end_datetime': 'End time must be after start time.'}
                )

        # Ensure advance payment is not greater than budget
        budget = data.get('event_budget')
        advance = data.get('advance_payment')
        if budget is not None and advance is not None and advance > budget:
            raise serializers.ValidationError(
                {'advance_payment': 'Advance payment cannot be greater than event budget.'}
            )

        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
            validated_data['is_posted'] = True

            # Auto-fill country/city from user if not provided
            if not validated_data.get('country') and hasattr(request.user, 'country'):
                validated_data['country'] = request.user.country
            if not validated_data.get('city') and hasattr(request.user, 'city'):
                validated_data['city'] = request.user.city

            # Auto-set currency from user if not provided
            if not validated_data.get('currency') and hasattr(request.user, 'currency'):
                validated_data['currency'] = request.user.currency

        return super().create(validated_data)


# ============ Offer Thread Serializers ============

class OfferThreadSerializer(serializers.ModelSerializer):
    """Serializer for offer threads"""
    event_info = EventListSerializer(source='event', read_only=True)
    professional_info = UserBasicSerializer(source='professional', read_only=True)
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    last_message_time = serializers.SerializerMethodField()

    class Meta:
        model = OfferThread
        fields = (
            'id', 'event', 'event_info', 'professional', 'professional_info',
            'created_at', 'message_count', 'last_message', 'last_message_time'
        )

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_last_message(self, obj):
        last_message = obj.messages.last()
        if last_message:
            return last_message.message[:100]  # First 100 chars
        return None

    def get_last_message_time(self, obj):
        last_message = obj.messages.last()
        if last_message:
            return last_message.created_at
        return None


class OfferMessageSerializer(serializers.ModelSerializer):
    """Serializer for offer messages"""
    sender_info = UserBasicSerializer(source='sender', read_only=True)
    thread_info = OfferThreadSerializer(source='thread', read_only=True)
    proposed_currency_info = CurrencySerializer(source='proposed_currency', read_only=True)
    event_currency_info = CurrencySerializer(source='event_currency', read_only=True)

    class Meta:
        model = OfferMessage
        fields = (
            'id', 'thread', 'thread_info', 'sender', 'sender_info',
            'sender_type', 'message', 'proposed_amount', 'proposed_currency',
            'proposed_currency_info', 'event_currency', 'event_currency_info',
            'conversion_rate', 'converted_amount', 'status', 'created_at'
        )
        read_only_fields = ('sender', 'created_at')

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['sender'] = request.user

            # Determine sender type
            if request.user.account_type == User.AccountType.PROFESSIONAL:
                validated_data['sender_type'] = 'professional'
            else:
                validated_data['sender_type'] = 'creator'

        return super().create(validated_data)


class OfferMessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating offer messages"""

    class Meta:
        model = OfferMessage
        fields = ('thread', 'message', 'proposed_amount', 'proposed_currency')


# ============ Busy Time Serializers ============

class BusyTimeSerializer(serializers.ModelSerializer):
    """Serializer for busy times"""

    class Meta:
        model = BusyTime
        fields = ('id', 'user', 'start_datetime', 'end_datetime',
                  'is_all_day', 'note', 'created_at')
        read_only_fields = ('user', 'created_at')

    def validate(self, data):
        # Ensure end time is after start time
        if data.get('end_datetime') and data.get('start_datetime'):
            if data['end_datetime'] <= data['start_datetime']:
                raise serializers.ValidationError(
                    {'end_datetime': 'End time must be after start time.'}
                )
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['user'] = request.user
        return super().create(validated_data)


# ============ Filter Serializers ============

class EventFilterSerializer(serializers.Serializer):
    """Serializer for event filter parameters"""
    show = serializers.ChoiceField(
        choices=['upcoming', 'past', 'all'],
        required=False,
        default='upcoming'
    )
    q = serializers.CharField(required=False, allow_blank=True)
    category = serializers.IntegerField(required=False, min_value=1)
    profession = serializers.IntegerField(required=False, min_value=1)
    country = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)
    near_me = serializers.BooleanField(required=False, default=False)
    min_budget = serializers.DecimalField(
        required=False, max_digits=12, decimal_places=2, min_value=0
    )
    max_budget = serializers.DecimalField(
        required=False, max_digits=12, decimal_places=2, min_value=0
    )
    order_by = serializers.ChoiceField(
        choices=['start_datetime', '-start_datetime', 'created_at', '-created_at', 'name'],
        required=False,
        default='start_datetime'
    )
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)


class FilterOptionsSerializer(serializers.Serializer):
    """Serializer for filter options"""
    categories = serializers.SerializerMethodField()
    profession_options = serializers.SerializerMethodField()
    budget_range = serializers.SerializerMethodField()

    def get_categories(self, obj):
        categories = EventCategory.objects.all().order_by('path')
        return EventCategorySerializer(categories, many=True).data

    def get_profession_options(self, obj):
        """Build hierarchical profession tree"""
        from ..views import _build_profession_tree_options
        options = _build_profession_tree_options()
        return [{'id': id, 'label': label} for id, label in options]

    def get_budget_range(self, obj):
        """Get min/max budget range"""
        from django.db.models import Min, Max

        bounds = Event.objects.filter(
            is_posted=True,
            event_budget__isnull=False
        ).aggregate(
            min_budget=Min('event_budget'),
            max_budget=Max('event_budget')
        )

        return {
            'min': bounds['min_budget'] or 0,
            'max': bounds['max_budget'] or 10000,
        }