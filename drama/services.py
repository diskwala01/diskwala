# drama/services.py  (or append to core/services.py)

from decimal import Decimal
from core.services import calculate_earnings_per_1000_views   # reuse

def update_drama_earnings(drama):
    """ Recalculate total earnings from all episodes """
    total_view_earn = Decimal('0')
    for ep in drama.episodes.all():
        total_view_earn += ep.view_earnings
    
    drama.view_earnings = total_view_earn
    drama.earnings = total_view_earn   # can add download_earnings later
    drama.save(update_fields=['earnings', 'view_earnings'])


def calculate_episode_view_earning(increment: int = 1) -> Decimal:
    from core.models import SiteSettings
    settings = SiteSettings.get_settings()
    rate = settings.earning_per_1000_views or Decimal('1.0000')   # same as files for now
    return calculate_earnings_per_1000_views(increment, rate)