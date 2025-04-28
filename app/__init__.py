from flask import Flask, render_template
from .extensions import db, migrate, login_manager, csrf, cache
from .routes import init_app as register_blueprints
import os
from dotenv import load_dotenv


def create_app():
    env = os.getenv("FLASK_ENV", "development").lower()
    load_dotenv(f".env.{env}")

    app = Flask(__name__, template_folder='templates', static_folder='static')

    if env == "production":
        app.config.from_object("config.production.ProductionConfig")
    else:
        app.config.from_object("config.development.DevelopmentConfig")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    cache.init_app(app)

    # Register all blueprints
    register_blueprints(app)

    # Handle 404s
    @app.errorhandler(404)
    def not_found(e):
        return render_template('base.html', content='<h2>Page not found</h2>'), 404

    return app