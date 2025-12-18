import hashlib

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def is_unique_view_today(file, ip):
    from datetime import date
    from .models import FileView
    return not FileView.objects.filter(
        file=file,
        ip_address=ip,
        viewed_at__date=date.today()
    ).exists()