import sqlite3

# Define the database file path
DB_FILE = "song_concentration.db"

def fetch_all_records():
    # Connect to the SQLite database
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Execute the SQL query to fetch all records from the song_concentration table
        cursor.execute("SELECT ID, song_id, AVG(average_concentration) FROM song_concentration GROUP BY song_id")

        # Fetch all the results
        records = cursor.fetchall()

        # Check if there are any records
        if records:
            print("ID | Song ID | Average Concentration |")
            print("-" * 60)
            for record in records:
                id, song_id, avg_concentration = record
                print(f"{id} | {song_id} | {avg_concentration:.2f} |")
            return records
        else:
            print("No records found in the song_concentration table.")

    except sqlite3.Error as e:
        print(f"Error querying the database: {e}")

    finally:
        # Close the database connection
        if conn:
            conn.close()
        
if __name__ == "__main__":
    fetch_all_records()