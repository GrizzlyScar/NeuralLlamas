from flask import Flask, redirect, request, session, url_for, render_template
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import json
import secret

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

# Step 1: Redirect to Spotify login
@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

# Step 2: Handle callback and obtain access token
@app.route('/callback')
def callback():
    code = request.args.get('code')
    # token_info = sp_oauth.get_access_token(code)
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
        playlists = sp.current_user_playlists(limit=50)
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
    song_id = request.json.get('song_id')
    if song_id:
        # Initialize Spotipy client with access token
        sp = Spotify(auth=session.get('access_token'))

        try:
            # Get audio analysis for the song
            analysis = sp.audio_analysis(song_id)
            sections = analysis.get('sections', [])
            track = analysis.get('track', [])
            # Define the output JSON file path
            output_dir = "song_analysis"
            os.makedirs(output_dir, exist_ok=True)  # Create directory if it doesn't exist
            audio_analysis_output_file = os.path.join(output_dir, f"{song_id}_analysis.json")

            # Prepare the JSON data
            data_to_save = {
                "song_id": song_id,
                "sections": sections,
                "track": track
            }

            # Save data to JSON file
            with open(audio_analysis_output_file, 'w') as file:
                json.dump(data_to_save, file, indent=4)


            features = sp.audio_features(song_id)
            output_dir = "song_features"
            os.makedirs(output_dir, exist_ok=True)  # Create directory if it doesn't exist
            output_file = os.path.join(output_dir, f"{song_id}_features.json")

            # Prepare the JSON data
            data_to_save = {
                "song_id": song_id,
                "features": features
            }

            # Save data to JSON file
            with open(output_file, 'w') as file:
                json.dump(data_to_save, file, indent=4)

            print(f"Audio analysis for song ID {song_id} saved to {audio_analysis_output_file}")
            print(f"Audio features for song ID {song_id} saved to {output_file}")
            return f"Audio analysis saved to {audio_analysis_output_file}\nAudio analysis saved to {output_file}", 200

        except Exception as e:
            print(f"Error fetching audio analysis: {e}")
            return "Failed to fetch audio analysis", 400
    else:
        return "No song ID provided", 400

@app.route('/')
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(port=3000, debug=True)
