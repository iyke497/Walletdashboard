from app.auth.routes import bp as auth_bp
from app.dashboard.routes import bp as dash_bp
from app.wallet.routes import bp as wallet_bp


def init_app(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(dash_bp)
    app.register_blueprint(wallet_bp)