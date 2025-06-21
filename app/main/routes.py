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


@main_bp.route('/about')
def about():
    return render_template('main/about.html')\
    

@main_bp.route('/terms-of-service')
def tos():
    return render_template('main/terms_of_service.html')

@main_bp.route('/privacy-policy')
def privacy_policy():
    return render_template('main/privacy_policy.html')

@main_bp.route('/cookies')
def cookies():
    return render_template('main/cookies.html')

@main_bp.route('/copytrade-terms-and-conditions')
def copytrade_terms_and_conditions():
    return render_template('main/copytrade_terms.html')

@main_bp.route('/learn-more-2fa')
def learn_more_2fa():
    return render_template('main/learn_more_2fa.html')

@main_bp.route('/referal-program')
def referal():
    return render_template('main/referal.html')