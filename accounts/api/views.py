from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import calendar
from datetime import date, datetime, timedelta

from accounts.models import (
     Profession, AccountPhoto, ProfessionalPhoto,
    AudioAcapellaCover, VideoAcapellaCover, Review,
    FavoriteProfessional, NewsPost, NewsRead, Language,
    Currency, ExchangeRate
)
from events.models import Event, BusyTime, OfferThread, OfferMessage, EventCategory
from .serializers import *

User = get_user_model()


class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ==================== Authentication Views ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_api(request):
    """
    Register a new user account

    Request Body:
    {
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+1234567890",
        "country": "USA",
        "city": "New York",
        "date_of_birth": "1990-01-01",
        "account_type": "personal",
        "password": "securepassword123",
        "password2": "securepassword123"
    }

    Response:
    201 Created: User created successfully
    400 Bad Request: Validation errors
    """
    serializer = RegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()

        # Authenticate and login
        auth_user = authenticate(email=user.email, password=request.data['password'])
        if auth_user:
            login(request, auth_user)

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        user_data = UserBasicSerializer(user).data
        return Response({
            'message': _('Account created successfully'),
            'user': user_data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    """
    Login user and return JWT tokens

    Request Body:
    {
        "email": "user@example.com",
        "password": "password123"
    }

    Response:
    200 OK: Login successful with tokens
    401 Unauthorized: Invalid credentials
    """
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        login(request, user)

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        user_data = UserBasicSerializer(user).data
        return Response({
            'message': _('Login successful'),
            'user': user_data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })

    return Response({'error': _('Invalid credentials')}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_api(request):
    """
    Logout user (invalidate refresh token on mobile side)

    Response:
    200 OK: Logout successful
    """
    return Response({'message': _('Logout successful')})


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_api(request):
    """
    Refresh access token using refresh token

    Request Body:
    {
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    }

    Response:
    200 OK: New access token
    401 Unauthorized: Invalid refresh token
    """
    refresh_token = request.data.get('refresh')

    if not refresh_token:
        return Response({'error': _('Refresh token is required')}, status=status.HTTP_400_BAD_REQUEST)

    try:
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)

        return Response({
            'access': access_token,
            'refresh': str(refresh),
        })
    except Exception as e:
        return Response({'error': _('Invalid refresh token')}, status=status.HTTP_401_UNAUTHORIZED)


# ==================== User Profile Views ====================

class UserProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def retrieve(self, request):
        """
        Get current user's profile

        Response:
        200 OK: User profile data
        """
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    def update(self, request):
        """
        Update current user's profile

        Request Body: Partial user data

        Response:
        200 OK: Profile updated successfully
        400 Bad Request: Validation errors
        """
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': _('Profile updated successfully'),
                'user': serializer.data
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'])
    def upload_avatar(self, request):
        """
        Upload profile picture

        Request Body (multipart/form-data):
        - profile_picture: Image file

        Response:
        200 OK: Avatar uploaded successfully
        400 Bad Request: No file provided
        """
        if 'profile_picture' not in request.FILES:
            return Response(
                {'error': _('No file provided')},
                status=status.HTTP_400_BAD_REQUEST
            )

        request.user.profile_picture = request.FILES['profile_picture']
        request.user.save()

        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response({
            'message': _('Avatar uploaded successfully'),
            'user': serializer.data
        })

    @action(detail=False, methods=['GET'])
    def dashboard(self, request):
        """
        Get user dashboard data

        Response:
        200 OK: Dashboard data
        """
        user = request.user
        is_pro = user.account_type == User.AccountType.PROFESSIONAL

        # Get user's events
        upcoming_events = Event.objects.filter(
            created_by=user,
            start_datetime__gte=timezone.now()
        ).order_by('start_datetime')[:5]

        # Get reviews if professional
        reviews = []
        avg_rating = 0
        if is_pro:
            reviews = Review.objects.filter(professional=user).order_by('-created_at')[:5]
            avg = Review.objects.filter(professional=user).aggregate(avg=Avg('rating'))['avg']
            avg_rating = avg or 0

        # Get unread news count
        unread_news_count = 0
        if NewsPost.objects.filter(is_published=True).exists():
            read_posts = NewsRead.objects.filter(user=user).values_list('post_id', flat=True)
            unread_news_count = NewsPost.objects.filter(
                is_published=True
            ).exclude(id__in=read_posts).count()

        data = {
            'user': UserBasicSerializer(user).data,
            'is_professional': is_pro,
            'stats': {
                'upcoming_events': EventSerializer(upcoming_events, many=True).data,
                'reviews': ReviewSerializer(reviews, many=True).data if reviews else [],
                'average_rating': avg_rating,
                'unread_news': unread_news_count,
            }
        }

        return Response(data)


# ==================== Public Profiles ====================

class PublicProfileViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def retrieve(self, request, pk=None):
        """
        Get public profile by ID or public_id

        Query Parameters:
        - tab: "overview" or "calendar" (default: "overview")
        - year: For calendar view (default: current year)
        - month: For calendar view (default: current month)

        Response:
        200 OK: Profile data with specified tab
        404 Not Found: Profile not found
        """
        try:
            # Try to get by public_id first, then by pk
            if pk and len(pk) == 8 and pk.isdigit():
                prof = User.objects.get(public_id=pk, account_type=User.AccountType.PROFESSIONAL, is_active=True)
            else:
                prof = User.objects.get(pk=pk, account_type=User.AccountType.PROFESSIONAL, is_active=True)
        except User.DoesNotExist:
            return Response({'error': _('Profile not found')}, status=status.HTTP_404_NOT_FOUND)

        tab = request.query_params.get('tab', 'overview')

        # Prepare base data
        serializer = PublicProfileSerializer(prof, context={'request': request})
        data = serializer.data

        # Add tab-specific data
        if tab == 'overview':
            # Add reviews
            reviews = Review.objects.filter(professional=prof).select_related('reviewer').order_by('-created_at')[:10]
            data['reviews'] = ReviewSerializer(reviews, many=True).data

            # Add similar professionals
            prof_profession_ids = list(prof.professions.values_list('id', flat=True))
            similar_pros = User.objects.filter(
                account_type=User.AccountType.PROFESSIONAL,
                is_active=True
            ).exclude(pk=prof.pk)

            if prof_profession_ids:
                similar_pros = similar_pros.filter(professions__id__in=prof_profession_ids).distinct()

            similar_pros = similar_pros.annotate(
                avg_rating=Avg('reviews_received__rating'),
                review_count=Count('reviews_received')
            ).order_by('-id')[:8]

            data['similar_professionals'] = PublicProfileSerializer(
                similar_pros, many=True, context={'request': request}
            ).data

        elif tab == 'calendar':
            data['calendar'] = self._get_calendar_data(prof, request)

        return Response(data)

    def _get_calendar_data(self, prof, request):
        """Helper method to get calendar data"""
        today = timezone.localdate()
        year = int(request.query_params.get('year', today.year))
        month = int(request.query_params.get('month', today.month))

        # Get first and last day of month
        _, last_day = calendar.monthrange(year, month)
        first_day = date(year, month, 1)
        last_day = date(year, month, last_day)

        # Generate calendar weeks
        cal = calendar.Calendar(firstweekday=0)  # Monday
        weeks = cal.monthdatescalendar(year, month)

        # Get events
        events_qs = Event.objects.filter(
            is_locked=True,
            accepted_thread__professional=prof
        ).select_related('accepted_thread', 'accepted_thread__professional', 'created_by')

        # Get busy times
        busy_qs = BusyTime.objects.filter(
            user=prof,
            start_datetime__date__lte=last_day,
            end_datetime__date__gte=first_day
        )

        # Process events for each day
        booked_map = {}
        for event in events_qs:
            if not event.start_datetime or not event.end_datetime:
                continue

            start_local = timezone.localtime(event.start_datetime)
            end_local = timezone.localtime(event.end_datetime)

            d1 = start_local.date()
            d2 = end_local.date()

            # Generate date range
            current = d1
            while current <= d2:
                booked_map.setdefault(current, [])
                current += timedelta(days=1)

        # Process busy times
        busy_map = {}
        for busy in busy_qs:
            s = timezone.localtime(busy.start_datetime)
            e = timezone.localtime(busy.end_datetime)

            current = s.date()
            while current <= e.date():
                busy_map.setdefault(current, []).append({
                    'is_all_day': busy.is_all_day,
                    'start': s.strftime('%H:%M'),
                    'end': e.strftime('%H:%M'),
                    'note': busy.note
                })
                current += timedelta(days=1)

        # Prepare response
        prev_month = (date(year, month, 1) - timedelta(days=1)).replace(day=1)
        next_month = (date(year, month, 28) + timedelta(days=10)).replace(day=1)

        return {
            'year': year,
            'month': month,
            'month_name': date(year, month, 1).strftime('%B'),
            'weeks': [[d.isoformat() for d in week] for week in weeks],
            'prev_year': prev_month.year,
            'prev_month': prev_month.month,
            'next_year': next_month.year,
            'next_month': next_month.month,
            'today': today.isoformat(),
            'booked_days': list(booked_map.keys()),
            'busy_days': {str(k): v for k, v in busy_map.items()}
        }

    @action(detail=True, methods=['POST'], permission_classes=[IsAuthenticated])
    def toggle_favorite(self, request, pk=None):
        """
        Toggle favorite status for a professional

        Response:
        200 OK: Favorite status updated
        404 Not Found: Profile not found
        """
        try:
            prof = User.objects.get(pk=pk, account_type=User.AccountType.PROFESSIONAL, is_active=True)
        except User.DoesNotExist:
            return Response({'error': _('Profile not found')}, status=status.HTTP_404_NOT_FOUND)

        if prof == request.user:
            return Response(
                {'error': _('You cannot favorite your own profile')},
                status=status.HTTP_400_BAD_REQUEST
            )

        favorite, created = FavoriteProfessional.objects.get_or_create(
            user=request.user,
            professional=prof
        )

        if not created:
            favorite.delete()
            is_favorite = False
            message = _('Removed from favorites')
        else:
            is_favorite = True
            message = _('Added to favorites')

        return Response({
            'message': message,
            'is_favorite': is_favorite
        })

    @action(detail=True, methods=['GET'])
    def media(self, request, pk=None):
        """
        Get professional's media by type

        Query Parameters:
        - tab: "studio", "work", "audio", or "video" (default: "studio")
        - page: Page number for pagination

        Response:
        200 OK: Media items with pagination
        404 Not Found: Profile not found
        """
        try:
            prof = User.objects.get(pk=pk, account_type=User.AccountType.PROFESSIONAL, is_active=True)
        except User.DoesNotExist:
            return Response({'error': _('Profile not found')}, status=status.HTTP_404_NOT_FOUND)

        tab = request.query_params.get('tab', 'studio')

        if tab == 'studio':
            queryset = ProfessionalPhoto.objects.filter(user=prof)
            serializer_class = ProfessionalPhotoSerializer
            title = 'Studio Photos'

        elif tab == 'work':
            queryset = AccountPhoto.objects.filter(user=prof)
            serializer_class = AccountPhotoSerializer
            title = 'Work Photos'

        elif tab == 'audio':
            queryset = AudioAcapellaCover.objects.filter(user=prof)
            serializer_class = AudioCoverSerializer
            title = 'Audio Covers'

        elif tab == 'video':
            queryset = VideoAcapellaCover.objects.filter(user=prof)
            serializer_class = VideoCoverSerializer
            title = 'Video Covers'

        else:
            return Response(
                {'error': _('Invalid tab specified')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Paginate
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(queryset.order_by('-uploaded_at'), request)

        if page is not None:
            serializer = serializer_class(page, many=True, context={'request': request})
            return paginator.get_paginated_response({
                'title': title,
                'tab': tab,
                'items': serializer.data
            })

        serializer = serializer_class(queryset, many=True, context={'request': request})
        return Response({
            'title': title,
            'tab': tab,
            'items': serializer.data
        })


# ==================== Reviews ====================

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        """Return reviews for the current user if professional, or reviews given by user"""
        user = self.request.user

        if user.account_type == User.AccountType.PROFESSIONAL:
            return Review.objects.filter(professional=user)

        return Review.objects.filter(reviewer=user)

    def create(self, request):
        """
        Create a new review for a professional

        Request Body:
        {
            "professional": 123,
            "rating": 5,
            "comment": "Great service!"
        }

        Response:
        201 Created: Review created successfully
        400 Bad Request: Validation errors
        404 Not Found: Professional not found
        """
        professional_id = request.data.get('professional')

        try:
            professional = User.objects.get(
                pk=professional_id,
                account_type=User.AccountType.PROFESSIONAL,
                is_active=True
            )
        except User.DoesNotExist:
            return Response(
                {'error': _('Professional not found')},
                status=status.HTTP_404_NOT_FOUND
            )

        if professional == request.user:
            return Response(
                {'error': _('You cannot review your own profile')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check for existing review
        if Review.objects.filter(professional=professional, reviewer=request.user).exists():
            return Response(
                {'error': _('You have already reviewed this professional')},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(professional=professional, reviewer=request.user)
            return Response({
                'message': _('Review submitted successfully'),
                'review': serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== Media Upload Views ====================

class MediaUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, media_type):
        """
        Upload media files

        Path Parameter:
        - media_type: "normal_photos", "professional_photos", "audio", or "video"

        Request Body (multipart/form-data):
        - files: List of files
        - titles: Optional list of titles (for audio/video)

        Response:
        201 Created: Files uploaded successfully
        400 Bad Request: Invalid media type or no files
        """
        if media_type not in ['normal_photos', 'professional_photos', 'audio', 'video']:
            return Response(
                {'error': _('Invalid media type')},
                status=status.HTTP_400_BAD_REQUEST
            )

        files = request.FILES.getlist('files')
        titles = request.data.getlist('titles', [])

        if not files:
            return Response(
                {'error': _('No files provided')},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_items = []

        if media_type == 'normal_photos':
            for file in files:
                photo = AccountPhoto.objects.create(user=request.user, image=file)
                uploaded_items.append({
                    'id': photo.id,
                    'url': photo.image.url if photo.image else None,
                    'uploaded_at': photo.uploaded_at
                })

        elif media_type == 'professional_photos':
            for file in files:
                photo = ProfessionalPhoto.objects.create(user=request.user, image=file)
                uploaded_items.append({
                    'id': photo.id,
                    'url': photo.image.url if photo.image else None,
                    'uploaded_at': photo.uploaded_at
                })

        elif media_type == 'audio':
            for i, file in enumerate(files):
                title = titles[i] if i < len(titles) else ''
                audio = AudioAcapellaCover.objects.create(
                    user=request.user,
                    title=title,
                    audio_file=file
                )
                uploaded_items.append({
                    'id': audio.id,
                    'title': audio.title,
                    'url': audio.audio_file.url if audio.audio_file else None,
                    'uploaded_at': audio.uploaded_at
                })

        elif media_type == 'video':
            for i, file in enumerate(files):
                title = titles[i] if i < len(titles) else ''
                video = VideoAcapellaCover.objects.create(
                    user=request.user,
                    title=title,
                    video_file=file
                )
                uploaded_items.append({
                    'id': video.id,
                    'title': video.title,
                    'url': video.video_file.url if video.video_file else None,
                    'uploaded_at': video.uploaded_at
                })

        return Response({
            'message': _('Files uploaded successfully'),
            'count': len(uploaded_items),
            'items': uploaded_items
        }, status=status.HTTP_201_CREATED)


# ==================== Profession Views ====================

class ProfessionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing professions
    """
    queryset = Profession.objects.all()
    serializer_class = ProfessionSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsPagination

    @action(detail=False, methods=['GET'])
    def tree(self, request):
        """
        Get professions as hierarchical tree

        Response:
        200 OK: Nested profession tree
        """
        root_professions = Profession.objects.filter(parent=None)
        serializer = self.get_serializer(root_professions, many=True)
        return Response(serializer.data)


# ==================== Search Views ====================

class ProfessionalSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Search for professionals with filters

        Query Parameters:
        - q: Search query (name, profession)
        - profession: Profession ID filter
        - city: City filter
        - country: Country filter
        - min_rating: Minimum average rating
        - min_price: Minimum cost per hour
        - max_price: Maximum cost per hour
        - page: Page number
        - page_size: Items per page

        Response:
        200 OK: Paginated list of professionals
        """
        queryset = User.objects.filter(
            account_type=User.AccountType.PROFESSIONAL,
            is_active=True
        ).select_related('currency').prefetch_related('professions')

        # Apply filters
        search_query = request.query_params.get('q', '')
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(nickname__icontains=search_query) |
                Q(professions__name__icontains=search_query)
            ).distinct()

        profession_id = request.query_params.get('profession')
        if profession_id:
            queryset = queryset.filter(professions__id=profession_id)

        city = request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__iexact=city)

        country = request.query_params.get('country')
        if country:
            queryset = queryset.filter(country__iexact=country)

        min_rating = request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.annotate(
                avg_rating=Avg('reviews_received__rating')
            ).filter(avg_rating__gte=float(min_rating))
        else:
            queryset = queryset.annotate(
                avg_rating=Avg('reviews_received__rating')
            )

        min_price = request.query_params.get('min_price')
        if min_price:
            queryset = queryset.filter(cost_per_hour__gte=float(min_price))

        max_price = request.query_params.get('max_price')
        if max_price:
            queryset = queryset.filter(cost_per_hour__lte=float(max_price))

        # Order by rating or date joined
        order_by = request.query_params.get('order_by', '-avg_rating')
        if order_by in ['avg_rating', '-avg_rating', 'date_joined', '-date_joined']:
            queryset = queryset.order_by(order_by)
        else:
            queryset = queryset.order_by('-avg_rating')

        # Paginate
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(queryset, request)

        if page is not None:
            serializer = PublicProfileSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        serializer = PublicProfileSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


# ==================== Favorites ====================

class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteProfessionalSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return FavoriteProfessional.objects.filter(user=self.request.user)

    def create(self, request):
        """
        Add a professional to favorites

        Request Body:
        {
            "professional": 123
        }

        Response:
        201 Created: Added to favorites
        400 Bad Request: Already in favorites or invalid data
        404 Not Found: Professional not found
        """
        professional_id = request.data.get('professional')

        try:
            professional = User.objects.get(
                pk=professional_id,
                account_type=User.AccountType.PROFESSIONAL,
                is_active=True
            )
        except User.DoesNotExist:
            return Response(
                {'error': _('Professional not found')},
                status=status.HTTP_404_NOT_FOUND
            )

        if professional == request.user:
            return Response(
                {'error': _('You cannot favorite your own profile')},
                status=status.HTTP_400_BAD_REQUEST
            )

        if FavoriteProfessional.objects.filter(user=request.user, professional=professional).exists():
            return Response(
                {'error': _('Already in favorites')},
                status=status.HTTP_400_BAD_REQUEST
            )

        favorite = FavoriteProfessional.objects.create(
            user=request.user,
            professional=professional
        )

        serializer = self.get_serializer(favorite)
        return Response({
            'message': _('Added to favorites'),
            'favorite': serializer.data
        }, status=status.HTTP_201_CREATED)


# ==================== News Views ====================

class NewsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NewsPost.objects.filter(is_published=True).order_by('-published_at')
    serializer_class = NewsPostSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    @action(detail=True, methods=['POST'])
    def mark_read(self, request, pk=None):
        """
        Mark a news post as read

        Response:
        200 OK: Marked as read
        404 Not Found: News post not found
        """
        try:
            news_post = self.get_queryset().get(pk=pk)
        except NewsPost.DoesNotExist:
            return Response(
                {'error': _('News post not found')},
                status=status.HTTP_404_NOT_FOUND
            )

        NewsRead.objects.get_or_create(user=request.user, post=news_post)

        return Response({'message': _('Marked as read')})

    @action(detail=False, methods=['GET'])
    def unread(self, request):
        """
        Get unread news posts

        Response:
        200 OK: List of unread news posts
        """
        read_posts = NewsRead.objects.filter(user=request.user).values_list('post_id', flat=True)
        unread_posts = self.get_queryset().exclude(id__in=read_posts)

        page = self.paginate_queryset(unread_posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(unread_posts, many=True)
        return Response(serializer.data)


# ==================== Utility Views ====================

class LanguageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Language.objects.all().order_by('name')
    serializer_class = LanguageSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsPagination


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Currency.objects.all().order_by('name')
    serializer_class = CurrencySerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsPagination


class ExchangeRateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Get exchange rates

        Query Parameters:
        - from_currency: Filter by from currency ID
        - to_currency: Filter by to currency ID

        Response:
        200 OK: List of exchange rates
        """
        queryset = ExchangeRate.objects.all().select_related('from_currency', 'to_currency')

        from_currency = request.query_params.get('from_currency')
        if from_currency:
            queryset = queryset.filter(from_currency_id=from_currency)

        to_currency = request.query_params.get('to_currency')
        if to_currency:
            queryset = queryset.filter(to_currency_id=to_currency)

        serializer = ExchangeRateSerializer(queryset, many=True)
        return Response(serializer.data)