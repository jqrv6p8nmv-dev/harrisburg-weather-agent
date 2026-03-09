import os
from dotenv import load_dotenv

load_dotenv()

# Email configuration
# Brevo API (recommended for Digital Ocean - uses HTTPS instead of SMTP)
BREVO_API_KEY = os.getenv('BREVO_API_KEY')

# Mailgun API (alternative)
MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')

# SMTP configuration (legacy - blocked on Digital Ocean)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# Common email settings
# EMAIL_TO supports multiple addresses: EMAIL_TO=first@example.com,second@example.com
EMAIL_TO = [e.strip() for e in os.getenv('EMAIL_TO', '').split(',') if e.strip()]
EMAIL_FROM = os.getenv('EMAIL_FROM')

# NWS API configuration
NWS_STATION = os.getenv('NWS_STATION', 'KMDT')  # Harrisburg International Airport
NWS_USER_AGENT = os.getenv('NWS_USER_AGENT', '(HarrisburgWeatherAgent, contact@example.com)')
NWS_API_BASE = 'https://api.weather.gov'

# Database configuration
DB_PATH = os.getenv('DB_PATH', './weather_data.db')

# Scheduling configuration
CHECK_INTERVAL_HOURS = int(os.getenv('CHECK_INTERVAL_HOURS', 6))

# Forecast parameters
FORECAST_DAYS = 7  # Look up to 7 days in the future
