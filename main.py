# --- IMPORTS ---
import duckdb
import time
import random
from datetime import datetime
from flask import Flask, render_template, jsonify 
import threading 

# --- CONFIGURATIE ---
# De naam van het databasebestand.
DATABASE_FILE = 'greenhouse.duckdb'
# Interval in seconden voor het nemen van nieuwe metingen
MEASUREMENT_INTERVAL_SECONDS = 5 

# --- FUNCTIE: INITIALISATIE (Database Setup) ---
def initialize_database():
    """Maakt de DuckDB connectie en zorgt dat de sensordata tabel bestaat."""
    
    con = duckdb.connect(database=DATABASE_FILE)
    
    con.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            timestamp TIMESTAMP,
            soil_moisture FLOAT,
            temperature FLOAT,
            humidity FLOAT,
            ph_level FLOAT,
            light_level INTEGER
        )
    """)
    
    con.close()
    print(f"Database '{DATABASE_FILE}' en tabel 'sensor_data' succesvol geïnitialiseerd.")


# --- FUNCTIES: DATA GENERATIE ---
def generate_realistic_data():
    """Genereert één set realistische sensor data op basis van de huidige tijd."""
    
    now = datetime.now()
    hour = now.hour
    
    # --- 1. Temperatuur ---
    temp_base = 20.0
    if 10 <= hour <= 18:
        temp_base += 5.0 
    temperature = round(random.uniform(temp_base - 1.5, temp_base + 1.5), 2)
    
    
    # --- 2. Lichtintensiteit ---
    light_level = 0
    if 6 <= hour <= 20:
        light_level = random.randint(350, 600)
    else:
        light_level = random.randint(10, 50) 
        
        
    # --- 3. Andere waarden ---
    soil_moisture = round(random.uniform(85.0, 90.0), 2) 
    humidity = round(random.uniform(80.0, 90.0), 2)      
    ph_level = round(random.uniform(5.5, 6.0), 2)        
    
    
    data = {
        'timestamp': now,
        'soil_moisture': soil_moisture,
        'temperature': temperature,
        'humidity': humidity,
        'ph_level': ph_level,
        'light_level': light_level
    }
    
    return data


# --- FUNCTIES: DATA OPSLAG ---
def insert_data_to_db(data):
    """Slaat een set data op in de sensor_data tabel."""
    
    con = duckdb.connect(database=DATABASE_FILE)
    
    con.execute("""
        INSERT INTO sensor_data (
            timestamp, soil_moisture, temperature, humidity, ph_level, light_level
        )
        VALUES (
            $timestamp, $soil_moisture, $temperature, $humidity, $ph_level, $light_level
        )
    """, data)
    
    con.close()
    
    
def take_and_store_measurement():
    """Genereert één meting en slaat deze op in de database."""
    data = generate_realistic_data()
    insert_data_to_db(data)
    print(f"INFO: Nieuwe meting opgeslagen om {data['timestamp'].strftime('%H:%M:%S')}")
    return data


# --- FUNCTIES: DATA OPHALEN ---

def get_latest_sensor_data():
    """Haalt de meest recente sensordata op uit de database."""
    
    con = duckdb.connect(database=DATABASE_FILE)
    
    # SQL-query om de laatste rij op te halen
    query = """
    SELECT 
        soil_moisture, temperature, humidity, ph_level, light_level
    FROM 
        sensor_data 
    ORDER BY 
        timestamp DESC 
    LIMIT 1
    """
    
    columns = [col[0] for col in con.execute(query).description]
    result = con.execute(query).fetchone()
    con.close()
    
    if result:
        # Combineer de kolomnamen en de waarden tot een Python dictionary
        return dict(zip(columns, result))
    else:
        # Geen data in de DB, geef veilige standaardwaarden
        return {
            'soil_moisture': 0.0, 'temperature': 0.0, 
            'humidity': 0.0, 'ph_level': 0.0, 'light_level': 0
        }

def get_historical_temperature_data(hours=8):
    """Haalt de historische temperatuurdata van de laatste X uur op voor de grafiek."""
    
    # Bereken de tijd van X uur geleden
    time_threshold = datetime.now() - timedelta(hours=hours)
    
    con = duckdb.connect(database=DATABASE_FILE)
    
    # Selecteer de temperatuur en het uur (afgerond op het dichtstbijzijnde kwartier)
    # van de laatste 8 uur. Dit zorgt voor een beheersbare hoeveelheid punten.
    query = f"""
    SELECT 
        STRFTIME(TIMESTAMP, '%H:%M') AS time_label,
        AVG(temperature) AS avg_temp
    FROM 
        sensor_data
    WHERE 
        timestamp >= '{time_threshold.strftime('%Y-%m-%d %H:%M:%S')}'
    GROUP BY 
        time_label
    ORDER BY 
        time_label ASC;
    """
    
    # We gebruiken een simpelere query voor de initiele setup:
    query_simple = """
    SELECT 
        STRFTIME(timestamp, '%H:%M') AS time_label,
        temperature
    FROM 
        sensor_data
    ORDER BY 
        timestamp DESC
    LIMIT 15;
    """

    # We draaien de resultaten om om van oud naar nieuw te sorteren
    results = con.execute(query_simple).fetchall()
    con.close()
    
    # Zet de data om in twee lijsten: labels (tijdstippen) en data (temperatuur)
    labels = [row[0] for row in results]
    data = [row[1] for row in results]
    
    # Draai de lijsten om zodat ze van oud naar nieuw gaan
    return {'labels': labels[::-1], 'data': data[::-1]}


# --- THREAD: AUTOMATISCHE METINGEN ---
def measurement_scheduler():
    """Loopt continu om metingen te nemen met een vast interval."""
    # Voorkom dat de scheduler de Flask 'context' van de hoofddraad overneemt.
    # We gebruiken hier alleen de database, dus dat is veilig.
    while True:
        take_and_store_measurement()
        time.sleep(MEASUREMENT_INTERVAL_SECONDS)
        
# =========================================================================
# === FLASK BACKEND SETUP =================================================
# =========================================================================

# Flask app initialiseren
app = Flask(__name__)

# --- ROUTE: DASHBOARD WEERGEVEN ---
@app.route('/')
def index():
    """Toont de hoofdpagina (het Greenhouse Dashboard) en geeft de laatste data mee."""
    
    # 1. Haal de laatste meting op uit de database
    latest_data = get_latest_sensor_data()
    
    # 2. Haal de historische data voor de grafiek op
    history_data = get_historical_temperature_data()

    # 3. Geef de data door aan de HTML-template
    return render_template(
        'index.html', 
        **latest_data, # De losse sensordata voor de tegels
        chart_labels=history_data['labels'],
        chart_data=history_data['data']
    ) 


# --- ROUTE: API voor Live Updates (JSON) ---
@app.route('/api/latest_data', methods=['GET'])
def latest_data_api():
    """Geeft de meest recente sensordata terug als JSON."""
    
    # Haal alleen de losse sensordata op voor de AJAX update
    latest_data = get_latest_sensor_data()
    
    # Flask's jsonify zet de Python dictionary om in JSON
    return jsonify(latest_data)

# --- ROUTE: API voor Grafiek Updates (JSON) ---
@app.route('/api/chart_data', methods=['GET'])
def chart_data_api():
    """Geeft de historische data voor de grafiek terug als JSON."""
    
    # Haal de historische data op
    history_data = get_historical_temperature_data()
    
    # Geef de data terug in een JSON-formaat dat Chart.js kan verwerken
    return jsonify(history_data)


# --- START APPLICATIE ---
if __name__ == '__main__':
    # Importeer timedelta pas hier om de imports bovenaan schoon te houden, 
    # of voeg deze toe aan de imports bovenaan (aanbevolen)
    from datetime import timedelta # Noodzakelijk voor historische data
    
    # Initialiseer de database één keer voordat de server start
    initialize_database() 
    
    # Start de automatische metingen in een aparte thread
    scheduler_thread = threading.Thread(target=measurement_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Start de webserver.
    app.run(debug=True, use_reloader=False)