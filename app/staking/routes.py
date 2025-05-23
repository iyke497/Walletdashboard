from flask import render_template, request, url_for
from app.staking import staking_bp
from app.staking.services import AssetService
from app.models import Asset

@staking_bp.route('/')
def staking_home():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '', type=str).strip()

    # Get paginated assets with search
    paginated_assets = AssetService.get_assets(
        page=page, 
        per_page=per_page, 
        search=search
    )

    # Serialize assets for template
    serialized_assets = []
    for asset in paginated_assets.items:
        #if asset.images is not None:
        serialized_assets.append({
            'id': asset.id,
            'symbol': asset.symbol,
            'name': asset.name,
            'image': asset.images.get('small', asset.images.get('thumb', '')) if asset.images else None
        })

    # Pagination info for template
    pagination_info = {
        'page': paginated_assets.page,
        'pages': paginated_assets.pages,
        'per_page': paginated_assets.per_page,
        'total': paginated_assets.total,
        'has_prev': paginated_assets.has_prev,
        'prev_num': paginated_assets.prev_num,
        'has_next': paginated_assets.has_next,
        'next_num': paginated_assets.next_num,
        'iter_pages': list(paginated_assets.iter_pages(left_edge=1, right_edge=1, left_current=1, right_current=2))
    }

    return render_template(
        'staking/staking_home.html', 
        assets=serialized_assets,
        pagination=pagination_info,
        search_query=search,
        current_per_page=per_page
    )