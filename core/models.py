# core/models.py → UPDATED FOR IMAGEKIT.IO DIRECT UPLOAD (NO SERVER STORAGE)

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
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
    
    # REMOVED: file = models.FileField(...)
    # REMOVED: thumbnail = models.ImageField(...)
    
    # NEW: External ImageKit URLs
    external_file_url = models.URLField(
        max_length=500,
        blank=True,        # ← Yeh add karo (form mein optional)
        null=True,         # ← Yeh add karo (database mein NULL allow karega)
        default="",        # ← Optional: empty string as default
        help_text="Direct ImageKit URL of the uploaded file"
    )
    external_thumbnail_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        default="",        # ya None rakh sakte ho
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
        return reverse('public_file_view', kwargs={'short_code': self.short_code})  # url name match karo


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


class Withdrawal(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected')
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default="UPI/PayPal")
    payment_details = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.amount} - {self.status}"


class SiteSettings(models.Model):
    earning_per_view = models.DecimalField(max_digits=8, decimal_places=6, default=0.002500)
    min_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    site_name = models.CharField(max_length=100, default="dSkWala")

    adsense_client_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Google AdSense Client ID (ca-pub-XXXXXXXXXXXXXXXX)"
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