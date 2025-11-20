from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc

def create_layout():
    return dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Img(src="https://benzara.com/cdn/shop/files/download.png?v=1690743366&width=600", height="60px", className="me-3"),
                    html.Div([
                        html.H1("Sales & Product Analysis Hub", className="text-primary mb-0"),
                        html.P("Developed by Import Team", style={'fontSize': 'medium', 'color': 'grey', 'fontStyle': 'italic', 'marginTop': '0px'})
                    ], className="text-center")
                ], className="d-flex align-items-center")
            ], width="auto")
        ], justify="center", align="center", className="my-4"),

        # Data Stores
        dcc.Store(id='sales-data-store'),
        dcc.Store(id='reorder-data-store'),
        dcc.Store(id='margins-data-store'),
        dcc.Store(id='import-list-store'),
        dcc.Store(id='merged-data-store'),
        dcc.Store(id='abc-analysis-data-store'),
        dcc.Download(id="download-csv"),
        dcc.Download(id="download-abc-component"),
        dcc.Download(id="download-at-risk-csv"),

        # Upload Section
        dbc.Row([dbc.Col(dbc.Button("Show/Hide Upload Section", id="collapse-upload-button", className="mb-2"), width=12)]),
        dbc.Collapse(
            dbc.Row([
                dbc.Col(dcc.Upload(id={'type': 'upload', 'index': 'sales'}, children=html.Div(['1. Upload Sales Data']), className='upload-box'), width=3),
                dbc.Col(dcc.Upload(id={'type': 'upload', 'index': 'reorder'}, children=html.Div(['2. Upload Reorder Data']), className='upload-box'), width=3),
                dbc.Col(dcc.Upload(id={'type': 'upload', 'index': 'margins'}, children=html.Div(['3. Upload Margins & Costs']), className='upload-box'), width=3),
                dbc.Col(dcc.Upload(id={'type': 'upload', 'index': 'import'}, children=html.Div(['4. Upload Import Item List']), className='upload-box'), width=3),
            ], className="mb-4"),
            id="upload-collapse", is_open=True
        ),
        html.Div(id='processing-status', className='text-center text-muted mb-4'),

        # --- Tabbed Layout ---
        dbc.Tabs(id="dashboard-tabs", active_tab="tab-overview", children=[
            dbc.Tab(label="Sales Overview", tab_id="tab-overview", children=[
                html.Div(id='main-dashboard-content', style={'display': 'none'}, children=[
                    dbc.Card(dbc.CardBody([
                        dbc.Row([
                            dbc.Col(dcc.DatePickerRange(id='date-range-picker', className="w-100"), width=12, lg=3),
                            dbc.Col(dcc.Dropdown(id='item-dropdown', multi=True, placeholder="Filter by Item..."), width=12, lg=3),
                            dbc.Col(dcc.Dropdown(id='customer-dropdown', multi=True, placeholder="Filter by Customer..."), width=12, lg=3),
                            dbc.Col(dcc.Dropdown(id='category-dropdown', multi=True, placeholder="Filter by Category..."), width=12, lg=3, id='category-filter-col', style={'display': 'none'}),
                        ], className="mb-3"),
                        dbc.Row([
                            dbc.Col(dbc.Switch(id='import-only-switch', label="Show Import Items Only", value=False), width="auto"),
                            dbc.Col(dbc.Button("Clear All Filters", id="clear-filters-button", color="danger", outline=True), width="auto", className="ms-auto")
                        ])
                    ])),
                    html.Div(id='deep-dive-section', className="mt-4"),
                    dbc.Row(id='kpi-cards-row', className="my-4"),
                    dbc.Row([
                        dbc.Col(dcc.Graph(id='monthly-quantity-chart'), width=12, lg=6),
                        dbc.Col(dcc.Graph(id='customer-sales-chart'), width=12, lg=6)
                    ], className="mb-4"),
                    html.Div(id='price-trend-div', style={'display': 'none'}, children=[
                        dbc.Row([dbc.Col(dcc.Graph(id='price-trend-chart'), width=12)])
                    ]),
                    html.Div(id='import-charts-section', style={'display': 'none'}, children=[
                        dbc.Row([
                            dbc.Col(dcc.Graph(id='category-sales-pie-chart'), width=12, lg=6),
                            dbc.Col(dcc.Graph(id='top-items-bar-chart'), width=12, lg=6)
                        ])
                    ]),
                    dbc.Row([dbc.Col(html.Div([
                        html.H4("Transaction Details"),
                        dbc.Row([
                            dbc.Col(dcc.Dropdown(id='table-month-filter', placeholder="Filter Table by Month..."), width=12, lg=4, className="mb-2"),
                            dbc.Col(dbc.Button("Export Table to CSV", id="export-csv-button", color="success"), width="auto", className="mb-2")
                        ]),
                        dash_table.DataTable(id='main-data-table', page_size=10, sort_action="native")
                    ]))])
                ])
            ]),

            dbc.Tab(label="Inventory Analysis", tab_id="tab-inventory", children=[
                dbc.Card(dbc.CardBody([
                    html.H4("Import Inventory Value & Health", className="mb-3"),
                    dbc.Row(id='inventory-kpi-row', className="my-4 g-3"),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col(dcc.Graph(id='in-stock-percentage-chart'), width=12, lg=6),
                        dbc.Col([
                            html.H5("ABC Analysis"),
                            html.P("Class A: Top 80% of consumption value. Class B: Next 15%. Class C: Bottom 5%.", className="text-muted small"),
                            html.Div(id='abc-summary-table'),
                            dbc.Button("Download ABC Analysis Details", id="download-abc-csv", color="secondary", outline=True, className="mt-2 w-100")
                        ], width=12, lg=6),
                    ], className="my-4"),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col([
                            dbc.Row([
                                dbc.Col(html.H4("At-Risk Inventory Alert"), width='auto'),
                                dbc.Col(dbc.Button("Download At-Risk Data", id="download-at-risk-button", color="info", outline=True, size="sm"), width='auto')
                            ], align="center", justify="between", className="mb-2"),
                            html.P("Items with less than 60 days of total supply.", className="text-muted"),
                            dash_table.DataTable(id='at-risk-table', page_size=5, sort_action="native")
                        ]),
                    ], className="my-4")
                ]))
            ]),
            
            dbc.Tab(label="Profitability Analysis", tab_id="tab-profit", children=[
                dbc.Card(dbc.CardBody([
                    html.H4("Profitability Overview"),
                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id='profit-item-dropdown', multi=True, placeholder="Filter by Import Item...")),
                        dbc.Col(dcc.Dropdown(id='profit-customer-dropdown', multi=True, placeholder="Filter by Customer...")),
                        dbc.Col(dcc.Dropdown(id='profit-category-dropdown', multi=True, placeholder="Filter by Category...")),
                    ], className="mb-3"),
                    dbc.Row(id='profit-kpi-row', className="my-4 g-3"),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col(dcc.Graph(id='profit-by-customer-chart'), width=12, lg=6),
                        dbc.Col(dcc.Graph(id='top-profitable-items-chart'), width=12, lg=6)
                    ], className="my-4"),
                    dbc.Row([
                        dbc.Col(dcc.Graph(id='margin-by-category-chart'), width=12)
                    ])
                ]))
            ]),

            dbc.Tab(label="Forecasting", tab_id="tab-forecast", children=[
                 dbc.Card(dbc.CardBody([
                    html.H4("Sales Quantity Forecasting"),
                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id='forecast-item-dropdown', placeholder="Select an import item to forecast..."), width=12, lg=6),
                        dbc.Col([
                            html.P("Forecast Period (Days):", className="mb-0 small"),
                            dcc.Slider(id='forecast-period-slider', min=30, max=180, step=30, value=90, marks={i: str(i) for i in range(30, 181, 30)})
                        ], width=12, lg=6)
                    ], className="mb-4 align-items-center"),
                    dbc.Row(id='forecast-kpi-row', className="my-4 g-3"),
                    dbc.Spinner(dcc.Graph(id='forecast-chart'), color="primary"),
                    dbc.Spinner(dcc.Graph(id='forecast-decomposition-chart'), color="secondary")
                ]))
            ]),
        ])
    ], fluid=True, className="dbc")
