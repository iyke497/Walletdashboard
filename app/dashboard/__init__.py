# app/dashboard/__init__.py

from flask import Blueprint

dashboard_bp = Blueprint(
    "dashboard",         # the endpoint name
    __name__,            # module name
    template_folder="templates",  # if you have templates here
)

# import your routes so they get registered on dashboard_bp
from . import routes
