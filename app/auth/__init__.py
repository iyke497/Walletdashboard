# app/auth/__init__.py
from flask import Blueprint

auth_bp = Blueprint(
    "auth",                # blueprint name
    __name__,              # package name
    template_folder="templates",  # if you have auth templates
)

# make sure routes.py is loaded so auth_bp gets its view functions
from . import routes
