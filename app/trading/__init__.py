from flask import Blueprint

trading_bp = Blueprint(
    'trading', 
    __name__,
    template_folder="templates",)

from . import routes
