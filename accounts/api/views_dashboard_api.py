# accounts/api/views_dashboard_api.py
from rest_framework import viewsets, status, generics, mixins
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
import json
from django.utils import timezone

from ..models import (
    Profession, AccountPhoto, ProfessionalPhoto,
    AudioAcapellaCover, VideoAcapellaCover, Review,
    FavoriteProfessional, NewsPost, NewsRead, Language,
    Currency, ExchangeRate
)
from events.models import EventCategory
from .serializers_dashboard import *

User = get_user_model()


# ==================== Dashboard Views ====================

class DashboardHomeView(APIView):
    """
    Get dashboard home data

    GET /api/v1/dashboard/home/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_pro = user.account_type == User.AccountType.PROFESSIONAL

        normal_photos = AccountPhoto.objects.filter(user=user).order_by("-id")
        professional_photos = ProfessionalPhoto.objects.filter(user=user).order_by("-id")
        audio_covers = AudioAcapellaCover.objects.filter(user=user).order_by("-id")
        video_covers = VideoAcapellaCover.objects.filter(user=user).order_by("-id")

        data = {
            'user': user,
            'is_professional': is_pro,
            'normal_photos': normal_photos,
            'professional_photos': professional_photos,
            'audio_covers': audio_covers,
            'video_covers': video_covers,
        }

        serializer = DashboardHomeSerializer(data, context={'request': request})
        return Response(serializer.data)


class SwitchProfileView(APIView):
    """
    Switch between personal and professional profile

    GET /api/v1/dashboard/switch-profile/ - Get current profile info
    POST /api/v1/dashboard/switch-profile/ - Switch profile type
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get current profile and profession options"""
        from ..views_dashboard import _build_profession_tree_options

        user = request.user
        profession_options = _build_profession_tree_options()
        selected_prof_ids = list(user.professions.values_list('id', flat=True))

        data = {
            'user': user,
            'profession_options': profession_options,
            'selected_profession_ids': selected_prof_ids,
        }

        return Response({
            'current_account_type': user.account_type,
            'profession_options': [{'id': id, 'label': label} for id, label in profession_options],
            'selected_profession_ids': selected_prof_ids,
        })

    def post(self, request):
        """Switch profile type"""
        user = request.user
        target_type = request.data.get('account_type')
        profession_ids = request.data.get('professions', [])
        selected_ids = request.data.get('selected_profession_ids', [])

        if target_type not in [User.AccountType.PERSONAL, User.AccountType.PROFESSIONAL]:
            return Response(
                {'error': _('Invalid account type')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Switching to personal
        if target_type == User.AccountType.PERSONAL:
            user.account_type = User.AccountType.PERSONAL
            user.save(update_fields=['account_type'])
            user.professions.clear()

            return Response({
                'message': _('Switched to Personal profile'),
                'account_type': user.account_type,
            })

        # Switching to professional
        if target_type == User.AccountType.PROFESSIONAL:
            # Use either professions or selected_profession_ids
            if profession_ids:
                ids_to_set = profession_ids
            elif selected_ids:
                ids_to_set = selected_ids
            else:
                return Response(
                    {'error': _('Please select at least one profession')},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate profession IDs
            valid_professions = Profession.objects.filter(id__in=ids_to_set)
            if not valid_professions.exists():
                return Response(
                    {'error': _('Invalid profession IDs')},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.account_type = User.AccountType.PROFESSIONAL
            user.save(update_fields=['account_type'])
            user.professions.set(valid_professions)

            return Response({
                'message': _('Switched to Professional profile'),
                'account_type': user.account_type,
                'professions': list(user.professions.values_list('id', flat=True)),
            })


class ProfileEditView(APIView):
    """
    Edit user profile with media uploads

    GET /api/v1/dashboard/profile/edit/ - Get current profile
    PUT /api/v1/dashboard/profile/edit/ - Update profile
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        """Get current profile data"""
        user = request.user
        serializer = ProfileEditSerializer(user, context={'request': request})
        return Response(serializer.data)

    def put(self, request):
        """Update profile with file uploads"""
        user = request.user

        # Handle file uploads separately
        data = request.data.copy()

        # Process file fields
        if 'normal_photos' in request.FILES:
            data['normal_photos'] = request.FILES.getlist('normal_photos')
        if 'professional_photos' in request.FILES:
            data['professional_photos'] = request.FILES.getlist('professional_photos')
        if 'audio_files' in request.FILES:
            data['audio_files'] = request.FILES.getlist('audio_files')
        if 'video_files' in request.FILES:
            data['video_files'] = request.FILES.getlist('video_files')

        serializer = ProfileEditSerializer(
            user,
            data=data,
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': _('Profile updated successfully'),
                'user': ProfileEditSerializer(user, context={'request': request}).data
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FavoritesView(generics.ListAPIView):
    """
    List user's favorite professionals

    GET /api/v1/dashboard/favorites/
    """
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination

    def get_queryset(self):
        return FavoriteProfessional.objects.filter(
            user=self.request.user
        ).select_related('professional').order_by('-created_at')


class FavoriteToggleView(APIView):
    """
    Toggle favorite status for a professional

    POST /api/v1/dashboard/favorites/toggle/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FavoriteToggleSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            professional = serializer.validated_data['professional']

            # Toggle favorite
            favorite = FavoriteProfessional.objects.filter(
                user=request.user,
                professional=professional
            ).first()

            if favorite:
                favorite.delete()
                is_favorite = False
                message = _('Removed from favorites')
            else:
                FavoriteProfessional.objects.create(
                    user=request.user,
                    professional=professional
                )
                is_favorite = True
                message = _('Added to favorites')

            return Response({
                'message': message,
                'is_favorite': is_favorite,
                'professional_id': professional.id,
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrencyView(APIView):
    """
    Update user's currency preference

    GET /api/v1/dashboard/currency/ - Get current currency
    PUT /api/v1/dashboard/currency/ - Update currency
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get current currency and available currencies"""
        user = request.user
        currencies = Currency.objects.all().order_by('name')

        return Response({
            'current_currency': CurrencySerializer(user.currency).data if user.currency else None,
            'available_currencies': CurrencySerializer(currencies, many=True).data,
        })

    def put(self, request):
        """Update currency"""
        user = request.user
        currency_id = request.data.get('currency')

        if not currency_id:
            return Response(
                {'error': _('Currency ID is required')},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            currency = Currency.objects.get(id=currency_id)
        except Currency.DoesNotExist:
            return Response(
                {'error': _('Invalid currency')},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.currency = currency
        user.save(update_fields=['currency'])

        return Response({
            'message': _('Currency updated'),
            'currency': CurrencySerializer(currency).data,
        })


class LanguageView(APIView):
    """
    Update user's language preferences

    GET /api/v1/dashboard/languages/ - Get current languages
    PUT /api/v1/dashboard/languages/ - Update languages
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get current languages and available languages"""
        user = request.user
        languages = Language.objects.all().order_by('name')

        return Response({
            'communication_languages': LanguageSerializer(
                user.communication_languages.all(), many=True
            ).data,
            'event_languages': LanguageSerializer(
                user.event_languages.all(), many=True
            ).data,
            'available_languages': LanguageSerializer(languages, many=True).data,
        })

    def put(self, request):
        """Update languages"""
        user = request.user
        communication_ids = request.data.get('communication_languages', [])
        event_ids = request.data.get('event_languages', [])

        try:
            # Validate language IDs
            communication_langs = Language.objects.filter(id__in=communication_ids)
            event_langs = Language.objects.filter(id__in=event_ids)

            user.communication_languages.set(communication_langs)
            user.event_languages.set(event_langs)

            return Response({
                'message': _('Languages updated'),
                'communication_languages': LanguageSerializer(communication_langs, many=True).data,
                'event_languages': LanguageSerializer(event_langs, many=True).data,
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class MediaSectionView(APIView):
    """
    Manage media sections (normal/professional photos, audio/video covers)

    GET /api/v1/dashboard/media/{kind}/ - Get media items
    POST /api/v1/dashboard/media/{kind}/ - Upload/delete media
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, kind):
        """Get media items for a specific kind"""
        if kind not in ['normal', 'professional', 'audio', 'video']:
            return Response(
                {'error': _('Invalid media kind')},
                status=status.HTTP_400_BAD_REQUEST
            )

        if kind == 'normal':
            queryset = AccountPhoto.objects.filter(user=request.user)
            serializer_class = AccountPhotoSerializer
        elif kind == 'professional':
            queryset = ProfessionalPhoto.objects.filter(user=request.user)
            serializer_class = ProfessionalPhotoSerializer
        elif kind == 'audio':
            queryset = AudioAcapellaCover.objects.filter(user=request.user)
            serializer_class = AudioCoverSerializer
        elif kind == 'video':
            queryset = VideoAcapellaCover.objects.filter(user=request.user)
            serializer_class = VideoCoverSerializer

        items = queryset.order_by('-uploaded_at')
        serializer = serializer_class(items, many=True, context={'request': request})

        return Response({
            'kind': kind,
            'items': serializer.data,
            'title': self._get_title(kind),
        })

    def post(self, request, kind):
        """Upload new files and/or delete existing ones"""
        if kind not in ['normal', 'professional', 'audio', 'video']:
            return Response(
                {'error': _('Invalid media kind')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Delete selected items
        delete_ids = request.data.getlist('delete_ids', [])
        if delete_ids:
            delete_ids = [int(id) for id in delete_ids if str(id).isdigit()]
            if kind == 'normal':
                AccountPhoto.objects.filter(user=request.user, id__in=delete_ids).delete()
            elif kind == 'professional':
                ProfessionalPhoto.objects.filter(user=request.user, id__in=delete_ids).delete()
            elif kind == 'audio':
                AudioAcapellaCover.objects.filter(user=request.user, id__in=delete_ids).delete()
            elif kind == 'video':
                VideoAcapellaCover.objects.filter(user=request.user, id__in=delete_ids).delete()

        # Upload new files
        uploaded_files = []
        if kind == 'normal':
            files = request.FILES.getlist('files', [])
            for f in files:
                photo = AccountPhoto.objects.create(user=request.user, image=f)
                uploaded_files.append({
                    'id': photo.id,
                    'url': photo.image.url if photo.image else None,
                })
        elif kind == 'professional':
            files = request.FILES.getlist('files', [])
            for f in files:
                photo = ProfessionalPhoto.objects.create(user=request.user, image=f)
                uploaded_files.append({
                    'id': photo.id,
                    'url': photo.image.url if photo.image else None,
                })
        elif kind == 'audio':
            files = request.FILES.getlist('files', [])
            titles = request.data.getlist('titles', [])
            for i, f in enumerate(files):
                title = titles[i] if i < len(titles) else ''
                audio = AudioAcapellaCover.objects.create(
                    user=request.user,
                    title=title,
                    audio_file=f
                )
                uploaded_files.append({
                    'id': audio.id,
                    'title': audio.title,
                    'url': audio.audio_file.url if audio.audio_file else None,
                })
        elif kind == 'video':
            files = request.FILES.getlist('files', [])
            titles = request.data.getlist('titles', [])
            for i, f in enumerate(files):
                title = titles[i] if i < len(titles) else ''
                video = VideoAcapellaCover.objects.create(
                    user=request.user,
                    title=title,
                    video_file=f
                )
                uploaded_files.append({
                    'id': video.id,
                    'title': video.title,
                    'url': video.video_file.url if video.video_file else None,
                })

        return Response({
            'message': _('Media updated successfully'),
            'deleted_count': len(delete_ids),
            'uploaded_count': len(uploaded_files),
            'uploaded_files': uploaded_files,
        })

    def _get_title(self, kind):
        titles = {
            'normal': 'Normal Photos',
            'professional': 'Professional Photos',
            'audio': 'Audio Acapella Covers',
            'video': 'Video Acapella Covers',
        }
        return titles.get(kind, kind.capitalize())


class TermsView(APIView):
    """
    Get terms and conditions (placeholder)

    GET /api/v1/dashboard/terms/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'title': 'Terms and Conditions',
            'content': 'This is a placeholder for terms and conditions.',
            'last_updated': '2024-01-01',
        })


class SupportView(APIView):
    """
    Get support information (placeholder)

    GET /api/v1/dashboard/support/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'title': 'Support',
            'contact_email': 'support@example.com',
            'contact_phone': '+1-234-567-8900',
            'hours': 'Monday-Friday, 9AM-5PM',
            'faq_url': 'https://example.com/faq',
        })


# ==================== News Views ====================

class NewsListView(generics.ListAPIView):
    """
    List published news posts

    GET /api/v1/news/
    """
    queryset = NewsPost.objects.filter(is_published=True).order_by('-published_at', '-created_at')
    serializer_class = NewsPostSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination


class NewsDetailView(generics.RetrieveAPIView):
    """
    Get news post detail and mark as read

    GET /api/v1/news/{slug}/
    """
    queryset = NewsPost.objects.filter(is_published=True)
    serializer_class = NewsPostSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Mark as read
        NewsRead.objects.update_or_create(
            user=request.user,
            post=instance,
            defaults={'read_at': timezone.now()},
        )

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# ==================== Admin CRUD Views ====================

class CRUDPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


# Profession CRUD
class ProfessionCRUDViewSet(viewsets.ModelViewSet):
    """CRUD for professions"""
    queryset = Profession.objects.all().order_by('path')
    serializer_class = ProfessionCRUDSerializer
    permission_classes = [IsAdminUser]
    pagination_class = CRUDPagination
    lookup_field = 'pk'


# EventCategory CRUD
class EventCategoryCRUDViewSet(viewsets.ModelViewSet):
    """CRUD for event categories"""
    queryset = EventCategory.objects.all().order_by('path')
    serializer_class = EventCategorySerializer
    permission_classes = [IsAdminUser]
    pagination_class = CRUDPagination
    lookup_field = 'pk'


# Language CRUD
class LanguageCRUDViewSet(viewsets.ModelViewSet):
    """CRUD for languages"""
    queryset = Language.objects.all().order_by('name')
    serializer_class = LanguageCRUDSerializer
    permission_classes = [IsAdminUser]
    pagination_class = CRUDPagination
    lookup_field = 'pk'


# Currency CRUD
class CurrencyCRUDViewSet(viewsets.ModelViewSet):
    """CRUD for currencies"""
    queryset = Currency.objects.all().order_by('name')
    serializer_class = CurrencyCRUDSerializer
    permission_classes = [IsAdminUser]
    pagination_class = CRUDPagination
    lookup_field = 'pk'


# ExchangeRate CRUD
class ExchangeRateCRUDViewSet(viewsets.ModelViewSet):
    """CRUD for exchange rates"""
    queryset = ExchangeRate.objects.all().select_related(
        'from_currency', 'to_currency'
    ).order_by('-updated_at')
    serializer_class = ExchangeRateCRUDSerializer
    permission_classes = [IsAdminUser]
    pagination_class = CRUDPagination
    lookup_field = 'pk'


# NewsPost CRUD
class NewsPostCRUDViewSet(viewsets.ModelViewSet):
    """CRUD for news posts"""
    queryset = NewsPost.objects.all().order_by('-created_at')
    serializer_class = NewsPostCRUDSerializer
    permission_classes = [IsAdminUser]
    pagination_class = CRUDPagination
    lookup_field = 'pk'

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# User CRUD
class UserCRUDView(generics.ListAPIView):
    """List and filter users (admin only)"""
    serializer_class = UserListSerializer
    permission_classes = [IsAdminUser]
    pagination_class = CRUDPagination

    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')

        # Apply filters
        q = self.request.query_params.get('q', '')
        if q:
            queryset = queryset.filter(
                Q(email__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(nickname__icontains=q) |
                Q(phone__icontains=q)
            )

        account_type = self.request.query_params.get('account_type')
        if account_type in ['personal', 'professional']:
            queryset = queryset.filter(account_type=account_type)

        staff = self.request.query_params.get('staff')
        if staff in ['1', '0']:
            queryset = queryset.filter(is_staff=(staff == '1'))

        active = self.request.query_params.get('active')
        if active in ['1', '0']:
            queryset = queryset.filter(is_active=(active == '1'))

        return queryset


class UserCRUDDetailView(generics.RetrieveUpdateAPIView):
    """Get and update user details (admin only)"""
    queryset = User.objects.all()
    serializer_class = AdminUserUpdateSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'pk'


class UserToggleActiveView(APIView):
    """Toggle user active status (admin only)"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        # Prevent deactivating yourself
        if user.pk == request.user.pk:
            return Response(
                {'error': _('You cannot deactivate your own account')},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])

        return Response({
            'message': f"User is now {'active' if user.is_active else 'inactive'}",
            'is_active': user.is_active,
        })


class UserToggleStaffView(APIView):
    """Toggle user staff status (admin only)"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        # Prevent demoting yourself
        if user.pk == request.user.pk:
            return Response(
                {'error': _('You cannot change your own staff status')},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.is_staff = not user.is_staff
        user.save(update_fields=['is_staff'])

        return Response({
            'message': f"User is now {'staff' if user.is_staff else 'not staff'}",
            'is_staff': user.is_staff,
        })


# ==================== CRUD Home ====================

class CRUDHomeView(APIView):
    """
    Admin CRUD dashboard home

    GET /api/v1/admin/crud/
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({
            'message': 'Admin CRUD Dashboard',
            'available_sections': {
                'professions': '/api/v1/admin/crud/professions/',
                'event_categories': '/api/v1/admin/crud/event-categories/',
                'languages': '/api/v1/admin/crud/languages/',
                'currencies': '/api/v1/admin/crud/currencies/',
                'exchange_rates': '/api/v1/admin/crud/exchange-rates/',
                'news_posts': '/api/v1/admin/crud/news/',
                'users': '/api/v1/admin/crud/users/',
            }
        })