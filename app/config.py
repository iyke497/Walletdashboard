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

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    ENV = "development"

class ProductionConfig(BaseConfig):
    DEBUG = False
    ENV = "production"

# factory to pick config
config_by_name = dict(
    dev=DevelopmentConfig,
    prod=ProductionConfig,
)
