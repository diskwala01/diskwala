# drama/models.py

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.utils.text import slugify

from core.models import generate_short_code  # assuming this exists in core/models.py

User = settings.AUTH_USER_MODEL


class DramaCategory(models.Model):
    name        = models.CharField(max_length=80, unique=True)
    slug        = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    order       = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "Drama Categories"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Drama(models.Model):
    STATUS_CHOICES = (
        ('pending',   'Pending Review'),
        ('approved',  'Approved'),
        ('rejected',  'Rejected'),
        ('archived',  'Archived'),
    )

    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dramas')
    title           = models.CharField(max_length=220)
    slug            = models.SlugField(max_length=260, unique=True, blank=True)
    short_code      = models.CharField(max_length=12, unique=True, default=generate_short_code)

    category        = models.ForeignKey(
        DramaCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dramas'
    )

    description     = models.TextField(blank=True)
    thumbnail_url   = models.URLField(max_length=500, blank=True, null=True)   # ImageKit external
    poster_url      = models.URLField(max_length=500, blank=True, null=True)   # bigger poster / banner

    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by     = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_dramas'
    )
    approved_at     = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True, help_text="Reason if rejected by admin")

    # Statistics & Earnings
    views           = models.PositiveBigIntegerField(default=0)
    total_episodes  = models.PositiveIntegerField(default=0)   # cache — updated via signal or save
    earnings        = models.DecimalField(max_digits=12, decimal_places=4, default=0.0000)
    view_earnings   = models.DecimalField(max_digits=12, decimal_places=4, default=0.0000)

    # Soft delete
    is_archived     = models.BooleanField(default=False, db_index=True)
    archived_at     = models.DateTimeField(null=True, blank=True)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-approved_at', '-created_at']
        indexes = [
            models.Index(fields=['status', 'is_archived']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.title} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:250]
        super().save(*args, **kwargs)

    def archive(self):
        """Soft-delete / archive this drama"""
        if not self.is_archived:
            self.is_archived = True
            self.archived_at = timezone.now()
            self.status = 'archived'  # optional: sync status
            self.save(update_fields=['is_archived', 'archived_at', 'status'])

    def restore(self):
        """Restore from archive (if needed)"""
        if self.is_archived:
            self.is_archived = False
            self.archived_at = None
            self.status = 'pending'   # or 'approved' — your choice
            self.save(update_fields=['is_archived', 'archived_at', 'status'])


class DramaEpisode(models.Model):
    drama           = models.ForeignKey(Drama, on_delete=models.CASCADE, related_name='episodes')
    episode_no      = models.PositiveSmallIntegerField()
    title           = models.CharField(max_length=220, blank=True)

    video_url       = models.URLField(max_length=500)                     # main video (ImageKit/external)
    thumbnail_url   = models.URLField(max_length=500, blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    description     = models.TextField(blank=True)
    views           = models.PositiveBigIntegerField(default=0)

    # Earnings
    earnings        = models.DecimalField(max_digits=10, decimal_places=4, default=0.0000)
    view_earnings   = models.DecimalField(max_digits=10, decimal_places=4, default=0.0000)

    is_active       = models.BooleanField(default=True)
    uploaded_at     = models.DateTimeField(auto_now_add=True)
    order           = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [['drama', 'episode_no']]
        ordering = ['order', 'episode_no']
        indexes = [
            models.Index(fields=['drama', 'episode_no']),
        ]

    def __str__(self):
        return f"{self.drama.title} - Ep {self.episode_no}"


# ───────────────────────────────────────────────
# View tracking (for unique views per day)
# ───────────────────────────────────────────────

class DramaView(models.Model):
    drama = models.ForeignKey(Drama, on_delete=models.CASCADE, related_name='view_logs')
    ip_address = models.GenericIPAddressField()
    viewed_at = models.DateTimeField(auto_now_add=True)
    view_date = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = (('drama', 'ip_address', 'view_date'),)
        indexes = [
            models.Index(fields=['drama', 'viewed_at']),
        ]


class EpisodeView(models.Model):
    episode = models.ForeignKey(DramaEpisode, on_delete=models.CASCADE, related_name='view_logs')
    ip_address = models.GenericIPAddressField()
    viewed_at = models.DateTimeField(auto_now_add=True)
    view_date = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = (('episode', 'ip_address', 'view_date'),)
        indexes = [
            models.Index(fields=['episode', 'viewed_at']),
        ]


# Optional: better default manager for active content only

class ActiveDramaManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_archived=False)


Drama.active_objects = ActiveDramaManager()