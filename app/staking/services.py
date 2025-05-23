from app.models import User, Holding, Asset, AssetType
from sqlalchemy import or_

class AssetService:
    @staticmethod
    def get_assets(page=1, per_page=10, search=''):
        """Get assets with pagination and search functionality"""
        #query = Asset.query.filter(Asset.is_active == True)
        #query = Asset.query.filter(Asset.images.isnot(None))
        query = Asset.query.filter(
                                Asset.asset_type == AssetType.CRYPTO,  # Only crypto assets
                                Asset.images.isnot(None))              # Only assets with images
        
        # Add search filter if provided
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    Asset.symbol.ilike(search_filter),
                    Asset.name.ilike(search_filter)
                )
            )
        
        # Order by symbol for consistent results
        query = query.order_by(Asset.id)
        
        # Apply pagination
        paginated_assets = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return paginated_assets
    
    @staticmethod
    def get_all_assets():
        """Get all assets without pagination (for backwards compatibility)"""
        return Asset.query.filter(Asset.is_active == True).all()