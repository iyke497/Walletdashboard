from datetime import datetime

def format_datetime(value):
    if value is None:
        return ""
    return value.strftime('%Y-%m-%d %H:%M:%S')

def init_app(app):
    app.jinja_env.filters['datetime'] = format_datetime 