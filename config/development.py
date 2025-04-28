import os
from .base import BaseConfig

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DEV_DATABASE_URI", "sqlite:///dev.db"
    )
    # any other dev-only flags
