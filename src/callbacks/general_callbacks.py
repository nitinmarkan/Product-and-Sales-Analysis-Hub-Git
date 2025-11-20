from dash import Input, Output, State, html, dcc, dash_table
from dash.exceptions import PreventUpdate
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from src.app_instance import app
from src.utils.data_processing import parse_contents

def register_general_callbacks(app):
    @app.callback(
        [Output('sales-data-store', 'data'), Output({'type': 'upload', 'index': 'sales'}, 'children')],
        Input({'type': 'upload', 'index': 'sales'}, 'contents'), State({'type': 'upload', 'index': 'sales'}, 'filename'))
    def store_sales_data(c, f):
        if not c: raise PreventUpdate
        df = parse_contents(c, f)
        if df is None or 'itemname' not in df.columns: return None, html.Div([html.I(className="fas fa-times-circle text-danger me-2"), "Invalid Sales File"])
        return df.to_json(orient='split'), html.Div([html.I(className="fas fa-check-circle text-success me-2"), f])

    @app.callback(
        [Output('reorder-data-store', 'data'), Output({'type': 'upload', 'index': 'reorder'}, 'children')],
        Input({'type': 'upload', 'index': 'reorder'}, 'contents'), State({'type': 'upload', 'index': 'reorder'}, 'filename'))
    def store_reorder_data(c, f):
        if not c: raise PreventUpdate
        df = parse_contents(c, f)
        if df is None or 'sku' not in df.columns: return None, html.Div([html.I(className="fas fa-times-circle text-danger me-2"), "Invalid Reorder File"])
        return df.to_json(orient='split'), html.Div([html.I(className="fas fa-check-circle text-success me-2"), f])

    @app.callback(
        [Output('margins-data-store', 'data'), Output({'type': 'upload', 'index': 'margins'}, 'children')],
        Input({'type': 'upload', 'index': 'margins'}, 'contents'), State({'type': 'upload', 'index': 'margins'}, 'filename'))
    def store_margins_data(c, f):
        if not c: raise PreventUpdate
        df = parse_contents(c, f)
        if df is None or ('sku' not in df.columns and 'normal sku' not in df.columns): return None, html.Div([html.I(className="fas fa-times-circle text-danger me-2"), "Invalid Margins File"])
        return df.to_json(orient='split'), html.Div([html.I(className="fas fa-check-circle text-success me-2"), f])

    @app.callback(
        [Output('import-list-store', 'data'), Output({'type': 'upload', 'index': 'import'}, 'children')],
        Input({'type': 'upload', 'index': 'import'}, 'contents'), State({'type': 'upload', 'index': 'import'}, 'filename'))
    def store_import_list(c, f):
        if not c: raise PreventUpdate
        df = parse_contents(c, f)
        if df is None: return None, html.Div([html.I(className="fas fa-times-circle text-danger me-2"), "Invalid Import File"])
        skus = []
        if 'retail channel sku' in df.columns: skus.extend(df['retail channel sku'].dropna().astype(str).str.strip().str.lower())
        if 'vendor/ mask sku' in df.columns: skus.extend(df['vendor/ mask sku'].dropna().astype(str).str.strip().str.lower())
        if not skus: return None, html.Div([html.I(className="fas fa-times-circle text-danger me-2"), "No SKU columns found"])
        return list(set(skus)), html.Div([html.I(className="fas fa-check-circle text-success me-2"), f])

    @app.callback(
        Output('merged-data-store', 'data'),
        [Input('sales-data-store', 'data'), Input('reorder-data-store', 'data'), Input('margins-data-store', 'data')])
    def merge_data(sales_json, reorder_json, margins_json):
        if not sales_json: raise PreventUpdate
        sales_df = pd.read_json(sales_json, orient='split')
        reorder_df = pd.read_json(reorder_json, orient='split') if reorder_json else pd.DataFrame()
        margins_df = pd.read_json(margins_json, orient='split') if margins_json else pd.DataFrame()

        mpf_data = {
        'wayfair': 0.25, 'home depot': 0.30, 'bed bath & beyond': 0.32,
        'oj commerce': 0.28, 'vir venture': 0.28, 'uber bazaar': 0.28,
        'unbeatable': 0.28, 'amazon ca warehouse': 0.56, 'amazon vc dsv': 0.25,
        'amazon warehouse': 0.35, 'target': 0.30, 'lowes': 0.30, 'ashley home': 0.25,  
                                
        }
        
        master_key, secondary_key = 'sku', 'normal sku'
        sales_df['original_itemname'] = sales_df['itemname']

        for df, cols in [(sales_df, ['itemname', 'customer name']), (reorder_df, [master_key, secondary_key, 'itemname']), (margins_df, [master_key, secondary_key])]:
            for col in cols:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip().str.lower()
        
        sku_map = {}
        if not reorder_df.empty and secondary_key in reorder_df.columns:
            map_df = reorder_df.dropna(subset=[master_key, secondary_key])
            sku_map = pd.Series(map_df[master_key].values, index=map_df[secondary_key]).to_dict()

        sales_df[master_key] = sales_df['itemname'].map(sku_map).fillna(sales_df['itemname'])
        
        try: sales_df['orderdate'] = pd.to_datetime(sales_df['orderdate'], format='%d %B %Y', errors='coerce')
        except Exception: sales_df['orderdate'] = pd.to_datetime(sales_df['orderdate'], errors='coerce')
        sales_df = sales_df.dropna(subset=['orderdate'])
        sales_df = sales_df[sales_df['orderstatus'].isin(['Processed', 'Pending'])].copy()
        for col in ['quantity', 'price']: sales_df[col] = pd.to_numeric(sales_df[col], errors='coerce').fillna(0)
        sales_df['sales'] = sales_df['quantity'] * sales_df['price']
        
        merged_df = sales_df
        if not reorder_df.empty:
            agg_cols = {col: 'sum' for col in ['production', 'intransit'] if col in reorder_df.columns}
            first_cols = {col: 'first' for col in ['inv', 'image', 'category', 'product type', 'itemname'] if col in reorder_df.columns}
            reorder_agg = reorder_df.groupby(master_key).agg({**agg_cols, **first_cols}).reset_index()
            merged_df = pd.merge(merged_df, reorder_agg, on=master_key, how='left')

        if not margins_df.empty:
            if secondary_key in margins_df.columns:
                margins_df[master_key] = margins_df[secondary_key].map(sku_map).fillna(margins_df.get(master_key))
            cost_cols = [c for c in ['fob', 'landing cost'] if c in margins_df.columns]
            if cost_cols:
                for col in cost_cols: margins_df[col] = pd.to_numeric(margins_df[col], errors='coerce').fillna(0)
                margins_agg = margins_df.groupby(master_key)[cost_cols].first().reset_index()
                merged_df = pd.merge(merged_df, margins_agg, on=master_key, how='left', suffixes=('', '_margins'))
        
        if 'itemname' in merged_df.columns:
            merged_df['display_name'] = merged_df['itemname'].fillna(merged_df['original_itemname'])
        else:
            merged_df['display_name'] = merged_df['original_itemname']

        merged_df['mpf_percentage'] = merged_df['customer name'].map(mpf_data)
        merged_df['mpf_amount_per_unit'] = merged_df['price'] * merged_df['mpf_percentage']
        merged_df['profit_per_unit'] = merged_df['price'] - merged_df.get('landing cost', 0) - merged_df['mpf_amount_per_unit']
        merged_df['profit'] = merged_df['profit_per_unit'] * merged_df['quantity']
        merged_df['profit_margin'] = (merged_df['profit_per_unit'] / merged_df['price']).replace([np.inf, -np.inf], np.nan)

        return merged_df.to_json(date_format='iso', orient='split')

    @app.callback(
        [Output('main-dashboard-content', 'style'), Output('processing-status', 'children'),
        Output('customer-dropdown', 'options'), Output('date-range-picker', 'min_date_allowed'),
        Output('date-range-picker', 'max_date_allowed'), Output('date-range-picker', 'start_date'),
        Output('date-range-picker', 'end_date'),
        Output('table-month-filter', 'options'), Output('profit-customer-dropdown', 'options'),
        Output('profit-category-dropdown', 'options')],
        Input('merged-data-store', 'data'))
    def update_ui_elements(merged_json):
        if not merged_json: return {'display': 'none'}, "Waiting for Sales Data...", [], None, None, None, None, [], [], []
        df = pd.read_json(merged_json, orient='split')
        df['orderdate'] = pd.to_datetime(df['orderdate'])
        all_customers = sorted(df['customer name'].dropna().unique())
        all_categories = sorted(df['category'].dropna().unique()) if 'category' in df.columns else []
        min_date, max_date = df['orderdate'].min().date(), df['orderdate'].max().date()
        month_options = sorted(df['orderdate'].dt.to_period('M').unique().astype(str).tolist())
        return ({'display': 'block'}, "Data loaded successfully!", all_customers,
                min_date, max_date, min_date, max_date, month_options, all_customers, all_categories)

    @app.callback(
        Output("upload-collapse", "is_open"),
        Input("collapse-upload-button", "n_clicks"), State("upload-collapse", "is_open"))
    def toggle_upload_collapse(n, is_open):
        if n: return not is_open
        return is_open

    @app.callback(
        Output('item-dropdown', 'options'),
        [Input('merged-data-store', 'data'), Input('import-only-switch', 'value'), Input('import-list-store', 'data')])
    def update_item_dropdown_options(merged_json, import_only, import_list):
        if not merged_json: return []
        df = pd.read_json(merged_json, orient='split')
        if import_only and import_list:
            df = df[df['sku'].isin(import_list)]
        options = [{'label': name, 'value': key} for name, key in df[['display_name', 'sku']].drop_duplicates().sort_values('display_name').values]
        return options

    @app.callback(
        [Output('profit-item-dropdown', 'options'),
        Output('forecast-item-dropdown', 'options')],
        [Input('merged-data-store', 'data'), Input('import-list-store', 'data')]
    )
    def update_import_only_dropdowns(merged_json, import_list):
        if not merged_json or not import_list:
            return [], []
        df = pd.read_json(merged_json, orient='split')
        import_df = df[df['sku'].isin(import_list)]
        options = [{'label': name, 'value': key} for name, key in import_df[['display_name', 'sku']].drop_duplicates().sort_values('display_name').values]
        return options, options

    @app.callback(
        [Output('category-filter-col', 'style'), Output('category-dropdown', 'options'), Output('import-charts-section', 'style')],
        [Input('import-only-switch', 'value'), Input('item-dropdown', 'value'), Input('merged-data-store', 'data')])
    def toggle_import_section(toggle_on, items_selected, merged_json):
        if not merged_json: raise PreventUpdate
        df = pd.read_json(merged_json, orient='split')
        categories = sorted(df['category'].dropna().unique()) if 'category' in df.columns else []
        if toggle_on and not items_selected:
            return {'display': 'block'}, [{'label': c, 'value': c} for c in categories], {'display': 'block'}
        return {'display': 'none'}, [], {'display': 'none'}

    @app.callback(
        [Output('kpi-cards-row', 'children'), Output('monthly-quantity-chart', 'figure'),
        Output('customer-sales-chart', 'figure'), Output('main-data-table', 'columns'),
        Output('main-data-table', 'data'), Output('category-sales-pie-chart', 'figure'),
        Output('top-items-bar-chart', 'figure'), Output('price-trend-div', 'style'),
        Output('price-trend-chart', 'figure')],
        [Input('merged-data-store', 'data'), Input('date-range-picker', 'start_date'),
        Input('date-range-picker', 'end_date'), Input('item-dropdown', 'value'),
        Input('customer-dropdown', 'value'), Input('import-only-switch', 'value'),
        Input('import-list-store', 'data'), Input('category-dropdown', 'value'),
        Input('table-month-filter', 'value')])
    def update_main_visuals(merged_json, start_date, end_date, items, customers, import_only, import_list, categories, table_month):
        if not all([merged_json, start_date, end_date]): raise PreventUpdate
        df = pd.read_json(merged_json, orient='split')
        df['orderdate'] = pd.to_datetime(df['orderdate'])
        dff = df.copy()
        if import_only and import_list: dff = dff[dff['sku'].isin(import_list)]
        dff = dff[(dff['orderdate'] >= pd.to_datetime(start_date)) & (dff['orderdate'] <= pd.to_datetime(end_date))]
        if items: dff = dff[dff['sku'].isin(items)]
        if customers: dff = dff[dff['customer name'].isin(customers)]
        if categories: dff = dff[dff['category'].isin(categories)]
        
        total_sales, total_quantity, total_orders = dff['sales'].sum(), dff['quantity'].sum(), dff['orderid'].nunique()
        avg_order_value = total_sales / total_orders if total_orders > 0 else 0
        kpi_cards = [
            dbc.Col(dbc.Card(dbc.CardBody([html.H4("Total Sales"), html.H2(f"${total_sales:,.0f}")]))),
            dbc.Col(dbc.Card(dbc.CardBody([html.H4("Total Quantity"), html.H2(f"{total_quantity:,}")]))),
            dbc.Col(dbc.Card(dbc.CardBody([html.H4("Total Orders"), html.H2(f"{total_orders:,}")]))),
            dbc.Col(dbc.Card(dbc.CardBody([html.H4("Avg. Order Value"), html.H2(f"${avg_order_value:,.2f}")]))),
        ]

        fig_monthly = go.Figure(layout_title_text="Quantity Sold by Time")
        if not dff.empty:
            time_diff = pd.to_datetime(end_date) - pd.to_datetime(start_date)
            if time_diff.days < 14:
                rule, title = 'D', 'Daily Quantity Sold'
                grouped_data = dff.set_index('orderdate').resample(rule).agg({'quantity': 'sum', 'sales': 'sum'}).reset_index()
                grouped_data['period'] = grouped_data['orderdate'].dt.strftime('%d %b')
            elif time_diff.days <= 62:
                rule, title = 'W-Mon', 'Weekly Quantity Sold'
                grouped_data = dff.set_index('orderdate').resample(rule).agg({'quantity': 'sum', 'sales': 'sum'}).reset_index()
                grouped_data['period'] = grouped_data['orderdate'].dt.strftime('%d %b') + ' - ' + (grouped_data['orderdate'] + pd.to_timedelta(6, unit='d')).dt.strftime('%d %b, %Y')
            else:
                rule, title = 'M', 'Monthly Quantity Sold'
                grouped_data = dff.set_index('orderdate').resample(rule).agg({'quantity': 'sum', 'sales': 'sum'}).reset_index()
                grouped_data['period'] = grouped_data['orderdate'].dt.strftime('%B %Y')
            
            fig_monthly.add_trace(go.Bar(x=grouped_data['period'], y=grouped_data['quantity'], name='Quantity', text=grouped_data['quantity'], textposition='auto', customdata=grouped_data['sales']))
            fig_monthly.update_traces(hovertemplate='<b>Quantity</b>: %{y}<br><b>Sales</b>: $%{customdata:,.2f}')
            fig_monthly.update_layout(title_text=title)
        
        fig_customer = go.Figure(layout_title_text='Top Customers by Quantity')
        if not dff.empty:
            customer_agg = dff.groupby('customer name').agg(quantity=('quantity', 'sum'), sales=('sales', 'sum')).nlargest(15, 'quantity').reset_index()
            fig_customer = px.bar(customer_agg, x='customer name', y='quantity', title='Top Customers by Quantity', text_auto=True, custom_data=['sales'])
            fig_customer.update_traces(hovertemplate='<b>Quantity</b>: %{y}<br><b>Sales</b>: $%{customdata[0]:,.2f}')
            fig_customer.update_xaxes(tickangle=-45)
        
        fig_pie, fig_top_items = go.Figure(layout_title_text="Sales by Category"), go.Figure(layout_title_text="Top 10 Items")
        if import_only and 'category' in dff.columns:
            dff_cat = dff[dff['category'].isin(categories)] if categories else dff
            if not dff_cat.empty:
                category_sales = dff_cat.groupby('category')['sales'].sum().reset_index()
                fig_pie = px.pie(category_sales, names='category', values='sales', title='Sales by Category')
                top_items_df = dff_cat.groupby('display_name').agg(sales=('sales', 'sum'), quantity=('quantity', 'sum')).nlargest(10, 'sales').reset_index()
                fig_top_items = px.bar(top_items_df, x='display_name', y='sales', title='Top 10 Items by Sales', custom_data=['quantity'])
                fig_top_items.update_traces(hovertemplate='<b>Sales</b>: $%{y:,.2f}<br><b>Quantity</b>: %{customdata[0]:,}<extra></extra>')
        
        dff_table = dff.copy()
        if table_month: dff_table = dff_table[dff_table['orderdate'].dt.to_period('M').astype(str) == table_month]
        display_cols = ['orderdate', 'display_name', 'customer name', 'quantity', 'price', 'sales', 'profit_margin']
        table_data = dff_table[display_cols].to_dict('records')
        for row in table_data: 
            row['orderdate'] = pd.to_datetime(row['orderdate']).strftime('%Y-%m-%d')
            row['profit_margin'] = f"{row.get('profit_margin', 0) * 100:.1f}%" if pd.notna(row.get('profit_margin')) else '-'
        table_cols = [{"name": "Date", "id": "orderdate"}, {"name": "Item Name", "id": "display_name"}, {"name": "Customer", "id": "customer name"}, {"name": "Quantity", "id": "quantity"}, {"name": "Price", "id": "price"}, {"name": "Sales", "id": "sales"}, {"name": "Profit Margin", "id": "profit_margin"}]
        
        price_trend_style, fig_price_trend = {'display': 'none'}, go.Figure()
        if items and customers:
            trend_df = dff[dff['sku'].isin(items) & dff['customer name'].isin(customers)]
            if not trend_df.empty:
                fig_price_trend = px.line(trend_df, x='orderdate', y='price', color='customer name', title='Price Trend Over Time', markers=True, custom_data=['profit_margin'])
                fig_price_trend.update_traces(hovertemplate='<b>Price</b>: $%{y:,.2f}<br><b>Profit Margin</b>: %{customdata[0]:.1%}<extra></extra>')
                price_trend_style = {'display': 'block'}

        return kpi_cards, fig_monthly, fig_customer, table_cols, table_data, fig_pie, fig_top_items, price_trend_style, fig_price_trend

    @app.callback(
        Output('deep-dive-section', 'children'),
        [Input('item-dropdown', 'value'), Input('merged-data-store', 'data')])
    def update_deep_dive(selected_items, merged_json):
        if not selected_items or not merged_json or len(selected_items) != 1: return None
        df = pd.read_json(merged_json, orient='split')
        item_data = df[df['sku'] == selected_items[0]].iloc[0]
        card_content = [
            dbc.Row([
                dbc.Col(html.Img(src=item_data.get('image', ''), style={'height':'150px', 'width': 'auto'}), width=3),
                dbc.Col([
                    html.H4(item_data.get('display_name')),
                    html.P(f"Category: {item_data.get('category', 'N/A')}"),
                    html.P(f"Product Type: {item_data.get('product type', 'N/A')}")
                ], width=9)
            ]), html.Hr(),
            dbc.Row([
                dbc.Col(html.Div([html.P("Inventory"), html.H5(f"{item_data.get('inv', 0):,.0f}")])),
                dbc.Col(html.Div([html.P("In Production"), html.H5(f"{item_data.get('production', 0):,.0f}")])),
                dbc.Col(html.Div([html.P("In Transit"), html.H5(f"{item_data.get('intransit', 0):,.0f}")])),
                dbc.Col(html.Div([html.P("FOB Cost"), html.H5(f"${item_data.get('fob', 0):,.2f}")])),
                dbc.Col(html.Div([html.P("Landing Cost"), html.H5(f"${item_data.get('landing cost', 0):,.2f}")]))
            ], className="text-center")]
        return dbc.Card(dbc.CardBody(card_content), className="mb-3")

    @app.callback(
        Output("download-csv", "data"),
        Input("export-csv-button", "n_clicks"), State("main-data-table", "data"),
        prevent_initial_call=True)
    def export_table_to_csv(n_clicks, table_data):
        if not table_data: raise PreventUpdate
        return dcc.send_data_frame(pd.DataFrame(table_data).to_csv, "filtered_transactions.csv", index=False)

    @app.callback(
        [Output('item-dropdown', 'value', allow_duplicate=True), Output('customer-dropdown', 'value', allow_duplicate=True),
        Output('category-dropdown', 'value', allow_duplicate=True), Output('date-range-picker', 'start_date', allow_duplicate=True),
        Output('date-range-picker', 'end_date', allow_duplicate=True)],
        Input('clear-filters-button', 'n_clicks'), State('merged-data-store', 'data'),
        prevent_initial_call=True)
    def clear_all_filters(n_clicks, merged_json):
        if not merged_json: raise PreventUpdate
        df = pd.read_json(merged_json, orient='split')
        df['orderdate'] = pd.to_datetime(df['orderdate'])
        min_date, max_date = df['orderdate'].min().date(), df['orderdate'].max().date()
        return [], [], [], min_date, max_date
