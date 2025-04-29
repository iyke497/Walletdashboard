# app/wallet/__init__.py

from flask import Blueprint

wallet_bp = Blueprint(
    "wallet",         # the endpoint name
    __name__,            # module name
    template_folder="templates",  # if you have templates here
)

# import your routes so they get registered on wallet_bp
from . import routes
