from src.app_instance import app, server
from src.components.layout import create_layout
from src.callbacks.register_callbacks import register_callbacks

# Set layout
app.layout = create_layout()

# Register callbacks
register_callbacks(app)

if __name__ == '__main__':
    app.run(debug=True, port=8051)
