# drama/urls.py

from django.urls import path
from .views import (
    # Categories
    DramaCategoryListView,
    
    # Creator endpoints
    DramaListCreateView,
    DramaDetailView,
    DramaEpisodeCreateView,
    DramaEpisodeListView,
    
    # Public browsing
    PublicDramaListView,
    PublicDramaDetailView,
    creator_drama_earnings_summary,
    
    # View counting / analytics
    increment_drama_view,
    admin_delete_drama,
    increment_episode_view,
    
    # Admin moderation
    admin_pending_dramas,
    admin_dramas_list,
    admin_approve_drama,
    admin_reject_drama,
)

app_name = 'drama'  # optional - useful if you use reverse('drama:some-name')

urlpatterns = [
    # ───────────────────────────────────────────────
    # Categories (public - used when creating/editing drama)
    # ───────────────────────────────────────────────
    path('categories/', 
         DramaCategoryListView.as_view(), 
         name='drama-categories'),

     path('admin/dramas/', admin_dramas_list, name='admin-dramas-list'),

    # ───────────────────────────────────────────────
    # Creator – My dramas (authenticated only)
    # ───────────────────────────────────────────────
    path('my-dramas/', 
         DramaListCreateView.as_view(), 
         name='my-dramas-list-create'),

    path('my-dramas/<int:pk>/', 
         DramaDetailView.as_view(), 
         name='my-drama-detail'),

    # Episodes – add new episode to my drama
    path('my-dramas/<int:drama_pk>/episodes/', 
         DramaEpisodeCreateView.as_view(), 
         name='drama-episode-create'),

    # List episodes of my own drama (even if not approved yet)
    path('my-dramas/<int:drama_pk>/episodes/list/', 
         DramaEpisodeListView.as_view(), 
         name='my-drama-episodes'),

    # ───────────────────────────────────────────────
    # Public – Browse approved dramas & episodes
    # ───────────────────────────────────────────────
    path('dramas/', 
         PublicDramaListView.as_view(), 
         name='public-dramas-list'),
     path('admin/<int:pk>/delete/', 
         admin_delete_drama, 
         name='admin-delete-drama'),

    path('dramas/<str:short_code>/', 
         PublicDramaDetailView.as_view(), 
         name='public-drama-detail'),

    # ───────────────────────────────────────────────
    # View tracking (called from player / frontend)
    # ───────────────────────────────────────────────
    path('dramas/<str:short_code>/view/', 
         increment_drama_view, 
         name='increment-drama-view'),

    path('episodes/<int:episode_id>/view/', 
         increment_episode_view, 
         name='increment-episode-view'),

    # ───────────────────────────────────────────────
    # Admin panel – moderation endpoints (admin only)
    # ───────────────────────────────────────────────
    path('admin/pending/', 
         admin_pending_dramas, 
         name='admin-pending-dramas'),

    path('my-dramas/earnings-summary/',
         creator_drama_earnings_summary,
         name='creator-drama-earnings-summary'),

    path('admin/<int:pk>/approve/', 
         admin_approve_drama, 
         name='admin-approve-drama'),

    path('admin/<int:pk>/reject/', 
         admin_reject_drama, 
         name='admin-reject-drama'),
]