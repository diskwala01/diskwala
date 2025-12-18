# core/serializers.py

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
            'id', 'title', 'file', 'file_url', 'thumbnail_url',
            'file_type', 'views', 'short_code', 'is_active', 'created_at',
            'downloads', 'download_earnings'
        ]

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_thumbnail_url(self, obj):
        request = self.context.get('request')

        # Agar thumbnail hai (video ya manually upload kiya gaya)
        if obj.thumbnail:
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url

        # Agar thumbnail nahi hai lekin file image hai → file ko hi thumbnail bana do
        if obj.file and obj.file_type in ['image', 'psd']:
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url

        # Final fallback (agar kuch bhi nahi mila)
        return "https://via.placeholder.com/64x64.png?text=No+Image"

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

# core/serializers.py → end mein

class BotLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotLink
        fields = '__all__'