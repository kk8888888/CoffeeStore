import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime

app = Flask(__name__)
DATABASE = 'stock.db'
CHART_DIR = 'static/images'
CHART_FILENAME = 'stock_analysis.png'

# Ensure the chart directory exists
os.makedirs(CHART_DIR, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # Allows accessing columns by name
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            record_date TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Initialize the database when the app starts
with app.app_context():
    init_db()

@app.route('/')
def index():
    conn = get_db_connection()
    # Get current stock levels (latest entry for each item)
    # This query gets the latest quantity for each item based on the record_date
    current_stock_query = """
        SELECT sh.item_name, sh.quantity
        FROM stock_history sh
        INNER JOIN (
            SELECT item_name, MAX(record_date) as max_date
            FROM stock_history
            GROUP BY item_name
        ) AS latest_records
        ON sh.item_name = latest_records.item_name AND sh.record_date = latest_records.max_date
    """
    current_stock = conn.execute(current_stock_query).fetchall()
    conn.close()
    return render_template('index.html', stock_items=current_stock)

@app.route('/add_item', methods=('GET', 'POST'))
def add_item():
    if request.method == 'POST':
        item_name = request.form['item_name']
        quantity = request.form['quantity']
        record_date_str = request.form['record_date']

        if not item_name or not quantity or not record_date_str:
            # Handle error: Missing fields
            return "Missing fields!", 400
        
        try:
            quantity = int(quantity)
            if quantity < 0:
                return "Quantity cannot be negative!", 400
            # Validate date format (optional, but good practice)
            datetime.strptime(record_date_str, '%Y-%m-%d') 
        except ValueError:
            return "Invalid quantity or date format (YYYY-MM-DD)!", 400

        conn = get_db_connection()
        conn.execute('INSERT INTO stock_history (item_name, quantity, record_date) VALUES (?, ?, ?)',
                     (item_name, quantity, record_date_str))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add_item.html')

@app.route('/analysis')
def analysis():
    conn = get_db_connection()
    stock_data = conn.execute('SELECT item_name, quantity, record_date FROM stock_history ORDER BY record_date').fetchall()
    conn.close()

    if not stock_data:
        return render_template('analysis.html', chart_exists=False)

    df = pd.DataFrame(stock_data, columns=['item_name', 'quantity', 'record_date'])
    df['record_date'] = pd.to_datetime(df['record_date'])

    # Generate a bar chart for current stock levels
    # Need to get the latest quantity for each item for this chart
    current_stock_df = df.sort_values('record_date').drop_duplicates('item_name', keep='last')
    
    plt.figure(figsize=(10, 6))
    plt.bar(current_stock_df['item_name'], current_stock_df['quantity'], color='skyblue')
    plt.xlabel('Item Name')
    plt.ylabel('Current Quantity')
    plt.title('Current Stock Levels')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    chart_path = os.path.join(CHART_DIR, CHART_FILENAME)
    plt.savefig(chart_path)
    plt.close() # Close the plot to free memory

    return render_template('analysis.html', chart_exists=True, chart_url=f'/{CHART_DIR}/{CHART_FILENAME}')

# Serve static files (like images)
@app.route(f'/{CHART_DIR}/<path:filename>')
def serve_chart(filename):
    return send_from_directory(CHART_DIR, filename)

if __name__ == '__main__':
    app.run(debug=True)