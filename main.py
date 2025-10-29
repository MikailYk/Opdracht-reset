# --- IMPORTS ---
import duckdb
import time
import random
# BELANGRIJKE FIX: timedelta is nu bovenaan geimporteerd
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import threading 

# --- CONFIGURATIE ---
# De naam van het databasebestand.
DATABASE_FILE = 'greenhouse.duckdb'
# Interval in seconden voor het nemen van nieuwe metingen
MEASUREMENT_INTERVAL_SECONDS = 5 

# BELANGRIJK: Dit moet een lange, willekeurige en GEHEIME string zijn!
app = Flask(__name__)
app.secret_key = 'een_heel_geheim_en_moeilijk_te_raden_sleutel_voor_beveiliging'

# NIEUW: Detailinformatie en configuratie voor elke sensor
SENSOR_DETAILS = {
    "Temperature": {'db_key': 'temperature', 'unit': '°C', 'icon': 'fa-temperature-three-quarters', 'color': '#dc3545', 'description': "Luchttemperatuur: Beïnvloedt de snelheid van fotosynthese en transpiratie. Te heet vertraagt groei, te koud beschadigt de cellen.", 'min_alert': 22, 'max_alert': 34},
    "Humidity": {'db_key': 'humidity', 'unit': '%', 'icon': 'fa-droplet', 'color': '#00bcd4', 'description': "Luchtvochtigheid: Relatief aan transpiratie van de plant. Te laag maakt bladeren droog; te hoog vergroot de kans op schimmel.", 'min_alert': 65, 'max_alert': 90},
    "Soil Moisture": {'db_key': 'soil_moisture', 'unit': '%', 'icon': 'fa-water', 'color': '#0d6efd', 'description': "Bodemvochtigheid: Essentieel voor wateropname van de plant. Te laag leidt tot uitdroging; te hoog kan wortelrot veroorzaken.", 'min_alert': 60, 'max_alert': 95},
    "Light Level": {'db_key': 'light_level', 'unit': ' lux', 'icon': 'fa-sun', 'color': '#ffc107', 'description': "Lichtintensiteit: De energiebron voor fotosynthese. Te weinig licht leidt tot zwakke groei; te veel kan de bladeren verbranden.", 'min_alert': 400, 'max_alert': 700},
    "pH Level": {'db_key': 'ph_level', 'unit': '', 'icon': 'fa-square-check', 'color': '#4caf50', 'description': "Water pH (zuurgraad): Bepaalt hoe goed de plant voedingsstoffen kan opnemen. Een afwijkende pH blokkeert de voedingsstroom.", 'min_alert': 5.5, 'max_alert': 6.5}
}


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
    temp_base = 25.0 # Iets warmer in een kas
    if 10 <= hour <= 18:
        temp_base += 5.0 
    temperature = round(random.uniform(temp_base - 1.5, temp_base + 1.5), 2)
    
    
    # --- 2. Lichtintensiteit ---
    light_level = 0
    if 6 <= hour <= 20:
        light_level = random.randint(450, 750) # Hoger in de kas
    else:
        light_level = random.randint(10, 50) 
        
        
    # --- 3. Andere waarden ---
    soil_moisture = round(random.uniform(70.0, 95.0), 2) # Realistisch bereik voor hydro
    humidity = round(random.uniform(75.0, 95.0), 2) 	 
    ph_level = round(random.uniform(5.5, 6.5), 2) 	 	 
    
    
    data = {
        'timestamp': now,
        'soil_moisture': soil_moisture,
        'temperature': temperature,
        'humidity': humidity,
        'ph_level': ph_level,
        'light_level': light_level
    }
    
    return data


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
    
# --- FUNCTIES: DATA OPSLAG (MET DEMO-TRUC) ---
def take_and_store_measurement():
    """Genereert één meting en slaat deze op in de database."""
    
    # 1. De normale, huidige meting
    current_data = generate_realistic_data()
    insert_data_to_db(current_data)
    print(f"INFO: Nieuwe meting opgeslagen om {current_data['timestamp'].strftime('%H:%M:%S')}")

    # 2. DE DEMO-TRUC: Genereer en sla ook data op voor verschillende momenten in het verleden.
    # Dit zorgt ervoor dat de grafieken altijd data hebben om te tonen, ongeacht de tijdsperiode.
    # We gebruiken timedelta om terug in de tijd te gaan.
    historical_offsets = [
        timedelta(hours=2), timedelta(hours=8), timedelta(days=1), 
        timedelta(days=3), timedelta(days=6)
    ]
    
    for offset in historical_offsets:
        fake_historical_data = generate_realistic_data() # Genereer nieuwe random waarden
        fake_historical_data['timestamp'] = datetime.now() - offset # OVERSCHRIJF de timestamp
        insert_data_to_db(fake_historical_data)


# --- FUNCTIES: DATA OPHALEN ---

# Om handmatig alle data te wissen
def clear_all_sensor_data():
    """WIST ALLE DATA uit de sensor_data tabel!"""
    con = duckdb.connect(database='greenhouse.duckdb')
    try:
        # TRUNCATE TABLE is de snelste manier om een hele tabel leeg te maken.
        con.execute("TRUNCATE TABLE sensor_data")
        print("\n=== SUCCESS: ALLE OUDE DATA IS VERWIJDERD! ===\n")
    except Exception as e:
        print(f"Fout bij het opschonen van data: {e}")
    finally:
        con.close()
        
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

# NIEUWE FUNCTIE: Om historische data voor ELKE sensor op te halen
def get_historical_sensor_data(db_column, hours=24, limit=150):
    """Haalt de historische data van de laatste X uur op voor een specifieke kolom."""
    
    con = duckdb.connect(database=DATABASE_FILE)
    
    # NIEUW: Bepaal het juiste formaat voor de tijd-labels op basis van de periode.
    # Dit maakt de x-as van de grafiek veel logischer.
    if int(hours) <= 24:
        # Voor periodes tot een dag, toon Uur:Minuut
        time_format = '%H:%M'
    else:
        # Voor langere periodes (zoals 7 dagen), toon Dag-Maand
        time_format = '%d-%m'

    # We gebruiken nu de dynamische 'time_format' variabele in de query.
    # De rest van de query blijft hetzelfde.
    query = f"""
    SELECT 
        STRFTIME(timestamp, '{time_format}') AS time_label,
        {db_column}
    FROM 
        sensor_data
    WHERE timestamp >= now() - INTERVAL '{int(hours)}' HOUR
    ORDER BY 
        timestamp ASC
    """
    
    results = con.execute(query).fetchall()
    con.close()
    
    # Draai de lijsten om zodat ze van oud naar nieuw gaan voor de grafiek
    labels = [row[0] for row in results]
    data = [row[1] for row in results]
    
    return {'labels': labels, 'data': data}


# FUNCTIE OPNIEUW DEFINIEREN (Gebruikt nu de nieuwe generieke functie)
def get_historical_temperature_data(hours=8):
    """Haalt de historische temperatuurdata op (gebruikt voor het Dashboard)."""
    # Haalt de data van de 'temperature' kolom op, beperkt tot 8 uur / 15 metingen
    return get_historical_sensor_data('temperature', hours=8, limit=15)


# --- THREAD: AUTOMATISCHE METINGEN ---
def measurement_scheduler():
    """Loopt continu om metingen te nemen met een vast interval."""
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
        chart_data=history_data['data'],
        active_page='dashboard' # NIEUW: Vertelt de template welke link actief is
    ) 

# --- ROUTE: CONTROLS WEERGEVEN (Nieuwe Route) ---
@app.route('/controls')
def controls():
    """Toont de Controls pagina."""
    return render_template('controls.html', active_page='controls')


# NIEUWE ROUTE: Detail View voor elke sensor
@app.route('/detail/<sensor_name>')
def detail_view(sensor_name):
    """Toont de detailpagina voor een specifieke sensor."""
    
    # Controleer of de gevraagde sensor bestaat in de configuratie
    if sensor_name not in SENSOR_DETAILS:
        # GEFIXTE FOUTAFHANDELING: Gebruik nu de placeholder.html template
        return render_template(
            'placeholder.html', 
            title=f"Fout 404: Sensor '{sensor_name}' niet gevonden"
        ), 404
        
    sensor_info = SENSOR_DETAILS[sensor_name]
    db_key = sensor_info['db_key']
    
    # Haal de historische data op (nu tot 24 uur / 150 metingen)
    history_data = get_historical_sensor_data(db_key, hours=24, limit=150)
    
    # Haal de meest recente waarde op om in de widget te tonen
    latest_data = get_latest_sensor_data()
    # Gebruik .get(..., 0.0) voor het geval de key mist
    latest_value = latest_data.get(db_key, 0.0) 

    return render_template(
        'detail_chart.html',
        sensor_name=sensor_name,
        latest_value=latest_value,
        chart_labels=history_data['labels'],
        chart_data=history_data['data'],
        # Geef alle details (unit, icon, color, description, alerts) mee aan de template
        **sensor_info, 
        active_page='climatic' # Om de sidebar te markeren
    )

# NIEUWE ROUTE: Een speciale pagina om alle data in de database te bekijken
@app.route('/bekijk-alle-data')
def view_all_data():
    """Toont een simpele tabel met alle opgeslagen sensordata."""
    
    con = duckdb.connect(database=DATABASE_FILE, read_only=True)
    
    # Haal alle data op, gesorteerd met de nieuwste meting bovenaan.
    query = "SELECT * FROM sensor_data ORDER BY timestamp DESC"
    
    # .fetchall() geeft een lijst van tuples, bv: [(ts1, val1, ...), (ts2, val2, ...)]
    all_data = con.execute(query).fetchall()
    
    # Haal ook de kolomnamen op voor de tabel-header in de HTML
    column_names = [col[0] for col in con.execute(query).description]
    
    con.close()
    
    return render_template('data_view.html', 
                           data=all_data, 
                           columns=column_names,
                           title="Database Inhoud",
                           active_page='database_view') # NIEUW: Markeer de zijbalk link

# NIEUWE ROUTE: Om de database te wissen via een POST-verzoek
@app.route('/clear-database', methods=['POST'])
def clear_database():
    """Wist alle data uit de sensor_data tabel en stuurt de gebruiker terug."""
    
    # Haal het wachtwoord op uit het formulier dat is meegestuurd.
    # .get('password', '') is een veilige manier: als het veld niet bestaat, krijgen we een lege string.
    submitted_password = request.form.get('password', '')
    
    # Controleer of het wachtwoord correct is.
    if submitted_password == 'doeidata':
        clear_all_sensor_data() # Roep de functie aan die de database leegmaakt
        # Stuur een JSON-response terug in plaats van een redirect
        return jsonify({'status': 'success', 'message': 'Database succesvol gewist! Alle sensordata is verwijderd.'})
    else:
        # Het wachtwoord was incorrect, wis de data NIET.
        # Stuur een JSON-response met een foutmelding terug
        return jsonify({'status': 'error', 'message': 'Incorrect wachtwoord. De database is NIET gewist.'})


# --- ROUTE: API voor Live Updates (JSON) ---
@app.route('/api/latest_data', methods=['GET'])
def latest_data_api():
    """Geeft de meest recente sensordata terug als JSON."""
    
    latest_data = get_latest_sensor_data()
    return jsonify(latest_data)

# --- ROUTE: API voor Grafiek Updates (JSON) ---
@app.route('/api/chart_data', methods=['GET'])
def chart_data_api():
    """Geeft de historische data voor de grafiek (temperatuur) terug als JSON."""
    
    history_data = get_historical_temperature_data()
    return jsonify(history_data)

# NIEUWE API ROUTE: Voor de dynamische detail-grafieken
@app.route('/api/historical_data/<sensor_name>', methods=['GET'])
def historical_data_api(sensor_name):
    """
    Geeft historische data voor een specifieke sensor en tijdsperiode terug.
    Wordt aangeroepen door de knoppen op de detailpagina.
    Voorbeeld URL: /api/historical_data/Temperature?hours=6
    """
    # 1. Haal het aantal uren op uit de URL (?hours=...). Standaard is 24.
    # We gebruiken request.args.get() om parameters uit de URL te lezen.
    try:
        hours = int(request.args.get('hours', 24))
    except ValueError:
        hours = 24 # Veilige standaardwaarde als er iets misgaat

    # 2. Controleer of de sensor bestaat en haal de database-kolomnaam op.
    if sensor_name in SENSOR_DETAILS:
        db_key = SENSOR_DETAILS[sensor_name]['db_key']
        # 3. Haal de data op met de juiste parameters.
        history_data = get_historical_sensor_data(db_key, hours=hours)
        return jsonify(history_data)
    else:
        # 4. Stuur een foutmelding als de sensor niet bekend is.
        return jsonify({'error': f'Sensor {sensor_name} not found'}), 404

# --- START APPLICATIE ---
if __name__ == '__main__':
    
    # Initialiseer de database één keer voordat de server start
    initialize_database() 

    # 🚨 EENMALIGE ACTIE: WIST DE DATABASE NU
    # clear_all_sensor_data()
    
    # Start de automatische metingen in een aparte thread
    scheduler_thread = threading.Thread(target=measurement_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Start de webserver. use_reloader=False is belangrijk voor de thread
    app.run(debug=True, use_reloader=False)