# core/serializers.py → UPDATED FOR IMAGEKIT EXTERNAL URLS

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserFile, Withdrawal, BotLink

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    # Manually override URL fields to allow empty strings & convert to None
    whatsapp = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    facebook = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    instagram = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    twitter = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    youtube = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    discord = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    telegram_channel = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    support_link = serializers.URLField(required=False, allow_blank=True, allow_null=True)

    # Brand name ko bhi blank allow karo
    brand_name = serializers.CharField(required=False, allow_blank=True, max_length=100)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'brand_name',
            'whatsapp', 'facebook', 'instagram', 'twitter',
            'youtube', 'discord', 'website',
            'telegram_channel', 'support_link', 'allow_download',
            'total_earnings', 'pending_earnings', 'paid_earnings',
            'api_key', 'email_verified'
        ]
        read_only_fields = ['total_earnings', 'pending_earnings', 'paid_earnings', 'api_key']

    # Optional: Empty strings ko None bana do (database clean rahega)
    def to_internal_value(self, data):
        for field in ['whatsapp', 'facebook', 'instagram', 'twitter', 'youtube',
                      'discord', 'website', 'telegram_channel', 'support_link']:
            if data.get(field) == '':
                data[field] = None
        return super().to_internal_value(data)


class FileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    uploaded_by = serializers.CharField(source='user.username', read_only=True)  # ← YE NAYA ADD KARO!
    downloads = serializers.IntegerField(read_only=True)
    download_earnings = serializers.DecimalField(max_digits=10, decimal_places=4, read_only=True)

    class Meta:
        model = UserFile
        fields = [
            'id', 'title', 'file_url', 'thumbnail_url', 'uploaded_by',  # ← uploaded_by add kiya
            'file_type', 'views', 'short_code', 'is_active', 'created_at',
            'downloads', 'download_earnings', 'allow_download'
        ]

    def get_file_url(self, obj):
        return obj.external_file_url

    def get_thumbnail_url(self, obj):
        if obj.external_thumbnail_url:
            return obj.external_thumbnail_url
        if obj.file_type == 'image':
            return obj.external_file_url
        return "https://via.placeholder.com/300x200/333333/ffffff?text=No+Preview"
        
    def get_public_link(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f"/f/{obj.short_code}/")
        return f"/f/{obj.short_code}/"


class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = '__all__'
        read_only_fields = ['user', 'status', 'requested_at', 'processed_at']


class BotLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotLink
        fields = '__all__'