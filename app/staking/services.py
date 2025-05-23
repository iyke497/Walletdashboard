from app.models import User, Holding, Asset

class AssetService:
    @staticmethod
    def get_assets():
        assets = Asset.query.all()
        return assets
    
    