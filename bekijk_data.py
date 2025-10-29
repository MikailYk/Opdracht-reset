# bekijk_data.py

# We hebben alleen de duckdb bibliotheek nodig om de database te kunnen lezen.
import duckdb

# We moeten weten welk databasebestand we willen openen.
DATABASE_FILE = 'greenhouse.duckdb'


def toon_alle_data():
    """Maakt verbinding met de database, haalt alle rijen op en print ze."""
    
    print(f"--- Bezig met ophalen van alle data uit '{DATABASE_FILE}' ---")
    
    try:
        # 1. Maak verbinding met de database (alleen-lezen is veilig)
        con = duckdb.connect(database=DATABASE_FILE, read_only=True)
        
        # 2. Voer een SQL-query uit om alles op te halen, nieuwste eerst
        # SELECT * betekent "selecteer alle kolommen"
        # ORDER BY timestamp DESC betekent "sorteer op tijd, de nieuwste bovenaan"
        results = con.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC").fetchall()
        
        # 3. Print de resultaten
        if not results:
            print("De tabel 'sensor_data' is leeg. Er is nog geen data om te tonen.")
        else:
            print(f"Totaal {len(results)} metingen gevonden. De 20 meest recente zijn:")
            # We printen alleen de eerste 20 om de terminal niet te vol te maken
            for row in results[:20]:
                print(row)
                
    except Exception as e:
        print(f"Er is een fout opgetreden: {e}")
    finally:
        # 4. Sluit altijd de verbinding, ook als er een fout was
        if 'con' in locals():
            con.close()
            
    print("--- Klaar ---")

# Dit zorgt ervoor dat de functie alleen wordt uitgevoerd als je dit script direct runt
if __name__ == '__main__':
    toon_alle_data()