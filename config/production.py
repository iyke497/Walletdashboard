import os
from .base import BaseConfig

class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")
    # e.g. email server creds, Sentry DSN, etc.
