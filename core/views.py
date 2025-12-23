# core/views.py
# FINAL UPDATED VERSION WITH DOWNLOADS SUPPORT & FIXED ALL ERRORS + PROPER INDENTATION

import os
import random
import string
import time
import hashlib
import hmac
import binascii
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.models import LogEntry
from django.utils import timezone
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate, get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings as dj_settings
from django.http import JsonResponse, HttpResponseForbidden
from django.core.management import call_command

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.authtoken.models import Token

from .models import UserFile, FileView, Withdrawal, SiteSettings, BotLink, FileDownload
from .serializers import UserProfileSerializer, FileSerializer, WithdrawalSerializer, BotLinkSerializer
from .services import calculate_earnings_per_view
from .utils import get_client_ip, is_unique_view_today

User = get_user_model()


# ================================
# SUPERUSER ONLY PERMISSION
# ================================
class IsSuperuser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


# ========================
# USER AUTH & PROFILE
# ========================
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')

        if not all([username, email, password]):
            return Response({"error": "All fields required"}, status=400)

        if User.objects.filter(username__iexact=username).exists():
            return Response({"error": "Username already taken"}, status=400)
        if User.objects.filter(email__iexact=email).exists():
            return Response({"error": "Email already registered"}, status=400)

        user = User.objects.create_user(username=username, email=email, password=password)
        return Response({"message": "Registered successfully!", "username": user.username}, status=201)


class ProfileView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)


# ========================
# FILE UPLOAD & PUBLIC VIEW
# ========================
class UploadFileView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_url = request.data.get('file_url')
        thumbnail_url = request.data.get('thumbnail_url')
        title = request.data.get('title', 'Untitled')
        file_type = request.data.get('file_type')
        allow_download = request.data.get('allow_download', True)

        if not file_url or not file_type:
            return Response({"error": "file_url and file_type are required"}, status=400)

        if file_type not in ['video', 'image', 'other']:
            return Response({"error": "Invalid file_type"}, status=400)

        user_file = UserFile.objects.create(
            user=request.user,
            title=title,
            file_type=file_type,
            short_code=''.join(random.choices(string.ascii_uppercase + string.digits, k=8)),
            allow_download=allow_download,
            external_file_url=file_url,
            external_thumbnail_url=thumbnail_url or file_url,
        )

        return Response(FileSerializer(user_file, context={'request': request}).data, status=201)


@api_view(['PATCH'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_file(request, pk):
    try:
        file_obj = UserFile.objects.get(pk=pk, user=request.user)
    except UserFile.DoesNotExist:
        return Response({"error": "File not found"}, status=404)

    if 'title' in request.data:
        file_obj.title = request.data['title']
    if 'allow_download' in request.data:
        file_obj.allow_download = request.data.get('allow_download')
    if 'external_thumbnail_url' in request.data:
        file_obj.external_thumbnail_url = request.data['external_thumbnail_url']

    file_obj.save()
    return Response(FileSerializer(file_obj, context={'request': request}).data)


# ========================
# PUBLIC FILE VIEW (View & Download Tracking)
# ========================
@api_view(['GET'])
@permission_classes([AllowAny])
def public_file_view(request, short_code):
    try:
        file_obj = UserFile.objects.get(short_code=short_code, is_active=True)
    except UserFile.DoesNotExist:
        return Response({"error": "File not found or inactive"}, status=404)

    ip = get_client_ip(request)
    settings = SiteSettings.get_settings()
    earning_rate = settings.earning_per_view

    download_requested = request.query_params.get('download', 'false').lower() == 'true'
    is_download_action = (file_obj.file_type != 'video') or download_requested

    view_incremented = False
    if file_obj.file_type == 'video':
        file_obj.views += 1
        if is_unique_view_today(file_obj, ip):
            file_obj.unique_views += 1
            FileView.objects.create(file=file_obj, ip_address=ip, user_agent=request.META.get('HTTP_USER_AGENT', ''))
        view_incremented = True

    download_incremented = False
    if is_download_action:
        file_obj.downloads += 1
        if not FileDownload.objects.filter(file=file_obj, ip_address=ip, downloaded_at__date=timezone.now().date()).exists():
            file_obj.unique_downloads += 1
            FileDownload.objects.create(file=file_obj, ip_address=ip, user_agent=request.META.get('HTTP_USER_AGENT', ''))
        download_incremented = True

    file_obj.save()

    # Earnings
    earning = Decimal('0.0')
    if view_incremented:
        earning += earning_rate
    if download_incremented:
        earning += earning_rate * Decimal('1.5')

    if earning > 0:
        file_obj.earnings += earning
        file_obj.download_earnings += (earning_rate * Decimal('1.5') if download_incremented else Decimal('0.0'))
        file_obj.user.pending_earnings += earning
        file_obj.user.total_earnings += earning
        file_obj.user.save()

    file_obj.save()

    serializer = FileSerializer(file_obj, context={'request': request})
    data = serializer.data
    data['should_download'] = is_download_action
    return Response(data)


# ========================
# USER DASHBOARD VIEWS
# ========================
class MyFilesView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        files = request.user.files.all().order_by('-created_at')
        serializer = FileSerializer(files, many=True, context={'request': request})
        return Response(serializer.data)


class AnalyticsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()
        month_start = today.replace(day=1)
        settings = SiteSettings.get_settings()
        rate_per_view = float(settings.earning_per_view)

        # Daily Stats
        today_files_count = user.files.filter(created_at__date=today).count()
        today_views_count = FileView.objects.filter(file__user=user, viewed_at__date=today).count()
        today_downloads_count = FileDownload.objects.filter(file__user=user, downloaded_at__date=today).count()
        today_earnings = round((today_views_count + today_downloads_count * 1.5) * rate_per_view, 5)

        # Monthly Stats
        monthly_files_count = user.files.filter(created_at__gte=month_start).count()
        monthly_views_count = FileView.objects.filter(file__user=user, viewed_at__gte=month_start).count()
        monthly_downloads_count = FileDownload.objects.filter(file__user=user, downloaded_at__gte=month_start).count()
        monthly_earnings = round((monthly_views_count + monthly_downloads_count * 1.5) * rate_per_view, 5)

        # Last 30 Days Chart
        start_date = today - timedelta(days=29)
        views_per_day = FileView.objects.filter(
            file__user=user,
            viewed_at__date__gte=start_date
        ).annotate(day=TruncDate('viewed_at')).values('day').annotate(count=Count('id')).order_by('day')

        downloads_per_day = FileDownload.objects.filter(
            file__user=user,
            downloaded_at__date__gte=start_date
        ).annotate(day=TruncDate('downloaded_at')).values('day').annotate(count=Count('id')).order_by('day')

        views_dict = {item['day']: item['count'] for item in views_per_day}
        downloads_dict = {item['day']: item['count'] for item in downloads_per_day}

        last_30_days = []
        for i in range(30):
            day = start_date + timedelta(days=i)
            views = views_dict.get(day, 0)
            downloads = downloads_dict.get(day, 0)
            earnings = round((views + downloads * 1.5) * rate_per_view, 5)
            last_30_days.append({
                "date": day.isoformat(),
                "views": views,
                "downloads": downloads,
                "earnings": earnings
            })

        # Total Downloads & Download Earnings
        total_downloads = user.files.aggregate(total=Sum('downloads'))['total'] or 0
        total_download_earnings = user.files.aggregate(total=Sum('download_earnings'))['total'] or 0

        return Response({
            "total_earnings": round(float(user.total_earnings), 5),
            "paid_earnings": round(float(user.paid_earnings), 5),
            "pending_earnings": round(float(user.pending_earnings), 5),

            "total_downloads": total_downloads,
            "download_earnings": round(float(total_download_earnings), 5),

            "daily": {
                "uploaded_files": today_files_count,
                "views": today_views_count,
                "downloads": today_downloads_count,
                "total_earnings": today_earnings
            },

            "monthly": {
                "uploaded_files": monthly_files_count,
                "views": monthly_views_count,
                "downloads": monthly_downloads_count,
                "total_earnings": monthly_earnings
            },

            "last_30_days": last_30_days
        })


# ========================
# WITHDRAWALS
# ========================
class CreateWithdrawalView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            amount = float(request.data.get('amount'))
        except:
            return Response({"error": "Invalid amount"}, status=400)

        settings = SiteSettings.get_settings()
        min_wd = float(settings.min_withdrawal)

        if amount < min_wd:
            return Response({"error": f"Minimum withdrawal is ${min_wd}"}, status=400)
        if amount > request.user.pending_earnings:
            return Response({"error": "Insufficient balance"}, status=400)

        Withdrawal.objects.create(
            user=request.user,
            amount=amount,
            payment_details=request.data.get('payment_details', '')
        )
        request.user.pending_earnings -= Decimal(str(amount))
        request.user.save(update_fields=['pending_earnings'])

        return Response({"message": "Withdrawal requested successfully!"}, status=201)


class WithdrawalListView(generics.ListAPIView):
    serializer_class = WithdrawalSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Withdrawal.objects.filter(user=self.request.user).order_by('-requested_at')


# ========================
# ADMIN PANEL — ONLY SUPERUSER
# ========================
@api_view(['GET'])
@permission_classes([IsSuperuser])
def admin_users(request):
    users = User.objects.all().annotate(
        file_count=Count('files')
    )

    data = list(users.values(
        'id',
        'username',
        'email',
        'total_earnings',
        'pending_earnings',
        'paid_earnings',
        'is_active',
        'created_at',
        'file_count'
    ))

    return Response(data)


@api_view(['GET'])
@permission_classes([IsSuperuser])
def admin_all_files(request):
    files = UserFile.objects.select_related('user').all()

    data = []
    for f in files:
        data.append({
            "id": f.id,
            "title": f.title or "Untitled",
            "user_username": f.user.username if f.user else "Deleted User",
            "views": f.views,
            "downloads": f.downloads,
            "earnings": round(float(f.earnings), 5),
            "is_active": f.is_active,
            "created_at": f.created_at.strftime("%b %d, %Y"),
            "file_url": f.external_file_url or "",
            "thumbnail_url": (
                f.external_thumbnail_url
                or (f.external_file_url if f.file_type == "image" else
                    "https://via.placeholder.com/80x80/333/fff?text=No+Image")
            ),
        })

    return Response(data)


@api_view(['GET'])
@permission_classes([IsSuperuser])
def admin_stats(request):
    total_earnings = User.objects.aggregate(t=Sum('total_earnings'))['t'] or 0
    total_downloads = UserFile.objects.aggregate(t=Sum('downloads'))['t'] or 0

    return Response({
        "total_users": User.objects.count(),
        "total_files": UserFile.objects.count(),
        "total_views": UserFile.objects.aggregate(t=Sum('views'))['t'] or 0,
        "total_downloads": total_downloads,
        "total_earnings": round(float(total_earnings), 5),
    })


@api_view(['GET'])
@permission_classes([IsSuperuser])
def admin_global_stats(request):
    total_platform = User.objects.aggregate(t=Sum('total_earnings'))['t'] or 0
    total_paid = User.objects.aggregate(t=Sum('paid_earnings'))['t'] or 0
    pending_wd = Withdrawal.objects.filter(status='pending').aggregate(t=Sum('amount'))['t'] or 0

    return Response({
        "platform_earnings": round(float(total_platform), 5),
        "total_paid": round(float(total_paid), 5),
        "pending_withdrawals": round(float(pending_wd or 0), 5),
    })


@api_view(['GET'])
@permission_classes([IsSuperuser])
def admin_logs(request):
    logs = LogEntry.objects.select_related('user').order_by('-action_time')[:200]
    data = []
    for log in logs:
        data.append({
            "timestamp": log.action_time.isoformat(),
            "user": log.user.username if log.user else "System",
            "action": log.get_action_flag_display(),
            "details": f"{log.content_type} → {log.object_repr}"
        })
    return Response(data)


@api_view(['GET', 'PATCH'])
@permission_classes([IsSuperuser])
def admin_settings(request):
    settings_obj = SiteSettings.get_settings()

    if request.method == 'GET':
        return Response({
            "earning_per_view": float(settings_obj.earning_per_view),
            "min_withdrawal": float(settings_obj.min_withdrawal),
            "site_name": settings_obj.site_name,
            "admob_banner_id": settings_obj.admob_banner_id,
            "admob_interstitial_id": settings_obj.admob_interstitial_id,
            "meta_banner_placement_id": settings_obj.meta_banner_placement_id or "",
            "meta_interstitial_placement_id": settings_obj.meta_interstitial_placement_id or "",
        })

    elif request.method == 'PATCH':
        if 'earning_per_view' in request.data:
            settings_obj.earning_per_view = Decimal(str(request.data['earning_per_view']))
        if 'min_withdrawal' in request.data:
            settings_obj.min_withdrawal = Decimal(str(request.data['min_withdrawal']))
        if 'site_name' in request.data:
            settings_obj.site_name = request.data['site_name']
        if 'admob_banner_id' in request.data:
            settings_obj.admob_banner_id = request.data['admob_banner_id'].strip()
        if 'admob_interstitial_id' in request.data:
            settings_obj.admob_interstitial_id = request.data['admob_interstitial_id'].strip()
        if 'meta_banner_placement_id' in request.data:
            settings_obj.meta_banner_placement_id = request.data['meta_banner_placement_id'].strip()
        if 'meta_interstitial_placement_id' in request.data:
            settings_obj.meta_interstitial_placement_id = request.data['meta_interstitial_placement_id'].strip()

        settings_obj.save()
        return Response({"message": "Settings updated successfully!"})


@api_view(['GET'])
@permission_classes([IsSuperuser])
def admin_withdrawals(request):
    withdrawals = Withdrawal.objects.select_related('user').all().values(
        'id', 'user__username', 'amount', 'status', 'requested_at', 'processed_at'
    )
    return Response(list(withdrawals))


@api_view(['POST'])
@permission_classes([IsSuperuser])
def admin_approve_withdrawal(request, pk):
    w = get_object_or_404(Withdrawal, pk=pk)
    w.status = 'paid'
    w.processed_at = timezone.now()
    w.user.paid_earnings += w.amount
    w.user.pending_earnings -= w.amount
    w.user.total_earnings = w.user.paid_earnings + w.user.pending_earnings
    w.user.save()
    w.save()
    return Response({"message": "Withdrawal approved"})


@api_view(['POST'])
@permission_classes([IsSuperuser])
def admin_reject_withdrawal(request, pk):
    w = get_object_or_404(Withdrawal, pk=pk)
    w.status = 'rejected'
    w.processed_at = timezone.now()
    w.user.pending_earnings += w.amount
    w.user.save()
    w.save()
    return Response({"message": "Withdrawal rejected"})


@api_view(['POST', 'DELETE'])
@permission_classes([IsSuperuser])
def admin_ban_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.is_active = False
        user.save()
        return Response({"message": "User banned"})
    else:
        user.is_active = True
        user.save()
        return Response({"message": "User unbanned"})


@api_view(['DELETE'])
@permission_classes([IsSuperuser])
def admin_delete_file(request, pk):
    file = get_object_or_404(UserFile, pk=pk)
    file.delete()
    return Response({"message": "File deleted permanently"})


@api_view(['POST'])
@permission_classes([IsSuperuser])
def admin_manual_payout(request):
    try:
        user_id = int(request.data['user_id'])
        amount = Decimal(str(request.data['amount']))
        user = User.objects.get(id=user_id)
        user.paid_earnings += amount
        user.pending_earnings -= amount
        if user.pending_earnings < 0:
            user.pending_earnings = 0
        user.total_earnings = user.paid_earnings + user.pending_earnings
        user.save()
        return Response({"message": f"Manual payout of ${amount} successful"})
    except Exception:
        return Response({"error": "Invalid data"}, status=400)


# ========================
# ADMIN LOGIN & BOT LINKS
# ========================
@method_decorator(csrf_exempt, name='dispatch')
class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({"error": "Username & password required"}, status=400)

        user = authenticate(username=username, password=password)

        if user and user.is_superuser:
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                "token": token.key,
                "message": "Admin login successful",
                "user": {"username": user.username}
            })

        return Response({"error": "Only superuser can login as admin"}, status=403)


@api_view(['GET'])
@permission_classes([IsSuperuser])
def admin_bot_links(request):
    bots = BotLink.objects.filter(is_active=True)
    serializer = BotLinkSerializer(bots, many=True)
    return Response(serializer.data)


@api_view(['POST', 'PATCH', 'DELETE'])
@permission_classes([IsSuperuser])
def admin_manage_bot_link(request):
    if request.method == 'POST':
        serializer = BotLinkSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    elif request.method == 'PATCH':
        bot_id = request.data.get('id')
        if not bot_id:
            return Response({"error": "id is required for edit"}, status=400)
        try:
            bot = BotLink.objects.get(id=bot_id)
        except BotLink.DoesNotExist:
            return Response({"error": "Bot not found"}, status=404)

        serializer = BotLinkSerializer(bot, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    elif request.method == 'DELETE':
        bot_id = request.data.get('id')
        if not bot_id:
            return Response({"error": "id is required"}, status=400)
        try:
            bot = BotLink.objects.get(id=bot_id)
            bot.delete()
            return Response({"message": "Bot deleted successfully"})
        except BotLink.DoesNotExist:
            return Response({"error": "Bot not found"}, status=404)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_bot_links(request):
    bots = BotLink.objects.filter(is_active=True).order_by('order')
    serializer = BotLinkSerializer(bots, many=True)
    return Response(serializer.data)


# ========================
# PUBLIC ADMOB + META IDs
# ========================
@api_view(['GET'])
@permission_classes([AllowAny])
def get_admob_ids(request):
    """
    Flutter app is endpoint se AdMob aur Meta IDs fetch karega
    """
    settings = SiteSettings.get_settings()

    return Response({
        "banner_id": settings.admob_banner_id or "ca-app-pub-3940256099942544/6300978111",
        "interstitial_id": settings.admob_interstitial_id or "ca-app-pub-3940256099942544/1033173712",
        "meta_banner_id": settings.meta_banner_placement_id or "",
        "meta_interstitial_id": settings.meta_interstitial_placement_id or "",
    })


def health_check(request):
    return JsonResponse({"status": "ok"})


def run_migrations(request):
    if request.GET.get("key") != dj_settings.SYSTEM_SECRET:
        return HttpResponseForbidden()
    call_command("migrate")
    return JsonResponse({"status": "ok"})

def run_full_migration(request):
    if request.GET.get("key") != settings.SYSTEM_SECRET:
        return HttpResponseForbidden("Forbidden")

    try:
        call_command("makemigrations")
        call_command("migrate")
        return JsonResponse({
            "status": "ok",
            "message": "makemigrations + migrate completed"
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "error": str(e)
        }, status=500)


def create_superuser(request):
    if request.GET.get("key") != dj_settings.SYSTEM_SECRET:
        return HttpResponseForbidden()

    User = get_user_model()
    if User.objects.filter(username="admin").exists():
        return JsonResponse({"status": "exists"})

    User.objects.create_superuser(
        username="diskwala",
        email="diskwala01@gmail.com",
        password="DISKwala7678"
    )
    return JsonResponse({"status": "created"})


@api_view(['GET'])
@permission_classes([AllowAny])
def imagekit_auth(request):
    private_key_str = getattr(dj_settings, 'IMAGEKIT_PRIVATE_KEY', None)

    print("Private key loaded:", "Yes" if private_key_str else "No")

    if not private_key_str:
        return Response({"error": "Private key missing in settings"}, status=500)

    try:
        token = binascii.hexlify(os.urandom(16)).decode()
        expire = int(time.time()) + 3600
        message = token + str(expire)

        private_key_bytes = private_key_str.encode('utf-8')

        signature = hmac.new(
            private_key_bytes,
            message.encode('utf-8'),
            hashlib.sha1
        ).hexdigest()

        print("Auth params generated:", {"token": token[:10] + "...", "expire": expire, "signature": signature[:10] + "..."})

        return Response({
            "token": token,
            "expire": expire,
            "signature": signature
        })

    except Exception as e:
        print("Error in imagekit_auth:", str(e))
        import traceback
        traceback.print_exc()
        return Response({"error": "Auth generation failed"}, status=500)