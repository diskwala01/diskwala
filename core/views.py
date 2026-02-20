# core/views.py
# FINAL UPDATED VERSION WITH:
# - DOWNLOADS SUPPORT
# - EMAIL OTP VERIFICATION (BREVO SMTP)
# - EMAIL VERIFIED CHECK FOR WITHDRAWAL
# - ADSENSE CLIENT ID SUPPORT
# - ALL FIXES & PROPER INDENTATION

import os
import io
import random
import string
import time
import hashlib
import requests
import hmac
import binascii
from django.db import connection
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.models import LogEntry
from django.utils import timezone
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, render
from django.contrib.auth import authenticate, get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings as dj_settings
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.core.management import call_command
from django.core.mail import send_mail

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.authtoken.models import Token

from .models import UserFile, FileView, Withdrawal, SiteSettings, BotLink, FileDownload, BroadcastNotification
from .serializers import UserProfileSerializer, FileSerializer, WithdrawalSerializer, BotLinkSerializer, BroadcastNotificationSerializer, SiteSettingsSerializer
from .services import calculate_earnings_per_1000_views, calculate_earnings_per_1000_downloads
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        print("📩 PATCH REQUEST DATA:", request.data)

        user = request.user

        data = request.data

        # Manual update – yeh guaranteed DB mein save karega
        if 'brand_name' in data:
            user.brand_name = data['brand_name'].strip() if data['brand_name'] else "My Drive"

        if 'instagram' in data:
            user.instagram = data['instagram'] if data['instagram'] else None
        if 'whatsapp' in data:
            user.whatsapp = data['whatsapp'] if data['whatsapp'] else None
        if 'facebook' in data:
            user.facebook = data['facebook'] if data['facebook'] else None
        if 'twitter' in data:
            user.twitter = data['twitter'] if data['twitter'] else None
        if 'youtube' in data:
            user.youtube = data['youtube'] if data['youtube'] else None
        if 'website' in data:
            user.website = data['website'] if data['website'] else None

        # Explicit save
        user.save(update_fields=[
            'brand_name', 'instagram', 'whatsapp', 'facebook',
            'twitter', 'youtube', 'website'
        ])

        # Confirm from DB
        user.refresh_from_db()

        print("✅ MANUAL SAVE SUCCESS:")
        print("   brand_name:", user.brand_name)
        print("   instagram:", user.instagram)

        return Response(UserProfileSerializer(user).data)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def send_email_otp(request):
    user = request.user
    if user.email_verified:
        return Response({"message": "Email already verified"}, status=400)

    otp = ''.join(random.choices('0123456789', k=6))
    user.email_otp = otp
    user.email_otp_expiry = timezone.now() + timedelta(minutes=10)
    user.save(update_fields=['email_otp', 'email_otp_expiry'])

    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        return Response({"error": "Email service not configured"}, status=500)

    url = "https://api.brevo.com/v3/smtp/email"
    payload = {
        "sender": {"name": "DiskWala", "email": "diskwala01@gmail.com"},
        "to": [{"email": user.email, "name": user.username}],
        "subject": "DiskWala - Email Verification OTP",
        "htmlContent": f"""
        <html>
          <body>
            <h2>Welcome to DiskWala!</h2>
            <p>Your OTP for email verification is: <strong style="font-size:1.5em">{otp}</strong></p>
            <p>This OTP is valid for <strong>10 minutes</strong> only.</p>
            <p>Do not share this OTP with anyone.</p>
            <br>
            <p>Thanks,<br>DiskWala Team</p>
          </body>
        </html>
        """
    }
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return Response({"message": "OTP sent successfully to your email"})
    except requests.exceptions.RequestException as e:
        print("Brevo API Error:", e)
        if hasattr(e, 'response') and e.response is not None:
            print("Response:", e.response.text)
        return Response({"error": "Failed to send OTP. Please try again later."}, status=500)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def verify_email_otp(request):
    otp = request.data.get('otp')
    user = request.user

    if user.email_verified:
        return Response({"error": "Email already verified"}, status=400)

    if not otp or otp != user.email_otp:
        return Response({"error": "Invalid OTP"}, status=400)

    if timezone.now() > user.email_otp_expiry:
        return Response({"error": "OTP expired"}, status=400)

    user.email_verified = True
    user.email_otp = None
    user.email_otp_expiry = None
    user.save(update_fields=['email_verified', 'email_otp', 'email_otp_expiry'])

    return Response({"message": "Email verified successfully!"})

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

# ==================== NEW: PUBLIC SITE SETTINGS (SEO + Global) ====================
@api_view(['GET'])
@permission_classes([AllowAny])
def public_site_settings(request):
    """
    Public endpoint to get site-wide settings
    Used by:
    - Frontend for dynamic SEO tags
    - Loading AdSense / third-party ad scripts
    - App settings (earning rates, social links, etc.)
    """
    try:
        # Singleton pattern - हमेशा पहला (या एकमात्र) रिकॉर्ड लौटाता है
        settings = SiteSettings.get_settings()
        
        # Serializer से सारे जरूरी फील्ड्स serialize हो जाएंगे
        serializer = SiteSettingsSerializer(settings)
        
        # अगर आपको कुछ एक्स्ट्रा/कस्टम फील्ड्स जोड़ने हों तो यहाँ कर सकते हैं
        data = serializer.data
        
        # (Optional) कुछ अतिरिक्त calculated या safe फील्ड्स अगर जरूरत हो
        # data['current_year'] = timezone.now().year
        
        return Response(data)
        
    except Exception as e:
        # प्रोडक्शन में इसे logger में डालना बेहतर होता है
        print(f"Error loading site settings: {str(e)}")  # ← debug के लिए
        
        return Response(
            {"error": "Failed to load site settings. Please try again later."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ========================
# PUBLIC FILE VIEW (View & Download Tracking + SEO Ready)
# ========================
@api_view(['GET'])
@permission_classes([AllowAny])
def public_file_view(request, short_code):
    try:
        file_obj = UserFile.objects.select_related('user').get(
            short_code=short_code,
            is_active=True
        )
    except UserFile.DoesNotExist:
        return Response({"error": "File not found or inactive"}, status=status.HTTP_404_NOT_FOUND)

    ip = get_client_ip(request)
    settings = SiteSettings.get_settings()

    # Query param se check karo ki download request hai ya nahi
    download_requested = request.query_params.get('download', 'false').lower() == 'true'
    is_download_action = (file_obj.file_type != 'video') or download_requested

    view_incremented = False
    download_incremented = False

    # ====================
    # VIEW COUNT — अब VIDEO के लिए बिल्कुल नहीं बढ़ेगा
    # ====================
    if file_obj.file_type == 'video':
        # Video के लिए views और unique_views पर कोई बदलाव नहीं
        pass
    else:
        # Non-video files के लिए views बढ़ाना (जैसा पहले था)
        file_obj.views += 1
        if is_unique_view_today(file_obj, ip):
            file_obj.unique_views += 1
            FileView.objects.create(
                file=file_obj,
                ip_address=ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
        view_incremented = True

    # ====================
    # DOWNLOAD COUNT (Non-video या video with ?download=true)
    # ====================
    if is_download_action:
        file_obj.downloads += 1
        today = timezone.now().date()
        already_downloaded_today = FileDownload.objects.filter(
            file=file_obj,
            ip_address=ip,
            downloaded_at__date=today
        ).exists()

        if not already_downloaded_today:
            file_obj.unique_downloads += 1
            FileDownload.objects.create(
                file=file_obj,
                ip_address=ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
        download_incremented = True

    # ====================
    # EARNINGS CALCULATION — video के लिए views से earning नहीं आएगी
    # ====================
    total_earning = Decimal('0.0000')

    if view_incremented:
        total_earning += settings.earning_per_view

    if download_incremented:
        # Download earning = 1.5x view rate (aap change kar sakte ho)
        download_earning = settings.earning_per_view * Decimal('1.5')
        total_earning += download_earning

    if total_earning > 0:
        file_obj.earnings += total_earning
        file_obj.download_earnings += (
            settings.earning_per_view * Decimal('1.5') if download_incremented else Decimal('0.0000')
        )
        file_obj.save(update_fields=[
            'views', 'unique_views', 'downloads', 'unique_downloads',
            'earnings', 'download_earnings'
        ])

        # User earnings update
        user = file_obj.user
        user.pending_earnings += total_earning
        user.total_earnings += total_earning
        user.save(update_fields=['pending_earnings', 'total_earnings'])

    # ====================
    # SERIALIZED RESPONSE
    # ====================
    serializer = FileSerializer(file_obj, context={'request': request})
    data = serializer.data

    # Extra data for Flutter/Android App
    data.update({
        'should_download': file_obj.user.allow_download and is_download_action,
        'uploaded_by': file_obj.user.username,
        'brand_name': file_obj.user.brand_name or file_obj.user.username,

        # Creator Social & Support Links
        'whatsapp': file_obj.user.whatsapp or None,
        'facebook': file_obj.user.facebook or None,
        'instagram': file_obj.user.instagram or None,
        'twitter': file_obj.user.twitter or None,
        'youtube': file_obj.user.youtube or None,
        'website': file_obj.user.website or None,
        'telegram_channel': file_obj.user.telegram_channel or None,
        'support_link': file_obj.user.support_link or None,
    })

    # ====================
    # SEO DATA
    # ====================
    seo_title = f"{file_obj.title} - {file_obj.user.brand_name or file_obj.user.username} on Royaldisk"
    seo_description = (
        file_obj.description[:297] + "..." 
        if file_obj.description and len(file_obj.description) > 300 
        else file_obj.description or f"Download or view {file_obj.title} securely shared on Royaldisk."
    )
    seo_og_image = (
        file_obj.external_thumbnail_url or 
        file_obj.external_file_url or 
        settings.seo_og_image or 
        f"{request.scheme}://{request.get_host()}/static/default-og.jpg"
    )

    data.update({
        'seo': {
            'title': seo_title,
            'description': seo_description,
            'keywords': settings.seo_keywords or "file sharing, download, secure upload, earn online",
            'og_image': seo_og_image,
            'og_url': request.build_absolute_uri(),
            'site_name': settings.site_name,
        }
    })

    return Response(data, status=status.HTTP_200_OK)

# 🚀 YE NAYA VIEW public_file_view के BAAD add karo (line 350-370 के around)
@api_view(['GET'])
@permission_classes([AllowAny])
def user_files_view(request, username):
    """
    Username se user ki saari active video files return karo
    URL: /api/user-files/{username}/
    """
    try:
        user = get_object_or_404(User, username=username)
        files = UserFile.objects.filter(
            user=user,
            is_active=True,  # Sirf videos
        ).order_by('-views', '-created_at')[:12]  # Top 12 by views, newest
        
        serializer = FileSerializer(files, many=True, context={'request': request})
        return Response({'files': serializer.data})
    except Exception as e:
        return Response({'error': str(e)}, status=404)

# ========================
# VIEW INCREMENT ENDPOINT (FOR FLUTTER APP)
# ========================
@api_view(['POST'])
@permission_classes([AllowAny])
def increment_view(request, short_code):
    try:
        # File fetch
        file_obj = get_object_or_404(
            UserFile,
            short_code=short_code,
            is_active=True
        )

        ip = get_client_ip(request)

        # =========================
        # ALWAYS COUNT VIEW
        # =========================
        file_obj.views += 1
        file_obj.unique_views += 1   # optional but useful for stats

        # =========================
        # EARNINGS CALCULATION
        # =========================
        settings = SiteSettings.get_settings()
        rate_per_1000 = settings.earning_per_1000_views or Decimal('1.0000')

        incremental_earning = calculate_earnings_per_1000_views(
            1,
            rate_per_1000
        )

        file_obj.earnings += incremental_earning

        # Save file stats
        file_obj.save(update_fields=[
            'views',
            'unique_views',
            'earnings'
        ])

        # =========================
        # USER EARNINGS UPDATE
        # =========================
        user = file_obj.user
        user.pending_earnings += incremental_earning
        user.total_earnings += incremental_earning

        user.save(update_fields=[
            'pending_earnings',
            'total_earnings'
        ])

        # =========================
        # STORE VIEW LOG (OPTIONAL ANALYTICS)
        # =========================
        FileView.objects.create(
            file=file_obj,
            ip_address=ip,
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )

        # =========================
        # RETURN UPDATED DATA
        # =========================
        file_obj.refresh_from_db()

        serializer = FileSerializer(
            file_obj,
            context={'request': request}
        )

        return Response(serializer.data, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=400)

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

        # ✅ SAFE SiteSettings fetch
        settings = SiteSettings.objects.first()
        if not settings:
            settings = SiteSettings.objects.create()

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
# WITHDRAWALS (WITH EMAIL VERIFICATION CHECK)
# ========================
# core/views.py → CreateWithdrawalView replace या add करें

class CreateWithdrawalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        
        # Email verification check
        if not user.email_verified:
            return Response({"error": "Please verify your email before withdrawing"}, status=400)

        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method')
        payment_details = request.data.get('payment_details')

        if not all([amount, payment_method, payment_details]):
            return Response({"error": "All fields are required"}, status=400)

        try:
            amount = Decimal(amount)
        except:
            return Response({"error": "Invalid amount"}, status=400)

        settings = SiteSettings.get_settings()
        if amount < settings.min_withdrawal:
            return Response({"error": f"Minimum withdrawal is ${settings.min_withdrawal}"}, status=400)

        # Calculate withdrawable balance (use billing summary logic)
        billing = billing_summary_logic(user)  # आप billing_summary view से logic copy कर सकते हैं
        if amount > billing['withdrawable_balance']:
            return Response({"error": "Insufficient balance"}, status=400)

        Withdrawal.objects.create(
            user=user,
            amount=amount,
            payment_method=payment_method,
            payment_details=payment_details
        )

        return Response({"message": "Withdrawal request created successfully!"}, status=201)


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
        file_count=Count('files'),
        view_earnings=Sum('files__earnings'),
        download_earnings=Sum('files__download_earnings')
    )

    data = []

    for u in users:
        total = (u.view_earnings or 0) + (u.download_earnings or 0)

        data.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,

            # REAL CALCULATED EARNINGS
            "total_earnings": float(total),

            # Existing fields
            "pending_earnings": float(u.pending_earnings or 0),
            "paid_earnings": float(u.paid_earnings or 0),

            "file_count": u.file_count,
            "is_active": u.is_active,
            "created_at": u.created_at
        })

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
            # Ye line add kar do ↓↓↓
            "short_code": f.short_code,
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
@permission_classes([IsSuperuser])  # या [IsAuthenticated] अगर सिर्फ लॉगिन काफी है
def admin_settings(request):
    """
    Admin-only endpoint to GET and PATCH global SiteSettings.
    Supports all current fields + custom ad script for third-party networks.
    """
    settings_obj = SiteSettings.get_settings()  # Singleton instance

    if request.method == 'GET':
        # Return all current settings as JSON (frontend admin page के लिए)
        return Response({
            # Earnings
            "earning_per_view": float(settings_obj.earning_per_view or 0),
            "earning_per_download": float(settings_obj.earning_per_download or 0),
            "earning_per_1000_views": float(settings_obj.earning_per_1000_views or 0),
            "earning_per_1000_downloads": float(settings_obj.earning_per_1000_downloads or 0),

            # Withdrawal
            "min_withdrawal": float(settings_obj.min_withdrawal or 10.00),

            # General
            "site_name": settings_obj.site_name or "Royaldisk",

            # Legacy Ads (AdMob / Meta / AdSense) - optional, रख सकते हो
            "admob_banner_id": settings_obj.admob_banner_id or "",
            "admob_interstitial_id": settings_obj.admob_interstitial_id or "",
            "meta_banner_placement_id": settings_obj.meta_banner_placement_id or "",
            "meta_interstitial_placement_id": settings_obj.meta_interstitial_placement_id or "",
            "adsense_client_id": settings_obj.adsense_client_id or "",

            # Social Links
            "instagram_link": settings_obj.instagram_link or "",
            "telegram_link": settings_obj.telegram_link or "",
            "youtube_link": settings_obj.youtube_link or "",

            # SEO & Sharing
            "seo_title": settings_obj.seo_title or "Royaldisk - Earn Money by Sharing Files",
            "seo_description": settings_obj.seo_description or "Upload files, share links, and earn real money from views and downloads.",
            "seo_keywords": settings_obj.seo_keywords or "file sharing, earn money online, cloud storage, upload files, Royaldisk",
            "seo_og_image": settings_obj.seo_og_image or "",
            "favicon_url": settings_obj.favicon_url or "",

            # ★★★ Custom Third-Party Ad Script (नया फीचर) ★★★
            "custom_ad_script": settings_obj.custom_ad_script or "",
            "custom_ad_script_enabled": settings_obj.custom_ad_script_enabled,
        })

    elif request.method == 'PATCH':
        # Update only the fields that are sent in the request (partial update)

        # Earnings
        if 'earning_per_view' in request.data:
            settings_obj.earning_per_view = Decimal(str(request.data['earning_per_view']))
        if 'earning_per_download' in request.data:
            settings_obj.earning_per_download = Decimal(str(request.data['earning_per_download']))
        if 'earning_per_1000_views' in request.data:
            settings_obj.earning_per_1000_views = Decimal(str(request.data['earning_per_1000_views']))
        if 'earning_per_1000_downloads' in request.data:
            settings_obj.earning_per_1000_downloads = Decimal(str(request.data['earning_per_1000_downloads']))

        # Withdrawal
        if 'min_withdrawal' in request.data:
            settings_obj.min_withdrawal = Decimal(str(request.data['min_withdrawal']))

        # General
        if 'site_name' in request.data:
            settings_obj.site_name = str(request.data['site_name'])[:100].strip() or "Royaldisk"

        # Legacy Ads
        if 'admob_banner_id' in request.data:
            settings_obj.admob_banner_id = str(request.data['admob_banner_id'])[:100].strip()
        if 'admob_interstitial_id' in request.data:
            settings_obj.admob_interstitial_id = str(request.data['admob_interstitial_id'])[:100].strip()
        if 'meta_banner_placement_id' in request.data:
            settings_obj.meta_banner_placement_id = str(request.data['meta_banner_placement_id'])[:100].strip()
        if 'meta_interstitial_placement_id' in request.data:
            settings_obj.meta_interstitial_placement_id = str(request.data['meta_interstitial_placement_id'])[:100].strip()
        if 'adsense_client_id' in request.data:
            settings_obj.adsense_client_id = str(request.data['adsense_client_id'])[:100].strip()

        # Social Links
        if 'instagram_link' in request.data:
            settings_obj.instagram_link = str(request.data['instagram_link'])[:500].strip()
        if 'telegram_link' in request.data:
            settings_obj.telegram_link = str(request.data['telegram_link'])[:500].strip()
        if 'youtube_link' in request.data:
            settings_obj.youtube_link = str(request.data['youtube_link'])[:500].strip()

        # SEO Fields
        if 'seo_title' in request.data:
            settings_obj.seo_title = str(request.data['seo_title'])[:200].strip()
        if 'seo_description' in request.data:
            settings_obj.seo_description = str(request.data['seo_description'])[:300].strip()
        if 'seo_keywords' in request.data:
            settings_obj.seo_keywords = str(request.data['seo_keywords'])[:500].strip()
        if 'seo_og_image' in request.data:
            settings_obj.seo_og_image = str(request.data['seo_og_image'])[:500].strip()
        if 'favicon_url' in request.data:
            settings_obj.favicon_url = str(request.data['favicon_url'])[:500].strip()

        # ★★★ Custom Ad Script Fields (मुख्य बदलाव यहीं) ★★★
        if 'custom_ad_script' in request.data:
            settings_obj.custom_ad_script = str(request.data['custom_ad_script']).strip()  # कोई लंबाई लिमिट नहीं, TextField है
        if 'custom_ad_script_enabled' in request.data:
            settings_obj.custom_ad_script_enabled = bool(request.data['custom_ad_script_enabled'])

        # Save to database
        settings_obj.save()

        # Success response (frontend को बताने के लिए)
        return Response({
            "message": "Settings updated successfully!",
            "success": True,
            # Optional: updated custom fields भी वापस भेज सकते हो
            "custom_ad_script": settings_obj.custom_ad_script,
            "custom_ad_script_enabled": settings_obj.custom_ad_script_enabled,
        }, status=status.HTTP_200_OK)

    return Response({"error": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

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
# PUBLIC ADMOB + META + ADSENSE IDs
# ========================
@api_view(['GET'])
@permission_classes([AllowAny])
def get_admob_ids(request):
    """
    Frontend & Flutter app will fetch AdMob, Meta & AdSense IDs from here
    """
    settings = SiteSettings.get_settings()

    return Response({
        "banner_id": settings.admob_banner_id or "ca-app-pub-3940256099942544/6300978111",
        "interstitial_id": settings.admob_interstitial_id or "ca-app-pub-3940256099942544/1033173712",
        "meta_banner_id": settings.meta_banner_placement_id or "",
        "meta_interstitial_id": settings.meta_interstitial_placement_id or "",
        "adsense_client_id": settings.adsense_client_id.strip(),
        'instagram_link': settings.instagram_link or "",
        'telegram_link': settings.telegram_link or "",
        'youtube_link': settings.youtube_link or "",
    })


def health_check(request):
    return JsonResponse({"status": "ok"})

def migrate_authtoken(request):
    if request.GET.get("key") != "super-system-secret-12345":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    call_command("migrate", "authtoken")
    return JsonResponse({"status": "authtoken migrated"})


def run_migrate(request):
    if request.GET.get("key") != "super-system-secret-12345":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    before = io.StringIO()
    migrate_out = io.StringIO()
    after = io.StringIO()

    try:
        # BEFORE
        call_command("showmigrations", "core", stdout=before)

        # NORMAL migrate (Django smartly decides)
        call_command(
            "migrate",
            "core",
            interactive=False,
            stdout=migrate_out,
            stderr=migrate_out
        )

        # AFTER
        call_command("showmigrations", "core", stdout=after)

        return JsonResponse({
            "status": "CORE MIGRATION CHECK DONE",
            "before_migrations": before.getvalue(),
            "migration_output": migrate_out.getvalue(),
            "after_migrations": after.getvalue(),
        })

    except Exception as e:
        return JsonResponse({
            "status": "FAILED",
            "error": str(e),
            "before_migrations": before.getvalue(),
            "migration_output": migrate_out.getvalue(),
        }, status=500)

def force_sync_db(request):
    if request.GET.get("key") != "super-system-secret-12345":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    out = io.StringIO()
    try:
        call_command("migrate", run_syncdb=True, interactive=False, stdout=out)
        return JsonResponse({
            "status": "syncdb forced",
            "output": out.getvalue()
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def run_makemigrations(request):
    key = request.GET.get("key")
    if key != "super-system-secret-12345":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    call_command("makemigrations")
    return JsonResponse({"status": "makemigrations done"})


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

        return Response({
            "token": token,
            "expire": expire,
            "signature": signature
        })

    except Exception as e:
        return Response({"error": "Auth generation failed"}, status=500)
    
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    if not user.check_password(old_password):
        return Response({"error": "Current password is incorrect"}, status=400)

    user.set_password(new_password)
    user.save()
    return Response({"message": "Password changed successfully"})

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def change_email(request):
    user = request.user
    current_password = request.data.get('current_password')
    new_email = request.data.get('new_email')

    if not user.check_password(current_password):
        return Response({"error": "Current password is incorrect"}, status=400)

    if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
        return Response({"error": "Email already in use"}, status=400)

    user.email = new_email
    user.email_verified = False  # नया email → re-verify करवाओ
    user.save()
    return Response({"message": "Email updated successfully. Please re-verify your email."})

@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_my_file(request, pk):
    file_obj = get_object_or_404(UserFile, pk=pk, user=request.user)  # Sirf apni file
    file_obj.delete()
    return Response({"message": "File deleted successfully"})

@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    email = request.data.get('email')
    if not email:
        return Response({"error": "Email is required"}, status=400)

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        # Security: Same message even if user not exist (prevent enumeration)
        return Response({"message": "If email exists, OTP has been sent."})

    # Generate OTP
    otp = ''.join(random.choices(string.digits, k=6))
    user.email_otp = otp
    user.email_otp_expiry = timezone.now() + timedelta(minutes=10)
    user.save(update_fields=['email_otp', 'email_otp_expiry'])

    # Send Email via Brevo
    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        return Response({"error": "Email service not configured"}, status=500)

    url = "https://api.brevo.com/v3/smtp/email"
    payload = {
        "sender": {"name": "Royaldisk", "email": "Royaldisk01@gmail.com"},
        "to": [{"email": user.email, "name": user.username}],
        "subject": "Royaldisk - Password Reset OTP",
        "htmlContent": f"""
        <html>
          <body>
            <h2>Password Reset Request</h2>
            <p>Your OTP for password reset is: <strong style="font-size:1.5em">{otp}</strong></p>
            <p>This OTP is valid for <strong>10 minutes</strong> only.</p>
            <p>If you didn't request this, ignore this email.</p>
            <br>
            <p>Thanks,<br>Royaldisk Team</p>
          </body>
        </html>
        """
    }
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return Response({"message": "If email exists, OTP has been sent."})
    except requests.exceptions.RequestException as e:
        print("Brevo Error:", e)
        return Response({"error": "Failed to send OTP"}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    email = request.data.get('email')
    otp = request.data.get('otp')
    new_password = request.data.get('new_password')

    if not all([email, otp, new_password]):
        return Response({"error": "All fields required"}, status=400)

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return Response({"error": "Invalid request"}, status=400)

    if user.email_otp != otp:
        return Response({"error": "Invalid OTP"}, status=400)

    if timezone.now() > user.email_otp_expiry:
        return Response({"error": "OTP expired"}, status=400)

    # Success: Set new password
    user.set_password(new_password)
    user.email_otp = None
    user.email_otp_expiry = None
    user.save()

    return Response({"message": "Password reset successfully! You can now login."})

# core/views.py → end mein add karo

@api_view(['GET'])
@permission_classes([AllowAny])
def get_active_notification(request):
    try:
        notification = BroadcastNotification.objects.filter(
            is_active=True
        ).exclude(expires_at__lt=timezone.now()).first()

        if notification and not notification.is_expired():
            serializer = BroadcastNotificationSerializer(notification)
            return Response(serializer.data)
        else:
            return Response({"detail": "No active notification"}, status=404)
    except:
        return Response({"detail": "No active notification"}, status=404)


@api_view(['GET', 'POST'])
@permission_classes([IsSuperuser])
def admin_notifications(request):
    if request.method == 'GET':
        notifications = BroadcastNotification.objects.all()
        serializer = BroadcastNotificationSerializer(notifications, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = BroadcastNotificationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsSuperuser])
def admin_notification_detail(request, pk):
    try:
        notification = BroadcastNotification.objects.get(pk=pk)
    except BroadcastNotification.DoesNotExist:
        return Response({"error": "Not found"}, status=404)

    if request.method == 'PATCH':
        serializer = BroadcastNotificationSerializer(notification, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    elif request.method == 'DELETE':
        notification.delete()
        return Response({"message": "Deleted successfully"})

@api_view(['POST'])
@permission_classes([AllowAny])
def increment_download(request, short_code):
    try:
        file_obj = get_object_or_404(UserFile, short_code=short_code, is_active=True)
        ip = get_client_ip(request)

        today = timezone.now().date()
        already_downloaded = FileDownload.objects.filter(
            file=file_obj, ip_address=ip, downloaded_at__date=today
        ).exists()

        if not already_downloaded:
            file_obj.downloads += 1
            file_obj.unique_downloads += 1

            settings = SiteSettings.get_settings()
            rate_per_1000_dl = settings.earning_per_1000_downloads or Decimal('1.0000')
            earning = calculate_earnings_per_1000_downloads(file_obj.downloads, rate_per_1000_dl)

            file_obj.download_earnings = earning
            file_obj.save(update_fields=['downloads', 'unique_downloads', 'download_earnings'])

            incremental = calculate_earnings_per_1000_downloads(1, rate_per_1000_dl)
            user = file_obj.user
            user.pending_earnings += incremental
            user.total_earnings += incremental
            user.save(update_fields=['pending_earnings', 'total_earnings'])

            FileDownload.objects.create(file=file_obj, ip_address=ip)

        return Response({"message": "Download counted"}, status=200)
    except Exception as e:
        return Response({"error": str(e)}, status=400)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def billing_summary(request):
    user = request.user

    # =====================
    # FILE LEVEL CALCULATION
    # =====================
    files = UserFile.objects.filter(user=user)

    total_views = files.aggregate(v=Sum('views'))['v'] or 0
    total_downloads = files.aggregate(d=Sum('downloads'))['d'] or 0

    view_earnings = files.aggregate(e=Sum('earnings'))['e'] or Decimal('0')
    download_earnings = files.aggregate(e=Sum('download_earnings'))['e'] or Decimal('0')

    total_earnings = view_earnings + download_earnings

    # =====================
    # WITHDRAWALS
    # =====================
    withdrawn = Withdrawal.objects.filter(
        user=user,
        status='paid'
    ).aggregate(a=Sum('amount'))['a'] or Decimal('0')

    pending_withdrawals = Withdrawal.objects.filter(
        user=user,
        status='pending'
    ).aggregate(a=Sum('amount'))['a'] or Decimal('0')

    # =====================
    # FINAL BALANCE
    # =====================
    withdrawable_balance = total_earnings - withdrawn - pending_withdrawals
    if withdrawable_balance < 0:
        withdrawable_balance = Decimal('0')

    return Response({
        "views": total_views,
        "downloads": total_downloads,

        "view_earnings": round(view_earnings, 5),
        "download_earnings": round(download_earnings, 5),

        "total_earnings": round(total_earnings, 5),

        "withdrawn_amount": round(withdrawn, 5),
        "pending_withdrawals": round(pending_withdrawals, 5),

        "withdrawable_balance": round(withdrawable_balance, 5)
    })
