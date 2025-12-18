from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserFile, FileView, Withdrawal

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'brand_name', 'total_earnings', 'date_joined']
    readonly_fields = ['api_key', 'total_earnings', 'pending_earnings']

admin.site.register(UserFile)
admin.site.register(FileView)
admin.site.register(Withdrawal)