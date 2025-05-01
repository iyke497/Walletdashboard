import os
from flask import Flask
from .config import config_by_name
from .extensions import db, migrate, login_manager
from .commands import init_app as init_commands

def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)

    # choose config
    if not config_name:
        flask_env = os.getenv("FLASK_ENV", "production")
        config_name = "dev" if flask_env == "development" else "prod"
    app.config.from_object(config_by_name[config_name])

    # initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Register commands
    init_commands(app)

    # register blueprints
    from .auth import auth_bp
    from .dashboard import dashboard_bp
    from .wallet import wallet_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(wallet_bp, url_prefix="/wallet")

    return app
