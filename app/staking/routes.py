from flask import render_template, request
from app.staking import staking_bp
from app.staking.services import AssetService
from app.models import Asset

@staking_bp.route('/')
def staking_home():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)  # Items per page
    search = request.args.get('search', '', type=str)

    # Build query with optional search
    query = Asset.query

    assets = AssetService.get_assets()

    serialized_assets = [
        {
            'symbol': asset.symbol,
            'name': asset.name,
            'images': asset.images.get('small') if asset.images else None
        }
        for asset in assets if asset.images is not None
    ]

    return render_template('staking/staking_home.html', assets=serialized_assets)