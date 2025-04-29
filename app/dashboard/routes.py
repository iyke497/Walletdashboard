from flask import render_template
from . import dashboard_bp

@dashboard_bp.route("/", methods=["GET"])
def index():
    # For now just render a placeholder
    return render_template("dashboard/index.html")
