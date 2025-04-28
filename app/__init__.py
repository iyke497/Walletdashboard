from flask import Flask, render_template
from config import Config
from .extensions import db, migrate, login_manager
from .routes import init_app as register_blueprints


def create_app():
    app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Register all blueprints
    register_blueprints(app)

    # Handle 404s
    @app.errorhandler(404)
    def not_found(e):
        return render_template('base.html', content='<h2>Page not found</h2>'), 404

    return app