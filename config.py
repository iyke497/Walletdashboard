import os
from pathlib import Path

basedir = Path(__file__).resolve().parent

class BaseConfig:
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY',  SECRET_KEY)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(BaseConfig):
    # if DEV_DATABASE_URL is set in .env, use that;
    # otherwise fall back to a SQLite file next to this config
    SQLALCHEMY_DATABASE_URI = (
        os.getenv('DEV_DATABASE_URL')
        or f"sqlite:///{ basedir / 'dev.sqlite3'}"
    )

class ProductionConfig(BaseConfig):
    # in prod, read DATABASE_URL (postgres, mysql, etc)
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', '')

# a simple mapping so we can do: app.config.from_object(configs[env])
configs = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
}