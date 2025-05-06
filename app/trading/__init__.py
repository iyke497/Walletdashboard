from flask import Blueprint

trading_bp = Blueprint('trading', __name__, 
                      url_prefix='/trading',
                      template_folder='templates',
                      static_folder='static',
                      static_url_path='')

from . import routes
