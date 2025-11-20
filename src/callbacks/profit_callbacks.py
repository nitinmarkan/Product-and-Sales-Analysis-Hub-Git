from dash import Input, Output, State, html, dcc, dash_table
from dash.exceptions import PreventUpdate
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc

def register_profit_callbacks(app):
    @app.callback(
        [Output('profit-kpi-row', 'children'),
        Output('profit-by-customer-chart', 'figure'),
        Output('top-profitable-items-chart', 'figure'),
        Output('margin-by-category-chart', 'figure')],
        [Input('merged-data-store', 'data'), Input('date-range-picker', 'start_date'),
        Input('date-range-picker', 'end_date'), Input('profit-item-dropdown', 'value'),
        Input('profit-customer-dropdown', 'value'),
        Input('profit-category-dropdown', 'value')])
    def update_profitability_tab(merged_json, start_date, end_date, items, customers, categories):
        if not all([merged_json, start_date, end_date]): raise PreventUpdate
        df = pd.read_json(merged_json, orient='split')
        df['orderdate'] = pd.to_datetime(df['orderdate'])
        
        # Profitability tab is now implicitly for import items only due to the dropdown
        dff = df.copy()
        dff = dff[(dff['orderdate'] >= pd.to_datetime(start_date)) & (dff['orderdate'] <= pd.to_datetime(end_date))]
        if items: dff = dff[dff['sku'].isin(items)]
        if customers: dff = dff[dff['customer name'].isin(customers)]
        if categories: dff = dff[dff['category'].isin(categories)]

        total_profit = dff['profit'].sum()
        avg_margin = (dff['profit'].sum() / dff['sales'].sum()) * 100 if dff['sales'].sum() > 0 else 0
        profit_kpis = [
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Total Profit"), html.H4(f"${total_profit:,.0f}")]))),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Average Profit Margin"), html.H4(f"{avg_margin:.1f}%")]))),
        ]

        fig_profit_customer = go.Figure(layout_title_text="Profit by Customer")
        if not dff.empty:
            customer_profit = dff.groupby('customer name')['profit'].sum().nlargest(15).reset_index()
            fig_profit_customer.add_trace(go.Bar(x=customer_profit['customer name'], y=customer_profit['profit'], text=customer_profit['profit'], texttemplate='$%{y:,.0f}', textposition='auto'))
            fig_profit_customer.update_layout(title_text="Profit by Customer", xaxis_tickangle=-45)

        fig_top_profit_items = go.Figure(layout_title_text="Top 10 Most Profitable Items")
        if not dff.empty:
            item_profit = dff.groupby('display_name')['profit'].sum().nlargest(10).reset_index()
            fig_top_profit_items.add_trace(go.Bar(x=item_profit['display_name'], y=item_profit['profit'], text=item_profit['profit'], texttemplate='$%{y:,.0f}', textposition='auto'))
            fig_top_profit_items.update_layout(title_text="Top 10 Most Profitable Items")

        fig_margin_category = go.Figure(layout_title_text="Average Margin by Category")
        if not dff.empty and 'category' in dff.columns:
            margin_df = dff[~dff['category'].isin(['closeout', 'discontinued'])]
            category_profit = margin_df.groupby('category').agg(total_profit=('profit', 'sum'), total_sales=('sales', 'sum')).reset_index()
            category_profit['avg_margin'] = (category_profit['total_profit'] / category_profit['total_sales'] * 100)
            fig_margin_category.add_trace(go.Bar(x=category_profit['category'], y=category_profit['avg_margin'], text=category_profit['avg_margin'], texttemplate='%{y:.1f}%', textposition='auto'))
            fig_margin_category.update_layout(title_text="Average Margin % by Category")

        return profit_kpis, fig_profit_customer, fig_top_profit_items, fig_margin_category
