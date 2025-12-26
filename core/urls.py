# core/urls.py
# FINAL & COMPLETE — User + Admin + System Endpoints

from django.urls import path
from rest_framework.authtoken.views import ObtainAuthToken

from .views import (
    # ========================
    # USER AUTH & DASHBOARD
    # ========================
    RegisterView,
    ProfileView,
    UploadFileView,
    MyFilesView,
    AnalyticsView,
    CreateWithdrawalView,
    WithdrawalListView,
    update_file,
    verify_email_otp,
    delete_my_file,
    send_email_otp,
    change_password,
    change_email,
    public_file_view,
    public_bot_links,
    get_admob_ids,
    imagekit_auth,
    force_sync_db,
    migrate_authtoken,
    forgot_password,
    reset_password,
    user_files_view,
    increment_view,
    admin_notifications,
    admin_notification_detail,
    get_active_notification,

    # ========================
    # ADMIN AUTH & PANEL
    # ========================
    AdminLoginView,
    admin_users,
    admin_all_files,
    admin_stats,
    admin_withdrawals,
    admin_global_stats,
    admin_logs,
    admin_settings,
    admin_ban_user,
    admin_delete_file,
    admin_approve_withdrawal,
    admin_reject_withdrawal,
    admin_manual_payout,
    admin_bot_links,
    create_superuser,
    health_check,
    admin_manage_bot_link,
)

# ========================
# SYSTEM / INTERNAL VIEWS
# ========================

urlpatterns = [

    # =====================================================
    # AUTHENTICATION
    # =====================================================
    path("auth/token/", ObtainAuthToken.as_view(), name="get_token"),
    path("register/", RegisterView.as_view(), name="register"),
    path("admin/login/", AdminLoginView.as_view(), name="admin_login"),

    # =====================================================
    # USER APIs
    # =====================================================
    path("profile/", ProfileView.as_view(), name="profile"),
    path("upload/", UploadFileView.as_view(), name="upload"),
    path("imagekit/auth/", imagekit_auth, name="imagekit_auth"),
    path("system/migrate-authtoken/", migrate_authtoken),
    path("my-files/", MyFilesView.as_view(), name="my_files"),
    path("analytics/", AnalyticsView.as_view(), name="analytics"),
    path("withdraw/", CreateWithdrawalView.as_view(), name="withdraw"),
    path("withdrawals/", WithdrawalListView.as_view(), name="withdrawals"),
    path("admob-ids/", get_admob_ids, name="admob_ids"),

    # File update (title / thumbnail etc.)
    path("files/<int:pk>/update/", update_file, name="update_file"),

    # Public file access (short URL)
    path("f/<str:short_code>/", public_file_view, name="public_file_view"),

    # Public bot links
    path("bots/", public_bot_links, name="public_bots"),

    # =====================================================
    # ADMIN PANEL APIs (SUPERUSER ONLY)
    # =====================================================
    path("admin/users/", admin_users, name="admin_users"),
    path("admin/all-files/", admin_all_files, name="admin_all_files"),
    path("admin/stats/", admin_stats, name="admin_stats"),
    path("admin/withdrawals/", admin_withdrawals, name="admin_withdrawals"),

    # Extra admin pages
    path("admin/global-stats/", admin_global_stats, name="admin_global_stats"),
    path("admin/logs/", admin_logs, name="admin_logs"),
    path("admin/settings/", admin_settings, name="admin_settings"),

    # User moderation
    path("admin/user/<int:pk>/ban/", admin_ban_user, name="admin_ban_user"),

    # Bot management
    path("admin/bots/", admin_bot_links, name="admin_bot_links"),
    path("admin/bots/manage/", admin_manage_bot_link, name="admin_manage_bot"),

    # File delete
    path("admin/file/<int:pk>/", admin_delete_file, name="admin_delete_file"),

    # Withdrawal actions
    path(
        "admin/withdrawal/<int:pk>/approve/",
        admin_approve_withdrawal,
        name="admin_approve_withdrawal",
    ),
    path(
        "admin/withdrawal/<int:pk>/reject/",
        admin_reject_withdrawal,
        name="admin_reject_withdrawal",
    ),

    # Manual payout
    path(
        "admin/manual-payout/",
        admin_manual_payout,
        name="admin_manual_payout",
    ),

    # =====================================================
    # SYSTEM / INTERNAL (SECURED)
    # =====================================================
    path(
        "system/create-superuser/",
        create_superuser,
        name="system_create_superuser",
    ),
    path("change-password/", change_password, name="change_password"),
    path("change-email/", change_email, name="change_email"),
    path("files/<int:pk>/delete/", delete_my_file, name="delete_my_file"),
    path("health/", health_check, name="health_check"),
    path("send-email-otp/", send_email_otp, name="send_email_otp"),
    path("verify-email/", verify_email_otp, name="verify_email"),
    path("system/force-sync/", force_sync_db),
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("reset-password/", reset_password, name="reset_password"),
    path("user-files/<str:username>/", user_files_view, name="user_files"),
    path('view/<str:short_code>/', increment_view, name='increment_view'),
    # core/urls.py → urlpatterns mein add karo
    path("admin/notifications/", admin_notifications, name="admin_notifications"),
    path("admin/notifications/<int:pk>/", admin_notification_detail, name="admin_notification_detail"),
    path("admin/active-notification/", get_active_notification, name="active_notification"),

]
