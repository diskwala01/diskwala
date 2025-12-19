# core/serializers.py → UPDATED FOR IMAGEKIT EXTERNAL URLS

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserFile, Withdrawal, BotLink

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'brand_name', 'telegram_channel',
            'support_link', 'allow_download', 'total_earnings',
            'pending_earnings', 'paid_earnings', 'api_key'
        ]
        read_only_fields = ['total_earnings', 'pending_earnings', 'paid_earnings', 'api_key']


class FileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    downloads = serializers.IntegerField(read_only=True)
    download_earnings = serializers.DecimalField(max_digits=10, decimal_places=4, read_only=True)

    class Meta:
        model = UserFile
        fields = [
            'id', 'title', 'file_url', 'thumbnail_url',  # file field removed
            'file_type', 'views', 'short_code', 'is_active', 'created_at',
            'downloads', 'download_earnings', 'allow_download'
        ]

    def get_file_url(self, obj):
        return obj.external_file_url

    def get_thumbnail_url(self, obj):
        # Priority: custom thumbnail > auto-generated > file itself (for images) > placeholder
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