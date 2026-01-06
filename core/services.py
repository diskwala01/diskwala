# core/services.py

from decimal import Decimal

def calculate_earnings_per_1000_views(views: int, rate_per_1000: Decimal) -> Decimal:
    """
    Calculate earnings based on per 1000 views rate
    Example: 2500 views with $1 per 1000 → $2.5
    """
    if views <= 0:
        return Decimal('0.0000')
    thousands = Decimal(views) / Decimal('1000')
    return round(thousands * rate_per_1000, 4)


def calculate_earnings_per_1000_downloads(downloads: int, rate_per_1000: Decimal) -> Decimal:
    """
    Same logic for downloads
    """
    if downloads <= 0:
        return Decimal('0.0000')
    thousands = Decimal(downloads) / Decimal('1000')
    return round(thousands * rate_per_1000, 4)


# Optional: File type detection (ab frontend se aata hai, lekin safe rakho)
def detect_file_type(file_name_or_type):
    """
    Dummy function - file_type ab frontend se direct aata hai
    """
    return "other"