from rest_framework import serializers
from django.utils import timezone
from ..models import Event, EventCategory, BusyTime, OfferThread, OfferMessage


class EventCategorySerializer(serializers.ModelSerializer):
    """Serializer for event categories"""
    depth = serializers.SerializerMethodField()

    class Meta:
        model = EventCategory
        fields = ['id', 'name', 'parent', 'path', 'depth']

    def get_depth(self, obj):
        return obj.get_depth()


class EventCategoryTreeSerializer(serializers.ModelSerializer):
    """Serializer for hierarchical category tree"""
    children = serializers.SerializerMethodField()

    class Meta:
        model = EventCategory
        fields = ['id', 'name', 'children']

    def get_children(self, obj):
        children = obj.children.all()
        return EventCategoryTreeSerializer(children, many=True).data


class EventCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating events"""

    class Meta:
        model = Event
        fields = [
            'name', 'location', 'country', 'city',
            'event_type', 'required_professions',
            'start_datetime', 'end_datetime',
            'currency', 'event_budget', 'advance_payment',
            'is_posted'
        ]

    def validate(self, data):
        # Validate end datetime is after start datetime
        if data.get('end_datetime') and data.get('start_datetime'):
            if data['end_datetime'] <= data['start_datetime']:
                raise serializers.ValidationError({
                    'end_datetime': 'End time must be after start time.'
                })

        # Validate advance payment is not greater than budget
        if (data.get('advance_payment') is not None and
                data.get('event_budget') is not None):
            if data['advance_payment'] > data['event_budget']:
                raise serializers.ValidationError({
                    'advance_payment': 'Advance payment cannot be greater than event budget.'
                })

        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class EventListSerializer(serializers.ModelSerializer):
    """Serializer for listing events"""
    event_type = EventCategorySerializer(read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    created_by_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'name', 'location', 'country', 'city',
            'event_type', 'start_datetime', 'end_datetime',
            'currency', 'event_budget', 'advance_payment',
            'is_locked', 'is_posted', 'created_by_name',
            'created_by_avatar', 'created_at'
        ]

    def get_created_by_avatar(self, obj):
        if hasattr(obj.created_by, 'profile_picture') and obj.created_by.profile_picture:
            return obj.created_by.profile_picture.url
        return None


class EventSerializer(serializers.ModelSerializer):
    """Detailed serializer for events"""
    event_type = EventCategorySerializer(read_only=True)
    required_professions = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    accepted_professional = serializers.SerializerMethodField()
    offer_threads_count = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = '__all__'

    def get_required_professions(self, obj):
        from accounts.serializers import ProfessionSerializer
        return ProfessionSerializer(obj.required_professions.all(), many=True).data

    def get_created_by(self, obj):
        from accounts.serializers import UserProfileSerializer
        return UserProfileSerializer(obj.created_by).data

    def get_accepted_professional(self, obj):
        from accounts.serializers import UserProfileSerializer
        if obj.accepted_professional:
            return UserProfileSerializer(obj.accepted_professional).data
        return None

    def get_offer_threads_count(self, obj):
        return obj.offer_threads.count()


class BusyTimeCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating busy times"""

    class Meta:
        model = BusyTime
        fields = ['start_datetime', 'end_datetime', 'is_all_day', 'note']

    def validate(self, data):
        # Validate end datetime is after start datetime
        if data['end_datetime'] <= data['start_datetime']:
            raise serializers.ValidationError({
                'end_datetime': 'End time must be after start time.'
            })

        # Validate not overlapping with existing busy times
        user = self.context['request'].user
        overlapping = BusyTime.objects.filter(
            user=user,
            start_datetime__lt=data['end_datetime'],
            end_datetime__gt=data['start_datetime']
        )

        if self.instance:
            overlapping = overlapping.exclude(pk=self.instance.pk)

        if overlapping.exists():
            raise serializers.ValidationError({
                'non_field_errors': 'This time overlaps with existing busy time.'
            })

        return data


class BusyTimeSerializer(serializers.ModelSerializer):
    """Serializer for busy times"""
    duration_hours = serializers.SerializerMethodField()

    class Meta:
        model = BusyTime
        fields = ['id', 'start_datetime', 'end_datetime',
                  'is_all_day', 'note', 'duration_hours', 'created_at']

    def get_duration_hours(self, obj):
        duration = obj.end_datetime - obj.start_datetime
        return round(duration.total_seconds() / 3600, 2)


class CalendarEventSerializer(serializers.ModelSerializer):
    """Serializer for calendar events"""
    event_type = serializers.CharField(source='event_type.name', allow_null=True)
    is_creator = serializers.SerializerMethodField()
    is_booked = serializers.SerializerMethodField()
    time_range = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = ['id', 'name', 'event_type', 'start_datetime',
                  'end_datetime', 'location', 'is_locked',
                  'is_creator', 'is_booked', 'time_range']

    def get_is_creator(self, obj):
        return obj.created_by == self.context['request'].user

    def get_is_booked(self, obj):
        user = self.context['request'].user
        return obj.is_locked and obj.accepted_thread.professional == user

    def get_time_range(self, obj):
        start_local = timezone.localtime(obj.start_datetime)
        end_local = timezone.localtime(obj.end_datetime)

        if start_local.date() == end_local.date():
            return f"{start_local.strftime('%H:%M')} - {end_local.strftime('%H:%M')}"
        else:
            return f"{start_local.strftime('%b %d, %H:%M')} - {end_local.strftime('%b %d, %H:%M')}"


class CalendarMonthSerializer(serializers.Serializer):
    """Serializer for calendar month view"""
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    month_name = serializers.CharField()
    prev_year = serializers.IntegerField()
    prev_month = serializers.IntegerField()
    next_year = serializers.IntegerField()
    next_month = serializers.IntegerField()
    today = serializers.DateField()
    weeks = serializers.ListField(
        child=serializers.ListField(child=serializers.DateField())
    )


class OfferThreadSerializer(serializers.ModelSerializer):
    """Serializer for offer threads"""
    event = EventListSerializer(read_only=True)
    professional = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = OfferThread
        fields = ['id', 'event', 'professional', 'last_message',
                  'unread_count', 'created_at']

    def get_professional(self, obj):
        from accounts.serializers import UserProfileSerializer
        return UserProfileSerializer(obj.professional).data

    def get_last_message(self, obj):
        last_message = obj.messages.last()
        if last_message:
            return {
                'message': last_message.message[:100] + '...' if len(
                    last_message.message) > 100 else last_message.message,
                'sender_type': last_message.sender_type,
                'created_at': last_message.created_at
            }
        return None

    def get_unread_count(self, obj):
        user = self.context['request'].user
        # Messages where user is not the sender and status is pending
        return obj.messages.exclude(sender=user).filter(status='pending').count()


class OfferMessageSerializer(serializers.ModelSerializer):
    """Serializer for offer messages"""
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)
    sender_avatar = serializers.SerializerMethodField()
    is_sent_by_me = serializers.SerializerMethodField()

    class Meta:
        model = OfferMessage
        fields = ['id', 'thread', 'sender', 'sender_name', 'sender_avatar',
                  'sender_type', 'message', 'proposed_amount',
                  'proposed_currency', 'event_currency', 'conversion_rate',
                  'converted_amount', 'status', 'created_at', 'is_sent_by_me']

    def get_sender_avatar(self, obj):
        if hasattr(obj.sender, 'profile_picture') and obj.sender.profile_picture:
            return obj.sender.profile_picture.url
        return None

    def get_is_sent_by_me(self, obj):
        return obj.sender == self.context['request'].user