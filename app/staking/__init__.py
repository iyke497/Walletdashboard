from flask import Blueprint

staking_bp = Blueprint('staking', __name__, template_folder='templates')

from . import routes
