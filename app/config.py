import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from instance folder
env_path = Path(__file__).parent.parent / "instance" / ".env"
load_dotenv(dotenv_path=env_path)

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Configure PostgreSQL URI or fallback to SQLite
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{Path(__file__).parent.parent/'instance'/'app.db'}"
    )
    # Pagination defaults, etc.
    ITEMS_PER_PAGE = int(os.getenv("ITEMS_PER_PAGE", 25))
    # Exchange API Key
    EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")
    # Exchange Secret Key
    EXCHANGE_SECRET_KEY = os.getenv("EXCHANGE_SECRET_KEY")

    # Asset configs
    ASSETS_DEBUG = os.environ.get('ASSETS_DEBUG', 'False') == 'True'
    ASSETS_AUTO_BUILD = True

    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or MAIL_USERNAME

    # SERVER NAME
    APPLICATION_ROOT = '/'

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    ENV = "development"

    MAIL_DEBUG = True
    MAIL_SUPPRESS_SEND = False
    
    SERVER_NAME = 'localhost:45000' #TODO: For generating url's within the application context.
    PREFERRED_URL_SCHEME = 'http'
class ProductionConfig(BaseConfig):
    DEBUG = False
    ENV = "production"

    MAIL_SUPPRESS_SEND = False

    SERVER_NAME = 'bloxxxchain.com'
    PREFERRED_URL_SCHEME = 'https'

# factory to pick config
config_by_name = dict(
    dev=DevelopmentConfig,
    prod=ProductionConfig,
)
