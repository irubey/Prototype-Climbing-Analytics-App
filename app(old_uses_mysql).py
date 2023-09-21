from flask import Flask, render_template, request, redirect, url_for
from flask_mysqldb import MySQL
from initial_calculations import perform_calculations
import pandas as pd
import numpy as np
import json
from datetime import date
from collections import defaultdict
import os


app = Flask(__name__)
app.static_folder = 'static'

#Database setup
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'ISRgo#6!'
app.config['MYSQL_DB'] = 'flask_app_db'

mysql = MySQL(app)


#Custom JSON encoder to handle datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)

#Helper Functions
def update_row_in_table(table_name, row_id, data):
    cursor = mysql.connection.cursor()

    # Constructing the update query based on the data keys and the given row_id
    columns = ', '.join(f"{key} = %s" for key in data.keys())
    values = tuple(data.values())

    update_query = f"UPDATE {table_name} SET {columns} WHERE id = %s"
    cursor.execute(update_query, (*values, row_id))

    mysql.connection.commit()
    cursor.close()

def update_calculated_data(calculated_data):
    def save_dataframe_to_table(df, table_name):
        cursor = mysql.connection.cursor()

        df = df.where(pd.notnull(df), np.nan)  # Replace NaN values with np.nan

        for _, row in df.iterrows():
            columns = ', '.join(row.index)
            values = tuple([None if pd.isna(val) else val for val in row.values])
            placeholders = ', '.join(['NULL' if pd.isna(val) else '%s' for val in row.values])

            # Filter out columns with NULL values
            filtered_columns = [col for col, val in zip(row.index, row.values) if not pd.isna(val)]
            filtered_values = tuple(val for val in row.values if not pd.isna(val))
            filtered_placeholders = ', '.join(['%s' for _ in filtered_columns])

            # Insert a new row
            query = f"INSERT INTO {table_name} ({', '.join(filtered_columns)}) VALUES ({filtered_placeholders})"
            cursor.execute(query, filtered_values)

        # Drop duplicate rows based on 'route_name' and 'tick_date', keeping the row with higher ID value
        drop_duplicates_query = f"DELETE t1 FROM {table_name} t1 INNER JOIN {table_name} t2 WHERE t1.id < t2.id AND t1.route_name = t2.route_name AND t1.tick_date = t2.tick_date"
        cursor.execute(drop_duplicates_query)

        mysql.connection.commit()
        cursor.close()

    save_dataframe_to_table(calculated_data['sport_pyramid'], 'sport_pyramid')
    save_dataframe_to_table(calculated_data['trad_pyramid'], 'trad_pyramid')
    save_dataframe_to_table(calculated_data['boulder_pyramid'], 'boulder_pyramid')
    save_dataframe_to_table(calculated_data['user_ticks'], 'user_ticks')

def retrieve_data_from_table(table_name, username):
    if table_name == 'binned_code_dict':
        cursor = mysql.connection.cursor()
        query = f"SELECT * FROM {table_name}"
        cursor.execute(query)
        rows = cursor.fetchall()
      
        column_names = [desc[0] for desc in cursor.description]

        
        data = [dict(zip(column_names, row)) for row in rows]

        cursor.close()

        return data
    else:
        cursor = mysql.connection.cursor()

        # Execute a SELECT query to retrieve the data for the given username
        query = f"SELECT * FROM {table_name} WHERE username = %s"
        cursor.execute(query, (username,))

        # Fetch all the rows from the result set
        rows = cursor.fetchall()

        # Get the column names from the cursor description
        column_names = [desc[0] for desc in cursor.description]

        # Create a list of dictionaries representing each row
        data = [dict(zip(column_names, row)) for row in rows]

        cursor.close()

        return data

def convert_data_to_json(username):
    sport_pyramid = json.dumps((retrieve_data_from_table('sport_pyramid', username=username)),cls=CustomJSONEncoder).replace("'", r"\'").replace('"', r'\"')
    trad_pyramid = json.dumps((retrieve_data_from_table('trad_pyramid', username=username)),cls = CustomJSONEncoder).replace("'", r"\'").replace('"', r'\"')
    boulder_pyramid = json.dumps((retrieve_data_from_table('boulder_pyramid', username=username)), cls = CustomJSONEncoder).replace("'", r"\'").replace('"', r'\"')
    user_ticks = json.dumps((retrieve_data_from_table('user_ticks', username=username)), cls = CustomJSONEncoder).replace("'", r"\'").replace('"', r'\"')
    binned_code_dict = json.dumps((retrieve_data_from_table('binned_code_dict', username=username)), cls = CustomJSONEncoder).replace("'", r"\'").replace('"', r'\"')
    return sport_pyramid,trad_pyramid,boulder_pyramid,user_ticks,binned_code_dict

#ROUTES
@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Retrieve first input from the form
        first_input = request.form.get('first_input')

        # Perform calculations on the first input
        sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, username = perform_calculations(first_input)

        # Update the calculated data 
        update_calculated_data({
            'sport_pyramid': sport_pyramid,
            'trad_pyramid': trad_pyramid,
            'boulder_pyramid': boulder_pyramid,
            'user_ticks': user_ticks
        })

        # Redirect the user to the pyramid_input route with the calculated data and first input
        return redirect(url_for('userviz', username=username))

    return render_template('index.html')

@app.route("/userviz")
def userviz():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    return render_template('userViz.html', username = username)

@app.route("/performance-pyramid")
def performance_pyramid():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, binned_code_dict =convert_data_to_json(username)

    return render_template('performancePyramid.html', username = username, sport_pyramid = sport_pyramid, trad_pyramid = trad_pyramid, boulder_pyramid = boulder_pyramid, user_ticks = user_ticks, binned_code_dict = binned_code_dict)

@app.route("/pyramid-input", methods=['GET', 'POST'])
def pyramid_input():
    if request.method == 'POST':
        form_data = request.form.to_dict(flat=True)
        structured_data = defaultdict(dict)
        
        # Retrieve the username for redirection, and remove it from form_data
        username = form_data.pop('username', None)

        for key, value in form_data.items():
            parts = key.split('_')
            attribute = '_'.join(parts[:-1])
            row_id = parts[-1]
            structured_data[row_id][attribute] = value

        # Update the database with the structured data
        for row_id, data in structured_data.items():
            update_row_in_table('sport_pyramid', row_id, data)
            update_row_in_table('trad_pyramid', row_id, data)
            update_row_in_table('boulder_pyramid', row_id, data)

        return redirect(url_for('performance_characteristics', username=username))

    username = request.args.get('username')
    sport_pyramid = retrieve_data_from_table('sport_pyramid', username)
    trad_pyramid = retrieve_data_from_table('trad_pyramid', username)
    boulder_pyramid = retrieve_data_from_table('boulder_pyramid', username)

    return render_template('pyramidInputs.html', username=username, sport_pyramid=sport_pyramid, trad_pyramid=trad_pyramid, boulder_pyramid=boulder_pyramid)

@app.route("/performance-characteristics")
def performance_characteristics():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, binned_code_dict =convert_data_to_json(username)

    return render_template('performanceCharacteristics.html', username = username, sport_pyramid = sport_pyramid, trad_pyramid = trad_pyramid, boulder_pyramid = boulder_pyramid, user_ticks = user_ticks, binned_code_dict = binned_code_dict)

@app.route("/base-volume")
def base_volume():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, binned_code_dict =convert_data_to_json(username)

    return render_template('baseVolume.html', username = username, sport_pyramid = sport_pyramid, trad_pyramid = trad_pyramid, boulder_pyramid = boulder_pyramid, user_ticks = user_ticks, binned_code_dict = binned_code_dict)

@app.route("/when-where")
def when_where():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, binned_code_dict =convert_data_to_json(username)

    return render_template('whenWhere.html', username = username, sport_pyramid = sport_pyramid, trad_pyramid = trad_pyramid, boulder_pyramid = boulder_pyramid, user_ticks = user_ticks, binned_code_dict = binned_code_dict)

@app.route("/progression")
def progression():
    # Retrieve the username from the query parameters
    username = request.args.get('username')

    sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, binned_code_dict =convert_data_to_json(username)

    return render_template('progression.html', username = username, sport_pyramid = sport_pyramid, trad_pyramid = trad_pyramid, boulder_pyramid = boulder_pyramid, user_ticks = user_ticks, binned_code_dict = binned_code_dict)

if __name__ == "__main__":
    app.run(debug=True)
