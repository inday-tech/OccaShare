import os

# Ideally, these should be environment variables for security.
# For simplicity in this dev environment, we define them here.

class Settings:
    # EMAIL CONFIGURATION
    MAIL_USERNAME = "dadaycaragay@gmail.com" 
    MAIL_PASSWORD = "ypgn kdud mvzs jhbo" 
    MAIL_FROM = "dadaycaragay@gmail.com" 
    MAIL_PORT = 587
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_TLS = True
    MAIL_SSL = False

    # SOCIAL LOGIN CONFIGURATION (Real)
    FACEBOOK_CLIENT_ID = "796095886083019"
    FACEBOOK_CLIENT_SECRET = "999b6616e229760dc1a254fb097dfa36" 
    

settings = Settings()
