from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_caching import Cache
from flask_assets import Environment, Bundle
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
assets = Environment()
mail = Mail()
csrf = CSRFProtect()

# Define bundles
css_bundle = Bundle(
    'vendor/css/core.css',
    'vendor/fonts/iconify-icons.css',
    'vendor/libs/node-waves/node-waves.css',
    'vendor/libs/perfect-scrollbar/perfect-scrollbar.css',
    'vendor/libs/pickr/pickr-themes.css',
    'css/demo.css',
    filters='cssmin',
    output='dist/css/app.min.css'
)

js_bundle = Bundle(
    'vendor/libs/jquery/jquery.js',
    'vendor/libs/popper/popper.js',
    'vendor/js/bootstrap.js',
    'vendor/libs/node-waves/node-waves.js',
    'vendor/libs/perfect-scrollbar/perfect-scrollbar.js',
    'vendor/libs/@algolia/autocomplete-js.js',
    'vendor/libs/pickr/pickr.js',
    'vendor/libs/hammer/hammer.js',
    'vendor/js/menu.js',
    'vendor/js/helpers.js',
    'js/config.js',
    'js/main.js',
    filters='jsmin',
    output='dist/js/app.min.js'
)
