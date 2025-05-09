from flask import Blueprint

copytrade_bp = Blueprint(
    "copytrade",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/copytrade/static"
)

# import your routes so they get registered on dashboard_bp
from . import routes
    