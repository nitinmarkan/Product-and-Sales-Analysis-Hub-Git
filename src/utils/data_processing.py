import base64
import io
import pandas as pd

def parse_contents(contents, filename):
    if contents is None: return None
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename: df = pd.read_csv(io.StringIO(decoded.decode('utf-8', errors='ignore')))
        elif 'xls' in filename: df = pd.read_excel(io.BytesIO(decoded), sheet_name=None)
        else: return None
        if isinstance(df, dict): df = pd.concat(df.values(), ignore_index=True)
        df.columns = [str(col).strip().lower() for col in df.columns]
        return df
    except Exception as e: print(f"Error parsing {filename}: {e}"); return None
