import os
from flask import Flask
from .config import config_by_name
from .extensions import db, migrate, login_manager, cache, assets, css_bundle, js_bundle, mail, csrf
from .commands import init_app as init_commands
from .filters import init_app as init_filters
from app.auth.services import EmailService
from app.utils.template_filters import register_template_filters

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
    cache.init_app(app)
    assets.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    # Register template filters
    register_template_filters(app)

    # Connect EmailService to mail extension
    EmailService.mail = mail

    # Register commands
    init_commands(app)

    # Register filters
    init_filters(app)

    # register assets
    assets.register('css_all', css_bundle)
    assets.register('js_all', js_bundle) # TODO: _all or _bundle

    # register blueprints
    from .main import main_bp
    from .auth import auth_bp
    from .dashboard import dashboard_bp
    from .wallet import wallet_bp
    from .trading import trading_bp
    from .copytrade import copytrade_bp
    from .staking import staking_bp
    from .errors import error_bp
    from .admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(wallet_bp, url_prefix="/wallet")
    app.register_blueprint(trading_bp, url_prefix="/trading")
    app.register_blueprint(copytrade_bp, url_prefix="/copytrade")
    app.register_blueprint(staking_bp, url_prefix="/staking")
    app.register_blueprint(error_bp)
    app.register_blueprint(admin_bp)
    
    return app
