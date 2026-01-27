# accounts/api/serializers_dashboard.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from ..models import (
    Profession, AccountPhoto, ProfessionalPhoto,
    AudioAcapellaCover, VideoAcapellaCover,
    FavoriteProfessional, NewsPost, NewsRead, Language,
    Currency, ExchangeRate, NewsPost
)
from events.models import EventCategory, Event, BusyTime
from .serializers import (
    UserBasicSerializer, ProfessionSerializer, CurrencySerializer,
    LanguageSerializer, ExchangeRateSerializer, AccountPhotoSerializer,
    ProfessionalPhotoSerializer, AudioCoverSerializer, VideoCoverSerializer,
    FavoriteSerializer, NewsPostSerializer
)

User = get_user_model()


# ============ Dashboard Serializers ============

class DashboardHomeSerializer(serializers.Serializer):
    """Serializer for dashboard home data"""
    user = UserBasicSerializer(read_only=True)
    is_professional = serializers.BooleanField()
    normal_photos = AccountPhotoSerializer(many=True, read_only=True)
    professional_photos = ProfessionalPhotoSerializer(many=True, read_only=True)
    audio_covers = AudioCoverSerializer(many=True, read_only=True)
    video_covers = VideoCoverSerializer(many=True, read_only=True)

    media_configs = serializers.SerializerMethodField()

    def get_media_configs(self, obj):
        return {
            'professional': {'kind': 'professional', 'title': 'Professional photos', 'item_type': 'image'},
            'normal': {'kind': 'normal', 'title': 'Normal photos', 'item_type': 'image'},
            'audio': {'kind': 'audio', 'title': 'Audio Acapella Covers', 'item_type': 'audio'},
            'video': {'kind': 'video', 'title': 'Video Acapella Covers', 'item_type': 'video'},
        }


class SwitchProfileSerializer(serializers.ModelSerializer):
    """Serializer for switching profile type"""
    professions = serializers.PrimaryKeyRelatedField(many=True, queryset=Profession.objects.all(), required=False)
    current_account_type = serializers.SerializerMethodField()
    profession_options = serializers.SerializerMethodField()
    selected_profession_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True
    )

    class Meta:
        model = User
        fields = ('account_type', 'professions', 'current_account_type',
                  'profession_options', 'selected_profession_ids')

    def get_current_account_type(self, obj):
        return obj.account_type

    def get_profession_options(self, obj):
        # Build profession tree options
        from ..views_dashboard import _build_profession_tree_options
        options = _build_profession_tree_options()
        return [{'id': id, 'label': label} for id, label in options]

    def update(self, instance, validated_data):
        professions = validated_data.pop('professions', None)
        selected_ids = validated_data.pop('selected_profession_ids', None)

        # Update account type
        instance = super().update(instance, validated_data)

        # Update professions if provided
        if professions is not None:
            instance.professions.set(professions)
        elif selected_ids is not None:
            instance.professions.set(selected_ids)

        return instance


class ProfileEditSerializer(serializers.ModelSerializer):
    """Serializer for profile editing with media uploads"""
    normal_photos = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        write_only=True
    )
    professional_photos = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        write_only=True
    )
    audio_files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        write_only=True
    )
    video_files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        write_only=True
    )

    class Meta:
        model = User
        fields = (
            'first_name', 'last_name', 'nickname', 'phone', 'country',
            'city', 'address', 'gender', 'date_of_birth', 'profile_picture',
            'professional_picture', 'account_type', 'professions',
            'years_of_experience', 'about_me', 'communication_languages',
            'event_languages', 'accepted_event_categories', 'currency',
            'cost_per_hour', 'cost_per_5_hours', 'normal_photos',
            'professional_photos', 'audio_files', 'video_files'
        )

    def update(self, instance, validated_data):
        # Handle file uploads
        normal_photos = validated_data.pop('normal_photos', [])
        professional_photos = validated_data.pop('professional_photos', [])
        audio_files = validated_data.pop('audio_files', [])
        video_files = validated_data.pop('video_files', [])

        # Update user fields
        instance = super().update(instance, validated_data)

        # Save uploaded files
        for photo in normal_photos:
            AccountPhoto.objects.create(user=instance, image=photo)

        for photo in professional_photos:
            ProfessionalPhoto.objects.create(user=instance, image=photo)

        for audio in audio_files:
            AudioAcapellaCover.objects.create(user=instance, audio_file=audio)

        for video in video_files:
            VideoAcapellaCover.objects.create(user=instance, video_file=video)

        return instance


class CurrencyUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating currency"""

    class Meta:
        model = User
        fields = ('currency',)


class LanguageUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating languages"""

    class Meta:
        model = User
        fields = ('communication_languages', 'event_languages')


class FavoriteToggleSerializer(serializers.Serializer):
    """Serializer for toggling favorites"""
    professional_id = serializers.IntegerField(required=True)

    def validate(self, data):
        professional_id = data['professional_id']
        try:
            professional = User.objects.get(
                pk=professional_id,
                is_active=True,
                account_type=User.AccountType.PROFESSIONAL
            )
            data['professional'] = professional
        except User.DoesNotExist:
            raise serializers.ValidationError(_('Professional not found'))

        if professional == self.context['request'].user:
            raise serializers.ValidationError(_('You cannot favorite yourself'))

        return data


class MediaSectionSerializer(serializers.Serializer):
    """Serializer for media section operations"""
    kind = serializers.ChoiceField(choices=['normal', 'professional', 'audio', 'video'])
    files = serializers.ListField(
        child=serializers.FileField(),
        required=False
    )
    delete_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )


# ============ CRUD Serializers ============

class EventCategorySerializer(serializers.ModelSerializer):
    """Serializer for EventCategory CRUD"""
    depth = serializers.SerializerMethodField()

    class Meta:
        model = EventCategory
        fields = ('id', 'name', 'parent', 'path', 'depth')

    def get_depth(self, obj):
        return obj.get_depth()


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for admin user updates"""

    class Meta:
        model = User
        fields = (
            'profile_picture', 'professional_picture', 'first_name', 'last_name',
            'nickname', 'email', 'phone', 'gender', 'account_type', 'is_active',
            'is_staff', 'currency', 'cost_per_hour', 'cost_per_5_hours'
        )


class ProfessionCRUDSerializer(serializers.ModelSerializer):
    """Serializer for Profession CRUD"""

    class Meta:
        model = Profession
        fields = ('id', 'name', 'parent', 'path')


class LanguageCRUDSerializer(serializers.ModelSerializer):
    """Serializer for Language CRUD"""

    class Meta:
        model = Language
        fields = ('id', 'name', 'slug')


class CurrencyCRUDSerializer(serializers.ModelSerializer):
    """Serializer for Currency CRUD"""

    class Meta:
        model = Currency
        fields = ('id', 'name', 'sign')


class ExchangeRateCRUDSerializer(serializers.ModelSerializer):
    """Serializer for ExchangeRate CRUD"""
    from_currency_info = CurrencySerializer(source='from_currency', read_only=True)
    to_currency_info = CurrencySerializer(source='to_currency', read_only=True)

    class Meta:
        model = ExchangeRate
        fields = ('id', 'from_currency', 'to_currency', 'from_currency_info',
                  'to_currency_info', 'rate', 'updated_at')


class NewsPostCRUDSerializer(serializers.ModelSerializer):
    """Serializer for NewsPost CRUD"""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = NewsPost
        fields = ('id', 'title', 'slug', 'excerpt', 'body', 'image', 'image_url',
                  'is_published', 'published_at', 'created_by', 'created_at',
                  'updated_at')
        read_only_fields = ('created_by', 'slug', 'created_at', 'updated_at')

    def get_image_url(self, obj):
        if obj.image and hasattr(obj.image, 'url'):
            return obj.image.url
        return None

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


# ============ List/Filter Serializers ============

class UserFilterSerializer(serializers.Serializer):
    """Serializer for filtering users"""
    q = serializers.CharField(required=False)
    account_type = serializers.ChoiceField(
        choices=User.AccountType.choices,
        required=False
    )
    staff = serializers.ChoiceField(choices=[('1', 'Yes'), ('0', 'No')], required=False)
    active = serializers.ChoiceField(choices=[('1', 'Yes'), ('0', 'No')], required=False)
    page = serializers.IntegerField(min_value=1, required=False, default=1)


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for user list in admin"""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'public_id', 'email', 'full_name', 'nickname', 'phone',
                  'account_type', 'is_active', 'is_staff', 'date_joined')

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"