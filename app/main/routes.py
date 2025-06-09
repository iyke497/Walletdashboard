from flask import render_template, flash, redirect, url_for
from . import main_bp
from .forms import ContactForm

@main_bp.route('/')
@main_bp.route('/index')
def index():
    """Renders the landing page."""
    # You might want to pass some dynamic data to the template here
    return render_template('main/index.html')


@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """ Presents form for phone and email contact"""

    form = ContactForm()

    if form.validate_on_submit():
        # Process the form data
        full_name = form.full_name.data
        email = form.email.data
        message = form.message.data
        
        # Here you would typically:
        # - Save to database
        # - Send email
        # - Process the contact request
        
        print(f"Contact form submitted:")
        print(f"Name: {full_name}")
        print(f"Email: {email}")
        print(f"Message: {message}")
        
        flash('Thank you for your message! We will get back to you soon.', 'success')
        return redirect(url_for('contact'))
    
    return render_template('main/contact_support.html', form=form)