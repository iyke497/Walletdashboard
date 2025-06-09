# app/utils/template_filters.py
from datetime import datetime

def register_template_filters(app):
    """Register custom template filters for Jinja2"""
    
    @app.template_filter('strftime')
    def strftime_filter(date_str, format='%b %d'):
        """Format a date string."""
        if isinstance(date_str, str):
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                return date_obj.strftime(format)
            except ValueError:
                return date_str
        return date_str

    @app.template_filter('number_format')
    def number_format_filter(value):
        """Format a number with commas as thousands separators."""
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return value