from flask import Flask, redirect, request, session, url_for, render_template
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import json
import secret
import threading
import time
import sqlite3
import websocket
from test_view_db import fetch_all_records

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure Spotipy OAuth with necessary scopes
sp_oauth = SpotifyOAuth(
    client_id=secret.client_id,
    client_secret=secret.client_secret,
    redirect_uri=secret.redirect_uri,
    scope="playlist-read-private user-read-email"
)

# Global variables to manage concentration data collection
current_song_id = None
concentration_data = []
data_collection_thread = None
data_collection_stop_event = threading.Event()

def collect_concentration_data(stop_event):
    ws = websocket.WebSocket()
    try:
        ws.connect("ws://localhost:8765")
        while not stop_event.is_set():
            result = ws.recv()
            data = json.loads(result)
            concentration = data.get('concentration')
            print(concentration)
            if concentration is not None:
                concentration_data.append(concentration)
                
            time.sleep(0.1)  # Adjust based on your data frequency
    except Exception as e:
        print(f"Error in WebSocket connection: {e}")
    finally:
        ws.close()

# Step 1: Redirect to Spotify login
@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

# Step 2: Handle callback and obtain access token
@app.route('/callback')
def callback():
    code = request.args.get('code')
    try:
        token_info = sp_oauth.get_access_token(code)
    except Exception as e:
        print(f"Error fetching access token: {e}")
        return "Authentication failed", 400

    if token_info:
        session['access_token'] = token_info['access_token']
        return redirect(url_for('embed'))
    else:
        return "Authentication failed", 400

@app.route('/embed')
def embed():
    if 'access_token' in session:
        # Initialize Spotify client with the access token
        sp = Spotify(auth=session['access_token'])
        
        # Fetch the user's playlists and find the playlist named "NPC"
        playlists = sp.current_user_playlists(limit=5)
        npc_playlist = None
        for playlist in playlists['items']:
            if playlist['name'].lower() == "npc":
                npc_playlist = playlist
                break

        # If the playlist is found, fetch the tracks in the playlist
        if npc_playlist:
            playlist_id = npc_playlist['id']
            tracks = sp.playlist_tracks(playlist_id, limit=5)
            track_info = [
                {
                    "name": track['track']['name'],
                    "artist": track['track']['artists'][0]['name'],
                    "songid": track['track']['id'],
                    "embed_url": f"https://open.spotify.com/embed/track/{track['track']['id']}"
                }
                for track in tracks['items']
            ]
            return render_template("playlist.html", playlist_name="NPC", tracks=track_info)
        else:
            return "Playlist 'NPC' not found", 404
    else:
        return redirect(url_for('login'))

@app.route('/log_song', methods=['POST'])
def log_song():
    global current_song_id, concentration_data, data_collection_thread, data_collection_stop_event

    song_id = request.json.get('song_id')
    isPaused = request.json.get('isPlayed')
    print(f"song_id: {song_id}, isPlayed: {isPaused}")

    if song_id:
        # Initialize Spotipy client with access token
        sp = Spotify(auth=session.get('access_token'))

        try:
            if isPaused is None:
                # Song is playing
                if current_song_id != song_id:
                    # New song started, reset data
                    current_song_id = song_id
                    concentration_data = []
                    data_collection_stop_event.clear()
                    data_collection_thread = threading.Thread(target=collect_concentration_data, args=(data_collection_stop_event,))
                    data_collection_thread.start()
                    print(f"Started collecting concentration data for song ID {song_id}")
                else:
                    # Same song continues playing
                    pass
                return "Started collecting concentration data", 200

            elif isPaused is True:
                print("paused")
                # Song is paused
                if current_song_id == song_id:

                    print(f"Paused collecting concentration data for song ID {current_song_id}")
                    # Stop data collection
                    data_collection_stop_event.set()
                    data_collection_thread.join()

                    print(concentration_data)

                    if concentration_data:
                        if len(concentration_data) !=0 :
                            average_concentration = sum(concentration_data) / len(concentration_data)
                        else:
                            average_concentration = 0
                        print(average_concentration)
                    
                        # Store in database
                        conn = sqlite3.connect('song_concentration.db')
                        c = conn.cursor()
                        c.execute('''CREATE TABLE IF NOT EXISTS song_concentration (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        song_id TEXT NOT NULL,
                                        average_concentration REAL NOT NULL
                                    )''')
                        c.execute('INSERT INTO song_concentration (song_id, average_concentration) VALUES (?, ?)',
                                  (song_id, average_concentration))
                        conn.commit()
                        conn.close()
                        print(f"Stored average concentration {average_concentration} for song ID {song_id}")
                    else:
                        print("No concentration data collected")
                    # Reset variables
                    current_song_id = None
                    concentration_data = []
                    data_collection_thread = None
                    return "Stopped collecting concentration data", 200
                else:
                    print(current_song_id)
                    print(song_id)
                    # Song paused but IDs don't match
                    print("Paused song does not match current song ID")
                    return "Paused song does not match current song ID", 400

            else:
                # isPaused is something else
                print("Invalid isPaused value")
                return "Invalid isPaused value", 400

        except Exception as e:
            print(f"Error in log_song: {e}")
            return "Failed to process song log", 400
    else:
        return "No song ID provided", 400

@app.route('/recommendations', methods=['GET'])
def get_recommendations():
    if 'access_token' not in session:
        return redirect(url_for('login'))

    sp = Spotify(auth=session['access_token'])
    try:
        # Fetch all records
        records = fetch_all_records()

        # Filter records with avg_concentration > 0.4
        filtered_songs = [record[1] for record in records if float(record[2]) > 0.4]

        for song_id in filtered_songs:
            # Fetch recommendations for each song
            response = sp.recommendations(seed_tracks=[song_id], limit=5)
            for i in range(50):
                recommendations = response['tracks'][i]['id']
                print(recommendations)

            for track in response['tracks']:
                recommendations.append({
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'id': track['id'],
                    'preview_url': track['preview_url'],
                })

        # Render or return recommendations
        return render_template('recommendations.html', recommendations=recommendations)

    except Exception as e:
        print(f"Error in get_recommendations: {e}")
        return "Failed to fetch recommendations", 500

@app.route('/')
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(port=3000, debug=True)
