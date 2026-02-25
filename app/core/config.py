import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # CORE CONFIG
    SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-me")
    
    # EMAIL CONFIGURATION
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "dadaycaragay@gmail.com")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "ypgn kdud mvzs jhbo")
    MAIL_FROM = os.getenv("MAIL_FROM", "dadaycaragay@gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_TLS = os.getenv("MAIL_TLS", "True") == "True"
    MAIL_SSL = os.getenv("MAIL_SSL", "False") == "True"

    # SOCIAL LOGIN CONFIGURATION
    FACEBOOK_CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID", "")
    FACEBOOK_CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET", "")
    
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    INSTAGRAM_CLIENT_ID = os.getenv("INSTAGRAM_CLIENT_ID", "")
    INSTAGRAM_CLIENT_SECRET = os.getenv("INSTAGRAM_CLIENT_SECRET", "")

settings = Settings()
