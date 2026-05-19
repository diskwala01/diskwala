# drama/services.py

from decimal import Decimal
from core.services import calculate_earnings_per_1000_views
from core.models import SiteSettings


def calculate_episode_view_earning(increment: int = 1) -> Decimal:
    """Per 1000 views rate use करके earning calculate करो"""
    settings = SiteSettings.get_settings()
    rate_per_1000 = settings.earning_per_1000_views or Decimal('1.0000')
    return calculate_earnings_per_1000_views(increment, rate_per_1000)


def update_drama_earnings(drama):
    """Drama ke total earnings = sab episodes ke earnings ka sum"""
    total_earn = Decimal('0')
    for ep in drama.episodes.all():
        total_earn += ep.earnings or Decimal('0')
    
    drama.earnings = total_earn
    drama.view_earnings = total_earn
    drama.save(update_fields=['earnings', 'view_earnings'])