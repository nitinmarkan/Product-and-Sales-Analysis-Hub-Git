from dash import Input, Output, State, html, dcc, dash_table
from dash.exceptions import PreventUpdate
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from prophet import Prophet
from plotly.subplots import make_subplots

def register_forecast_callbacks(app):
    @app.callback(
        [Output('forecast-chart', 'figure'), Output('forecast-kpi-row', 'children'),
        Output('forecast-decomposition-chart', 'figure')],
        [Input('forecast-item-dropdown', 'value'), Input('merged-data-store', 'data'),
        Input('import-list-store', 'data'), Input('forecast-period-slider', 'value')])
    def update_forecast_chart(selected_item_key, merged_json, import_list, period):
        if not selected_item_key or not merged_json: 
            return go.Figure(layout_title_text="Select an import item to generate its forecast"), [], go.Figure()
        
        # This check is now implicit as the dropdown only contains import items.
        if import_list and (selected_item_key not in import_list): 
            return go.Figure(layout_title_text="This is not an Import item."), [], go.Figure()

        metric = 'quantity' # Hardcoded to quantity
        df = pd.read_json(merged_json, orient='split')
        df['orderdate'] = pd.to_datetime(df['orderdate'])
        item_df = df[df['sku'] == selected_item_key].copy()
        item_name = item_df['display_name'].iloc[0] if not item_df.empty else selected_item_key
        
        df_prophet = item_df.groupby(item_df['orderdate'].dt.date)[metric].sum().reset_index()
        df_prophet.rename(columns={'orderdate': 'ds', metric: 'y'}, inplace=True)
        
        df_prophet['ds'] = pd.to_datetime(df_prophet['ds'])

        if len(df_prophet) < 2: 
            return go.Figure(layout_title_text=f"Not enough data to forecast for {item_name}"), [], go.Figure()

        model = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True).fit(df_prophet)
        future = model.make_future_dataframe(periods=period)
        forecast = model.predict(future)

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_prophet['ds'], y=df_prophet['y'], mode='lines', name='Historical'))
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat'], mode='lines', name='Forecasted', line={'dash': 'dash'}))
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat_upper'], fill=None, mode='lines', line_color='rgba(0,0,0,0)', showlegend=False))
        fig.add_trace(go.Scatter(x=forecast['ds'], y=forecast['yhat_lower'], fill='tonexty', mode='lines', line_color='rgba(0,0,0,0)', name='Confidence Interval'))
        fig.update_layout(title=f'{period}-Day Quantity Forecast for {item_name}', xaxis_title='Date', yaxis_title='Quantity')

        future_forecast = forecast[forecast['ds'] > df_prophet['ds'].max()]
        predicted_total = future_forecast['yhat'].sum()
        lower_bound = future_forecast['yhat_lower'].sum()
        upper_bound = future_forecast['yhat_upper'].sum()

        historical_rate = df_prophet['y'][-30:].mean()
        forecast_rate = future_forecast['yhat'].mean()
        growth_pct = ((forecast_rate / historical_rate) - 1) * 100 if historical_rate > 0 else 0

        kpi_cards = [
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Predicted Total Quantity"), html.H4(f"{predicted_total:,.0f}")]))),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Expected Growth"), html.H4(f"{growth_pct:+.1f}%")]))),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Confidence Range"), html.H4(f"{lower_bound:,.0f} - {upper_bound:,.0f}")]))),
        ]

        fig_decomp = make_subplots(rows=2, cols=1, subplot_titles=('Trend', 'Weekly Seasonality'))
        fig_decomp.add_trace(go.Scatter(x=forecast['ds'], y=forecast['trend'], mode='lines', name='Trend'), row=1, col=1)
        weekly_data = forecast[['ds', 'weekly']].set_index('ds').resample('D').mean().ffill().reset_index()
        weekly_data['day_of_week'] = weekly_data['ds'].dt.day_name()
        weekly_seasonality = weekly_data.groupby('day_of_week')['weekly'].mean().reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
        fig_decomp.add_trace(go.Bar(x=weekly_seasonality.index, y=weekly_seasonality.values, name='Weekly'), row=2, col=1)
        fig_decomp.update_layout(title_text="Forecast Components")

        return fig, kpi_cards, fig_decomp
