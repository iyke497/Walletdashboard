from flask import render_template
from . import main_bp

@main_bp.route('/')
@main_bp.route('/index')
def index():
    """Renders the landing page."""
    # You might want to pass some dynamic data to the template here
    return render_template('main/index.html')


@main_bp.route('/contact')
def contact():
    """ Presents form for phone and email contact"""

    return render_template('main/contact_support.html')