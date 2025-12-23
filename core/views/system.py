import os
from django.http import JsonResponse, HttpResponseForbidden
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.conf import settings

SECRET = os.environ.get("SYSTEM_SECRET", "dev-secret")

def check_secret(request):
    return request.GET.get("key") == SECRET

def run_full_migration(request):
    if request.GET.get("key") != settings.SYSTEM_SECRET:
        return HttpResponseForbidden("Forbidden")

    try:
        call_command("makemigrations")
        call_command("migrate")
        return JsonResponse({
            "status": "ok",
            "message": "makemigrations + migrate completed"
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "error": str(e)
        }, status=500)


# 1️⃣ Migration URL
def run_migrations(request):
    if not check_secret(request):
        return HttpResponseForbidden("Forbidden")

    try:
        call_command("makemigrations")
        call_command("migrate")
        return JsonResponse({"status": "ok", "message": "Migrations completed"})
    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)})


# 2️⃣ Superuser create URL
def create_superuser(request):
    if not check_secret(request):
        return HttpResponseForbidden("Forbidden")

    User = get_user_model()

    username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
    email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin123")

    if User.objects.filter(username=username).exists():
        return JsonResponse({"status": "exists", "message": "Superuser already exists"})

    User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )

    return JsonResponse({"status": "ok", "message": "Superuser created"})


# 3️⃣ Health Check URL
def health_check(request):
    return JsonResponse({
        "status": "ok",
        "service": "running"
    })
