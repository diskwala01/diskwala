# core/models.py → UPDATED FOR IMAGEKIT.IO DIRECT UPLOAD (NO SERVER STORAGE)

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random
import string


def generate_api_key():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))


def generate_short_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


class User(AbstractUser):
    brand_name = models.CharField(max_length=100, blank=True, default="My Drive")
    
    # NEW: Multiple social links
    instagram = models.CharField(max_length=255, blank=True, null=True)
    whatsapp = models.CharField(max_length=255, blank=True, null=True)
    facebook = models.CharField(max_length=255, blank=True, null=True)
    twitter = models.CharField(max_length=255, blank=True, null=True)
    youtube = models.CharField(max_length=255, blank=True, null=True)
    website = models.CharField(max_length=255, blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    email_otp = models.CharField(max_length=6, blank=True, null=True)
    email_otp_expiry = models.DateTimeField(null=True, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    telegram_channel = models.URLField(blank=True, null=True)
    support_link = models.URLField(blank=True, null=True)
    api_key = models.CharField(max_length=100, unique=True, default=generate_api_key)
    allow_download = models.BooleanField(default=True)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    pending_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    paid_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='core_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='core_user_permissions_set',
        blank=True,
        help_text='Specific permissions for this user.',
    )

    def __str__(self):
        return self.username


class UserFile(models.Model):
    FILE_TYPE_CHOICES = (
        ('video', 'Video'),
        ('image', 'Image'),
        ('other', 'Other'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    
    # NEW: External ImageKit URLs
    external_file_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        default="",
        help_text="Direct ImageKit URL of the uploaded file"
    )
    external_thumbnail_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        default="",
        help_text="ImageKit thumbnail URL (auto-generated for videos or custom)"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    short_code = models.CharField(max_length=10, unique=True, default=generate_short_code)
    views = models.BigIntegerField(default=0)
    unique_views = models.BigIntegerField(default=0)
    earnings = models.DecimalField(max_digits=10, decimal_places=4, default=0.0000)
    allow_download = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Download related fields
    downloads = models.BigIntegerField(default=0)
    unique_downloads = models.BigIntegerField(default=0)
    download_earnings = models.DecimalField(max_digits=10, decimal_places=4, default=0.0000)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def public_url(self):
        from django.urls import reverse
        return reverse('public_file_view', kwargs={'short_code': self.short_code})


class FileView(models.Model):
    file = models.ForeignKey(UserFile, on_delete=models.CASCADE, related_name='file_views')
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=500, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('file', 'ip_address', 'viewed_at')
        indexes = [
            models.Index(fields=['file', 'ip_address', 'viewed_at']),
            models.Index(fields=['viewed_at']),
        ]


class FileDownload(models.Model):
    file = models.ForeignKey(UserFile, on_delete=models.CASCADE, related_name='file_downloads')
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=500, blank=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['file', 'ip_address', 'downloaded_at']),
            models.Index(fields=['downloaded_at']),
        ]

    def __str__(self):
        return f"Download: {self.file.title} by {self.ip_address}"


# core/models.py → Withdrawal model में ये changes करो

class Withdrawal(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected')
    )

    PAYMENT_METHOD_CHOICES = (
        ('upi', 'UPI'),
        ('bank', 'Bank Transfer'),
        # ('paypal', 'PayPal'),  # future ke liye
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # NEW FIELDS
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='upi')
    payment_details = models.JSONField(
        default=dict,
        help_text="Details like UPI ID, Bank Account, IFSC etc. stored as JSON"
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - ${self.amount} - {self.get_payment_method_display()} - {self.status}"


class SiteSettings(models.Model):
    earning_per_view = models.DecimalField(max_digits=8, decimal_places=6, default=0.002500)
    min_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    site_name = models.CharField(max_length=100, default="dSkWala")
    seo_title = models.CharField(max_length=200, blank=True, default="Royaldisk - Fast & Secure File Sharing")
    seo_description = models.CharField(max_length=300, blank=True, default="Upload and share files securely. Earn money from views and downloads on Royaldisk.")
    seo_keywords = models.CharField(max_length=500, blank=True, default="file sharing, upload files, earn money online, secure cloud storage")
    seo_og_image = models.URLField(blank=True, null=True, help_text="Default OG image URL for social sharing (e.g. logo or banner)")
    favicon_url = models.URLField(blank=True, null=True)
    earning_per_download = models.DecimalField(          # ← YE NAYA FIELD
        max_digits=8, 
        decimal_places=6, 
        default=0.001000, 
        help_text="Earning per unique download (e.g., 0.001000 = $1 per 1000 downloads)"
    )
    adsense_client_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Google AdSense Client ID (ca-pub-XXXXXXXXXXXXXXXX)"
    )
    earning_per_1000_views = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal('1.0000'),
        help_text="Earnings in USD per 1000 views (e.g. 1.00 = $1 per 1K views)"
    )
    earning_per_1000_downloads = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal('1.0000'),
        help_text="Earnings in USD per 1000 downloads"
    )
    meta_banner_placement_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Meta Audience Network Banner Placement ID"
    )
    meta_interstitial_placement_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Meta Audience Network Interstitial Placement ID"
    )

    admob_banner_id = models.CharField(
        max_length=100,
        blank=True,
        default="ca-app-pub-3940256099942544/6300978111",
        help_text="AdMob Banner Ad Unit ID"
    )
    admob_interstitial_id = models.CharField(
        max_length=100,
        blank=True,
        default="ca-app-pub-3940256099942544/1033173712",
        help_text="AdMob Interstitial Ad Unit ID"
    )

    # NEW: Global Social Links for "More" Screen in App
    instagram_link = models.URLField(
        blank=True,
        default="",
        help_text="Instagram profile or channel full URL (e.g. https://www.instagram.com/yourprofile)"
    )
    telegram_link = models.URLField(
        blank=True,
        default="",
        help_text="Telegram channel or group full URL (e.g. https://t.me/yourchannel)"
    )
    youtube_link = models.URLField(
        blank=True,
        default="",
        help_text="YouTube channel full URL (e.g. https://www.youtube.com/@yourchannel)"
    )

    class Meta:
        verbose_name = "Site Setting"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Global Site Settings"

    @classmethod
    def get_settings(cls):
        return cls.objects.first() or cls.objects.create()


class BotLink(models.Model):
    name = models.CharField(max_length=100, help_text="Bot ka naam (jaise TB Converter)")
    description = models.TextField(help_text="Kya kaam karta hai ye bot")
    telegram_username = models.CharField(max_length=100, help_text="@DiskWalaTBConverterBot")
    telegram_link = models.URLField(help_text="https://t.me/DiskWalaTBConverterBot")
    icon = models.CharField(max_length=50, default="link-2", help_text="Feather icon name")
    order = models.IntegerField(default=0, help_text="Display order")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

# core/models.py → SiteSettings ke neeche add karo

class BroadcastNotification(models.Model):
    DURATION_CHOICES = (
        (1, '1 Day'),
        (3, '3 Days'),
        (7, '7 Days'),
        (30, '30 Days'),
        (0, 'Forever'),  # 0 = no expiry
    )

    message = models.TextField(help_text="Notification message jo app mein dikhega")
    link_url = models.URLField(blank=True, null=True, help_text="Optional link (khali chhodne par sirf message dikhega)")
    link_text = models.CharField(max_length=50, blank=True, default="Open Link", help_text="Button ka text (jaise 'Visit Now')")
    duration_days = models.IntegerField(choices=DURATION_CHOICES, default=7, help_text="Kitne din tak dikhega")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.duration_days == 0:
            self.expires_at = None  # Forever
        else:
            self.expires_at = timezone.now() + timedelta(days=self.duration_days)
        super().save(*args, **kwargs)

    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.message[:50]