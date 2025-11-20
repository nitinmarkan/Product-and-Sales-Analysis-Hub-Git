from dash import Input, Output, State, html, dcc, dash_table
from dash.exceptions import PreventUpdate
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc

def register_inventory_callbacks(app):
    @app.callback(
        [Output('inventory-kpi-row', 'children'), Output('in-stock-percentage-chart', 'figure'),
        Output('abc-summary-table', 'children'), Output('at-risk-table', 'data'),
        Output('at-risk-table', 'columns'), Output('abc-analysis-data-store', 'data')],
        [Input('merged-data-store', 'data'), Input('import-list-store', 'data'),
        Input('reorder-data-store', 'data'), Input('margins-data-store', 'data')])
    def update_inventory_tab(merged_json, import_list, reorder_json, margins_json):
        if not all([import_list, reorder_json, margins_json, merged_json]):
            raise PreventUpdate

        # --- 1. Prepare DataFrames ---
        import_skus_df = pd.DataFrame(import_list, columns=['sku'])
        reorder_df = pd.read_json(reorder_json, orient='split')
        margins_df = pd.read_json(margins_json, orient='split')
        sales_df = pd.read_json(merged_json, orient='split')
        sales_df['orderdate'] = pd.to_datetime(sales_df['orderdate'])

        for df, cols in [(reorder_df, ['sku', 'itemname']), (margins_df, ['sku', 'normal sku'])]:
            for col in cols:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip().str.lower()
        
        # --- 2. Create the Master Inventory DataFrame ---
        inv_master_df = pd.merge(import_skus_df, reorder_df.drop_duplicates(subset=['sku']), on='sku', how='left')
        inv_master_df = pd.merge(inv_master_df, margins_df.drop_duplicates(subset=['sku']), on='sku', how='left')

        if 'itemname' in inv_master_df.columns:
            inv_master_df['display_name'] = inv_master_df['itemname'].fillna(inv_master_df['sku'])
        else:
            inv_master_df['display_name'] = inv_master_df['sku']

        for col in ['inv', 'production', 'intransit', 'landing cost']:
            if col in inv_master_df.columns:
                inv_master_df[col] = pd.to_numeric(inv_master_df[col], errors='coerce').fillna(0)
            else: inv_master_df[col] = 0
        inv_master_df['category'] = inv_master_df['category'].fillna('Uncategorized')
        inv_master_df['inventory_value'] = inv_master_df['inv'] * inv_master_df['landing cost']

        # --- 3. Calculate KPIs ---
        inventory_kpis = []
        total_inv_value = inv_master_df['inventory_value'].sum()
        inventory_kpis.append(dbc.Col(dbc.Card(dbc.CardBody([html.H5("Total Inv. Value"), html.H4(f"${total_inv_value:,.0f}")])), width=6, lg=2, className="mb-2"))

        cats_to_display = ['Hot', 'Top', 'Normal', 'New', 'Slow']
        for cat in cats_to_display:
            cat_inv_value = inv_master_df[inv_master_df['category'] == cat]['inventory_value'].sum()
            inventory_kpis.append(dbc.Col(dbc.Card(dbc.CardBody([html.H5(f"Inv. Value ({cat})"), html.H4(f"${cat_inv_value:,.0f}")])), width=6, lg=2, className="mb-2"))

        turnover_kpis_children = []
        sales_df_import = sales_df[sales_df['sku'].isin(import_list)]
        for cat in cats_to_display:
            cat_sales_df = sales_df_import[sales_df_import['category'] == cat]
            cat_inv_df = inv_master_df[inv_master_df['category'] == cat]
            
            cogs = (cat_sales_df['quantity'] * cat_sales_df.get('landing cost', 0)).sum()
            avg_inv_value = cat_inv_df['inventory_value'].sum()
            turnover = cogs / avg_inv_value if avg_inv_value > 0 else 0
            turnover_kpis_children.append(html.Tr([html.Td(cat), html.Td(f"{turnover:.2f}")]))
        inventory_kpis.append(dbc.Col(dbc.Card(dbc.CardBody([html.H5("Inv. Turnover"), dbc.Table(html.Tbody(turnover_kpis_children), bordered=False, striped=True, hover=True, size='sm')])), width=12, lg=2, className="mb-2"))

        # --- 4. In-Stock Percentage Chart ---
        category_stock = inv_master_df.groupby('category').agg(
            total_skus=('sku', 'nunique'),
            in_stock_skus=('inv', lambda x: (x > 0).sum())
        ).reset_index()
        category_stock['in_stock_percent'] = (category_stock['in_stock_skus'] / category_stock['total_skus'] * 100).round(1)
        
        category_stock['category'] = pd.Categorical(category_stock['category'], categories=cats_to_display, ordered=True)
        category_stock = category_stock.dropna(subset=['category']).sort_values('category')

        fig_in_stock = go.Figure(layout_title_text="No inventory data for specified categories.")
        if not category_stock.empty:
            fig_in_stock = px.bar(category_stock, x='category', y='in_stock_percent', 
                                title='In-Stock SKU % by Category', 
                                text='in_stock_percent',
                                custom_data=['total_skus', 'in_stock_skus'],
                                labels={'in_stock_percent': 'In-Stock %'})
            
            fig_in_stock.update_traces(texttemplate='%{text}%', textposition='outside',
                                    hovertemplate='<b>%{x}</b><br><br>Total SKUs: %{customdata[0]:,}<br>SKUs in Stock: %{customdata[1]:,}<extra></extra>')
            fig_in_stock.update_yaxes(range=[0, 110])

        # --- 5. ABC Analysis ---
        abc_df = sales_df[sales_df['sku'].isin(import_list)]
        abc_df = abc_df[abc_df['category'].isin(cats_to_display)]
        abc_df = abc_df.dropna(subset=['landing cost', 'quantity'])
        item_consumption = abc_df.groupby(['sku', 'display_name']).apply(lambda x: (x['quantity'] * x['landing cost']).sum()).sort_values(ascending=False).reset_index(name='consumption_value')
        
        abc_summary_table = dbc.Table()
        abc_data_json = None
        if not item_consumption.empty and item_consumption['consumption_value'].sum() > 0:
            total_value = item_consumption['consumption_value'].sum()
            item_consumption['percent_of_total'] = item_consumption['consumption_value'] / total_value
            item_consumption['cumulative_percent'] = (item_consumption['consumption_value'].cumsum() / total_value) * 100
            def assign_abc_class(p): return 'A' if p <= 80 else 'B' if p <= 95 else 'C'
            item_consumption['class'] = item_consumption['cumulative_percent'].apply(assign_abc_class)
            abc_data_json = item_consumption.to_json(orient='split')
            class_counts = item_consumption['class'].value_counts().reset_index()

            # <-- MODIFIED: Sort the ABC summary table by class A, B, C -->
            class_counts['class'] = pd.Categorical(class_counts['class'], categories=['A', 'B', 'C'], ordered=True)
            class_counts = class_counts.sort_values('class')
            
            table_header = [html.Thead(html.Tr([html.Th("Class"), html.Th("No. of SKUs")]))]
            table_body = [html.Tbody([html.Tr([html.Td(row['class']), html.Td(row['count'])]) for index, row in class_counts.iterrows()])]
            abc_summary_table = dbc.Table(table_header + table_body, bordered=True, striped=True, hover=True)

        # --- 6. At-Risk Inventory Table ---
        risk_df = inv_master_df.copy()
        risk_df = risk_df[risk_df['category'].isin(cats_to_display)]
        risk_df['total_supply'] = risk_df['inv'] + risk_df['intransit'] + risk_df['production']
        
        avg_daily_sales = sales_df[sales_df['orderdate'] > sales_df['orderdate'].max() - pd.Timedelta(days=30)].groupby('sku')['quantity'].sum() / 30
        risk_df = pd.merge(risk_df, avg_daily_sales.rename('avg_daily_qty'), on='sku', how='left').fillna(0)
        
        risk_df['days_of_supply_left'] = risk_df.apply(lambda r: r['total_supply'] / r['avg_daily_qty'] if r['avg_daily_qty'] > 0 else np.inf, axis=1)
        at_risk_items = risk_df[risk_df['days_of_supply_left'] < 60].sort_values('days_of_supply_left')
        
        display_cols = {'display_name': 'Item Name', 'category': 'Category', 'inv': 'In Stock', 'intransit': 'In Transit', 'production': 'In Prod.', 'days_of_supply_left': 'Days Left'}
        at_risk_data = at_risk_items.rename(columns=display_cols)[list(display_cols.values())].to_dict('records')
        for row in at_risk_data: row['Days Left'] = int(row['Days Left']) if np.isfinite(row['Days Left']) else 'inf'
        at_risk_cols = [{"name": i, "id": i} for i in display_cols.values()]
            
        return inventory_kpis, fig_in_stock, abc_summary_table, at_risk_data, at_risk_cols, abc_data_json

    @app.callback(
        Output("download-at-risk-csv", "data"),
        Input("download-at-risk-button", "n_clicks"),
        State("at-risk-table", "data"),
        prevent_initial_call=True)
    def download_at_risk_data(n_clicks, table_data):
        if not table_data:
            raise PreventUpdate
        df_to_download = pd.DataFrame(table_data)
        return dcc.send_data_frame(df_to_download.to_csv, "at_risk_inventory.csv", index=False)

    @app.callback(
        Output("download-abc-component", "data"),
        Input("download-abc-csv", "n_clicks"),
        [State("abc-analysis-data-store", "data"), State("merged-data-store", "data")],
        prevent_initial_call=True)
    def download_abc_analysis(n_clicks, abc_json, merged_json):
        if not abc_json or not merged_json: raise PreventUpdate
        abc_df = pd.read_json(abc_json, orient='split')
        df = pd.read_json(merged_json, orient='split')
        
        df['orderdate'] = pd.to_datetime(df['orderdate'])
        
        risk_df = df.drop_duplicates(subset=['sku']).copy()
        for col in ['inv', 'intransit', 'production']: risk_df[col] = pd.to_numeric(risk_df[col], errors='coerce').fillna(0)
        risk_df['total_supply'] = risk_df['inv'] + risk_df['intransit'] + risk_df['production']
        avg_daily_sales = df[df['orderdate'] > df['orderdate'].max() - pd.Timedelta(days=30)].groupby('sku')['quantity'].sum() / 30
        risk_df = pd.merge(risk_df, avg_daily_sales.rename('avg_daily_qty'), on='sku', how='left').fillna(0)
        risk_df['days_of_supply_left'] = risk_df.apply(lambda r: r['total_supply'] / r['avg_daily_qty'] if r['avg_daily_qty'] > 0 else np.inf, axis=1)
        
        abc_df = pd.merge(abc_df, risk_df[['sku', 'inv', 'intransit', 'production', 'days_of_supply_left']], on='sku', how='left')

        output_cols = ['display_name', 'sku', 'class', 'consumption_value', 'percent_of_total', 'cumulative_percent', 'inv', 'intransit', 'production', 'days_of_supply_left']
        abc_df_to_export = abc_df[[col for col in output_cols if col in abc_df.columns]]
        
        header = """# ABC Analysis Data Explanation
    # display_name: The name of the item for display.
    # sku: The master unique identifier for the item.
    # class: The ABC class (A, B, or C) assigned to the item based on consumption value (A=Top 80%, B=Next 15%, C=Bottom 5%).
    # consumption_value: Total value consumed over the period (Quantity Sold * Landing Cost).
    # percent_of_total: The item's percentage contribution to the total consumption value.
    # cumulative_percent: The cumulative percentage of consumption value used for ranking.
    # inv: Current inventory on hand.
    # intransit: Inventory currently in transit.
    # production: Inventory currently in production.
    # days_of_supply_left: Estimated days of supply remaining based on the last 30 days of sales.
    # --- Data Starts Below ---
    """
        
        csv_string = abc_df_to_export.to_csv(index=False)
        full_content = header + csv_string

        return dict(content=full_content, filename="abc_analysis_details.csv")
