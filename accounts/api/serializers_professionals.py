# accounts/api/serializers_professionals.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Avg, Min, Max
from ..models import Profession, Language, Currency
from .serializers import UserBasicSerializer, ProfessionSerializer, LanguageSerializer, CurrencySerializer

User = get_user_model()


class ProfessionalListSerializer(serializers.ModelSerializer):
    """Serializer for professional listing with filters"""
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    professions_list = ProfessionSerializer(source='professions', many=True, read_only=True)
    communication_languages_list = LanguageSerializer(source='communication_languages', many=True, read_only=True)
    currency_info = CurrencySerializer(source='currency', read_only=True)
    avg_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'public_id', 'full_name', 'first_name', 'last_name', 'nickname',
            'profile_picture_url', 'account_type', 'professions_list',
            'communication_languages_list', 'years_of_experience', 'about_me',
            'currency_info', 'cost_per_hour', 'cost_per_5_hours', 'country',
            'city', 'gender', 'avg_rating', 'review_count'
        )

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


class FilterOptionsSerializer(serializers.Serializer):
    """Serializer for filter options"""
    professions = serializers.SerializerMethodField()
    languages = serializers.SerializerMethodField()
    price_range = serializers.SerializerMethodField()
    gender_options = serializers.SerializerMethodField()

    def get_professions(self, obj):
        """Build hierarchical profession tree"""
        from ..views import _build_profession_tree_options
        options = _build_profession_tree_options()
        return [{'id': id, 'label': label} for id, label in options]

    def get_languages(self, obj):
        languages = Language.objects.all().order_by('name')
        return LanguageSerializer(languages, many=True).data

    def get_price_range(self, obj):
        """Get min/max price range for sliders"""
        from django.db.models import Min, Max

        bounds = User.objects.filter(
            account_type=User.AccountType.PROFESSIONAL,
            is_active=True,
            cost_per_hour__isnull=False
        ).aggregate(
            min_price=Min('cost_per_hour'),
            max_price=Max('cost_per_hour')
        )

        return {
            'min': bounds['min_price'] or 0,
            'max': bounds['max_price'] or 1000,
        }

    def get_gender_options(self, obj):
        """Get available gender options"""
        return [
            {'value': 'male', 'label': 'Male'},
            {'value': 'female', 'label': 'Female'},
        ]


class FilterSerializer(serializers.Serializer):
    """Serializer for filter parameters"""
    q = serializers.CharField(required=False, allow_blank=True)
    profession = serializers.IntegerField(required=False, min_value=1)
    min_price = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0
    )
    max_price = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0
    )
    languages = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False
    )
    gender = serializers.ChoiceField(
        choices=['male', 'female'],
        required=False
    )
    order_by = serializers.ChoiceField(
        choices=[
            'rating', '-rating',
            'price', '-price',
            'experience', '-experience',
            'name', '-name'
        ],
        required=False,
        default='-rating'
    )
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)