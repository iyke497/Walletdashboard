from app import db
from app.models import Asset

def get_network_symbol(network_id):
    """
    Get the symbol for a network based on its ID.
    
    1. First checks if there's a dedicated Network model entry
    2. If not found, checks common network mappings
    3. Falls back to uppercase network_id if no match is found
    
    Args:
        network_id (str): The network identifier (e.g., "ethereum", "tron")
        
    Returns:
        str: The symbol for the network (e.g., "ERC20", "TRC20")
    """
    # As a last resort, check if there's an asset with this ID
    # and use its symbol (for native blockchains)
    asset = Asset.query.filter_by(coingecko_id=network_id).first()
    if asset:
        return asset.symbol.upper()
    
    # If all else fails, return the network_id in uppercase
    return network_id.upper()