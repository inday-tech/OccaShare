import random
import string

def get_random_string(length=12):
    letters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(letters) for i in range(length))

def get_random_digits(length=6):
    return ''.join(random.choice(string.digits) for i in range(length))

def get_dashboard_url(role: str) -> str:
    """Returns the dashboard URL for a given role."""
    mapping = {
        "admin": "/admin/dashboard",
        "caterer": "/caterer/dashboard",
        "customer": "/customer/dashboard"
    }
    return mapping.get(role, "/")
