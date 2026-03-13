from django.contrib import admin
from .models import DramaCategory, Drama, DramaEpisode

@admin.register(DramaCategory)
class DramaCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'order']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Drama)
class DramaAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'status', 'category', 'approved_at', 'views']
    list_filter = ['status', 'category']
    search_fields = ['title', 'user__username']
    readonly_fields = ['short_code', 'approved_by', 'approved_at', 'total_episodes']


@admin.register(DramaEpisode)
class DramaEpisodeAdmin(admin.ModelAdmin):
    list_display = ['drama', 'episode_no', 'title', 'views', 'is_active']
    list_filter = ['drama', 'is_active']
    search_fields = ['drama__title', 'title']