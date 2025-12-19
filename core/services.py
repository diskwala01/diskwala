# core/services.py
# CLEANED VERSION FOR IMAGEKIT DIRECT UPLOAD (NO SERVER PROCESSING)

# ==============================
# EARNINGS CALCULATION (ONLY THIS IS USED NOW)
# ==============================
def calculate_earnings_per_view(views):
    """
    Calculate earnings based on tiered view system (per 1000 views)
    """
    if views >= 100000:
        rate = 0.004
    elif views >= 50000:
        rate = 0.0035
    elif views >= 10000:
        rate = 0.003
    else:
        rate = 0.0025

    return round((views / 1000) * rate, 4)


# Optional: File type detection (ab frontend se aata hai, lekin safe rakho)
def detect_file_type(file_name_or_type):
    """
    Dummy function - file_type ab frontend se direct aata hai
    """
    return "other"