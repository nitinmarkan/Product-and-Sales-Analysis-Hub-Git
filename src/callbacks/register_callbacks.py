from src.callbacks.general_callbacks import register_general_callbacks
from src.callbacks.inventory_callbacks import register_inventory_callbacks
from src.callbacks.profit_callbacks import register_profit_callbacks
from src.callbacks.forecast_callbacks import register_forecast_callbacks

def register_callbacks(app):
    register_general_callbacks(app)
    register_inventory_callbacks(app)
    register_profit_callbacks(app)
    register_forecast_callbacks(app)
