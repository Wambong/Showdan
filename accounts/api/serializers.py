from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ..models import (
    Profession, AccountPhoto, ProfessionalPhoto,
    AudioAcapellaCover, VideoAcapellaCover, Review,
    FavoriteProfessional, NewsPost, NewsRead, Language, Currency,
    ExchangeRate
)
from events.models import Event, BusyTime, OfferThread, OfferMessage, EventCategory
import calendar
from datetime import date, timedelta

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    """Minimal user info for public profiles"""
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'public_id', 'first_name', 'last_name', 'full_name',
                  'profile_picture_url', 'account_type', 'nickname')
        read_only_fields = fields

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_profile_picture_url(self, obj):
        if obj.profile_picture and hasattr(obj.profile_picture, 'url'):
            return obj.profile_picture.url
        return None


class UserProfileSerializer(serializers.ModelSerializer):
    """Full user profile for authenticated users"""
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    professional_picture_url = serializers.SerializerMethodField()
    professions = serializers.PrimaryKeyRelatedField(many=True, queryset=Profession.objects.all())
    communication_languages = serializers.PrimaryKeyRelatedField(many=True, queryset=Language.objects.all())
    event_languages = serializers.PrimaryKeyRelatedField(many=True, queryset=Language.objects.all())
    accepted_event_categories = serializers.PrimaryKeyRelatedField(many=True, queryset=EventCategory.objects.all())

    class Meta:
        model = User
        fields = (
            'id', 'public_id', 'email', 'first_name', 'last_name', 'full_name',
            'nickname', 'phone', 'country', 'city', 'address', 'gender',
            'date_of_birth', 'profile_picture', 'profile_picture_url',
            'professional_picture', 'professional_picture_url',
            'account_type', 'professions', 'years_of_experience',
            'about_me', 'communication_languages', 'event_languages',
            'accepted_event_categories', 'currency', 'cost_per_hour',
            'cost_per_5_hours', 'date_joined', 'is_active'
        )
        read_only_fields = ('email', 'date_joined', 'is_active')

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_profile_picture_url(self, obj):
        if obj.profile_picture and hasattr(obj.profile_picture, 'url'):
            return obj.profile_picture.url
        return None

    def get_professional_picture_url(self, obj):
        if obj.professional_picture and hasattr(obj.professional_picture, 'url'):
            return obj.professional_picture.url
        return None


class ProfessionSerializer(serializers.ModelSerializer):
    """Serializer for Profession model"""
    depth_level = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Profession
        fields = ('id', 'name', 'parent', 'path', 'depth_level', 'children')

    def get_depth_level(self, obj):
        return obj.get_depth()

    def get_children(self, obj):
        children = obj.children.all()
        return ProfessionSerializer(children, many=True).data if children else []


class AccountPhotoSerializer(serializers.ModelSerializer):
    """Serializer for normal photos"""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = AccountPhoto
        fields = ('id', 'user', 'image', 'image_url', 'uploaded_at')
        read_only_fields = ('user', 'uploaded_at')

    def get_image_url(self, obj):
        if obj.image and hasattr(obj.image, 'url'):
            return obj.image.url
        return None


class ProfessionalPhotoSerializer(serializers.ModelSerializer):
    """Serializer for professional photos"""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProfessionalPhoto
        fields = ('id', 'user', 'image', 'image_url', 'uploaded_at')
        read_only_fields = ('user', 'uploaded_at')

    def get_image_url(self, obj):
        if obj.image and hasattr(obj.image, 'url'):
            return obj.image.url
        return None


class AudioCoverSerializer(serializers.ModelSerializer):
    """Serializer for audio acapella covers"""
    audio_url = serializers.SerializerMethodField()

    class Meta:
        model = AudioAcapellaCover
        fields = ('id', 'user', 'title', 'audio_file', 'audio_url', 'uploaded_at')
        read_only_fields = ('user', 'uploaded_at')

    def get_audio_url(self, obj):
        if obj.audio_file and hasattr(obj.audio_file, 'url'):
            return obj.audio_file.url
        return None


class VideoCoverSerializer(serializers.ModelSerializer):
    """Serializer for video acapella covers"""
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = VideoAcapellaCover
        fields = ('id', 'user', 'title', 'video_file', 'video_url', 'uploaded_at')
        read_only_fields = ('user', 'uploaded_at')

    def get_video_url(self, obj):
        if obj.video_file and hasattr(obj.video_file, 'url'):
            return obj.video_file.url
        return None


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for reviews"""
    reviewer_info = UserBasicSerializer(source='reviewer', read_only=True)
    professional_info = UserBasicSerializer(source='professional', read_only=True)

    class Meta:
        model = Review
        fields = ('id', 'professional', 'reviewer', 'reviewer_info',
                  'professional_info', 'rating', 'comment', 'created_at')
        read_only_fields = ('reviewer', 'professional', 'created_at')

    def validate(self, data):
        """Ensure user cannot review themselves"""
        request = self.context.get('request')
        professional = self.instance.professional if self.instance else data.get('professional')

        if request and request.user == professional:
            raise serializers.ValidationError(_("You cannot review your own profile."))

        return data


class FavoriteProfessionalSerializer(serializers.ModelSerializer):
    """Serializer for favorite professionals"""
    professional_info = UserBasicSerializer(source='professional', read_only=True)

    class Meta:
        model = FavoriteProfessional
        fields = ('id', 'user', 'professional', 'professional_info', 'created_at')
        read_only_fields = ('user', 'created_at')


# ============ ADD THIS MISSING SERIALIZER ============
class FavoriteSerializer(serializers.ModelSerializer):
    """Serializer for favorite professionals"""
    professional_info = UserBasicSerializer(source='professional', read_only=True)

    class Meta:
        model = FavoriteProfessional
        fields = ('id', 'user', 'professional', 'professional_info', 'created_at')
        read_only_fields = ('user', 'created_at')


# ============ END ADDITION ============
class NewsPostSerializer(serializers.ModelSerializer):
    """Serializer for news posts"""
    image_url = serializers.SerializerMethodField()
    read_status = serializers.SerializerMethodField()

    class Meta:
        model = NewsPost
        fields = ('id', 'title', 'slug', 'excerpt', 'body', 'image',
                  'image_url', 'is_published', 'published_at',
                  'created_by', 'created_at', 'updated_at', 'read_status')
        read_only_fields = ('created_by', 'slug', 'created_at', 'updated_at')

    def get_image_url(self, obj):
        if obj.image and hasattr(obj.image, 'url'):
            return obj.image.url
        return None

    def get_read_status(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return NewsRead.objects.filter(
                user=request.user, post=obj
            ).exists()
        return False


class LanguageSerializer(serializers.ModelSerializer):
    """Serializer for languages"""

    class Meta:
        model = Language
        fields = ('id', 'name', 'slug')


class CurrencySerializer(serializers.ModelSerializer):
    """Serializer for currencies"""

    class Meta:
        model = Currency
        fields = ('id', 'name', 'sign')


class ExchangeRateSerializer(serializers.ModelSerializer):
    """Serializer for exchange rates"""
    from_currency_info = CurrencySerializer(source='from_currency', read_only=True)
    to_currency_info = CurrencySerializer(source='to_currency', read_only=True)

    class Meta:
        model = ExchangeRate
        fields = ('id', 'from_currency', 'to_currency', 'from_currency_info',
                  'to_currency_info', 'rate', 'updated_at')


class EventSerializer(serializers.ModelSerializer):
    """Serializer for events"""
    created_by_info = UserBasicSerializer(source='created_by', read_only=True)
    accepted_professional_info = UserBasicSerializer(source='accepted_professional', read_only=True)

    class Meta:
        model = Event
        fields = ('id', 'name', 'location', 'country', 'city', 'event_type',
                  'required_professions', 'start_datetime', 'end_datetime',
                  'currency', 'event_budget', 'advance_payment',
                  'is_locked', 'is_posted', 'accepted_thread',
                  'accepted_professional', 'accepted_professional_info',
                  'created_by', 'created_by_info', 'created_at')
        read_only_fields = ('created_by', 'accepted_thread', 'accepted_professional', 'created_at')


class BusyTimeSerializer(serializers.ModelSerializer):
    """Serializer for busy times"""

    class Meta:
        model = BusyTime
        fields = ('id', 'user', 'start_datetime', 'end_datetime',
                  'is_all_day', 'note', 'created_at')
        read_only_fields = ('user', 'created_at')


class OfferThreadSerializer(serializers.ModelSerializer):
    """Serializer for offer threads"""
    professional_info = UserBasicSerializer(source='professional', read_only=True)
    event_info = EventSerializer(source='event', read_only=True)

    class Meta:
        model = OfferThread
        fields = ('id', 'event', 'professional', 'professional_info',
                  'event_info', 'created_at')
        read_only_fields = ('created_at',)


class OfferMessageSerializer(serializers.ModelSerializer):
    """Serializer for offer messages"""
    sender_info = UserBasicSerializer(source='sender', read_only=True)

    class Meta:
        model = OfferMessage
        fields = ('id', 'thread', 'sender', 'sender_info', 'sender_type',
                  'message', 'proposed_amount', 'proposed_currency',
                  'event_currency', 'conversion_rate', 'converted_amount',
                  'status', 'created_at')
        read_only_fields = ('sender', 'created_at')


class PublicProfileSerializer(serializers.ModelSerializer):
    """Serializer for public professional profiles"""
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    professions_list = ProfessionSerializer(source='professions', many=True, read_only=True)
    currency_info = CurrencySerializer(source='currency', read_only=True)

    # Stats
    avg_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    # Media counts
    normal_photos_count = serializers.SerializerMethodField()
    professional_photos_count = serializers.SerializerMethodField()
    audio_covers_count = serializers.SerializerMethodField()
    video_covers_count = serializers.SerializerMethodField()

    # Favorite status
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'public_id', 'full_name', 'first_name', 'last_name',
                  'nickname', 'profile_picture_url', 'account_type',
                  'professions_list', 'years_of_experience', 'about_me',
                  'currency_info', 'cost_per_hour', 'cost_per_5_hours',
                  'country', 'city', 'avg_rating', 'review_count',
                  'normal_photos_count', 'professional_photos_count',
                  'audio_covers_count', 'video_covers_count',
                  'is_favorite')

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_profile_picture_url(self, obj):
        if obj.profile_picture and hasattr(obj.profile_picture, 'url'):
            return obj.profile_picture.url
        return None

    def get_avg_rating(self, obj):
        from django.db.models import Avg
        avg = obj.reviews_received.aggregate(avg=Avg('rating'))['avg']
        return avg or 0

    def get_review_count(self, obj):
        return obj.reviews_received.count()

    def get_normal_photos_count(self, obj):
        return obj.normal_photos.count()

    def get_professional_photos_count(self, obj):
        return obj.professional_photos.count()

    def get_audio_covers_count(self, obj):
        return obj.audio_acapella_covers.count()

    def get_video_covers_count(self, obj):
        return obj.video_acapella_covers.count()

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return FavoriteProfessional.objects.filter(
                user=request.user, professional=obj
            ).exists()
        return False


class CalendarDaySerializer(serializers.Serializer):
    """Serializer for calendar day data"""
    date = serializers.DateField()
    booked_events = serializers.ListField(child=serializers.DictField())
    busy_times = serializers.ListField(child=serializers.DictField())


class CalendarMonthSerializer(serializers.Serializer):
    """Serializer for calendar month data"""
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    month_name = serializers.CharField()
    weeks = serializers.ListField(child=serializers.ListField(child=serializers.DateField()))
    days = CalendarDaySerializer(many=True)
    prev_year = serializers.IntegerField()
    prev_month = serializers.IntegerField()
    next_year = serializers.IntegerField()
    next_month = serializers.IntegerField()


class RegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone',
                  'country', 'city', 'date_of_birth', 'account_type',
                  'password', 'password2')

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError(_("Passwords do not match"))
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        from django.contrib.auth import authenticate
        user = authenticate(email=data['email'], password=data['password'])

        if not user:
            raise serializers.ValidationError(_("Invalid credentials"))

        if not user.is_active:
            raise serializers.ValidationError(_("Account is disabled"))

        data['user'] = user
        return data


class FileUploadSerializer(serializers.Serializer):
    """Generic serializer for file uploads"""
    files = serializers.ListField(
        child=serializers.FileField(),
        required=True
    )
    titles = serializers.ListField(
        child=serializers.CharField(max_length=150, required=False),
        required=False
    )