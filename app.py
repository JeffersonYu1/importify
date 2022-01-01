import os
import spotipy
import json
import requests
import urllib.parse

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from functools import wraps
from spotipy.oauth2 import SpotifyOAuth
from spotipy.oauth2 import SpotifyClientCredentials
from tempfile import mkdtemp
from time import sleep

# Spotify URLS
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/en/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com"
API_VERSION = "v1"
SPOTIFY_API_URL = "{}/{}".format(SPOTIFY_API_BASE_URL, API_VERSION)

# Server-side Parameters
CLIENT_SIDE_URL = "http://127.0.0.1"
PORT = 5000
REDIRECT_URI = "{}:{}/callback/q".format(CLIENT_SIDE_URL, PORT)
SCOPE = "user-library-read user-library-modify playlist-modify-private playlist-modify-public"
SHOW_DIALOG_bool = True

auth_query_parameters = {
    "client_id": os.environ.get("SPOTIPY_CLIENT_ID"),
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE,
    "show_dialog": SHOW_DIALOG_bool
}

# Start Flask
app = Flask(__name__)

# Rerender template if change detected
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Ensure client_id and client_secret are set
if not os.environ.get("SPOTIPY_CLIENT_ID"):
    raise RuntimeError("SPOTIPY_CLIENT_ID not set")

if not os.environ.get("SPOTIPY_CLIENT_SECRET"):
    raise RuntimeError("SPOTIPY_CLIENT_SECRET not set")

if not os.environ.get("SPOTIPY_REDIRECT_URI"):
    raise RuntimeError("SPOTIPY_REDIRECT_URI not set")

# Require login on certain pages
def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("response_data") is None:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function


@app.route("/callback/q")
def callback():
    # Auth Step 2: Requests refresh and access tokens
    auth_token = request.args['code']
    code_payload = {
        "grant_type": "authorization_code",
        "code": str(auth_token),
        "redirect_uri": REDIRECT_URI,
        'client_id': os.environ.get("SPOTIPY_CLIENT_ID"),
        'client_secret': os.environ.get("SPOTIPY_CLIENT_SECRET"),
    }
    post_request = requests.post(SPOTIFY_TOKEN_URL, data=code_payload)

    # Auth Step 3: Tokens are Returned to Application
    response_data = json.loads(post_request.text)
    # access_token = response_data["access_token"]
    # refresh_token = response_data["refresh_token"]
    # token_type = response_data["token_type"]
    # expires_in = response_data["expires_in"]

    session["response_data"] = response_data
    
    return redirect("/")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/info")
def info():
    return render_template("info.html")


@app.route("/link", methods=["GET", "POST"])
@login_required
def import_by_link():
    if request.method == "POST":
        # Make Spotipy object with access token
        sp = spotipy.Spotify(auth=session["response_data"]["access_token"])

        # Get desired playlist link from form data
        playlist_link = request.form.get("playlist_link")
        if not playlist_link:
            return render_template("link.html", error="No playlist link specified.")
        playlist_link.strip()

        # Convert URL into URI
        playlist_original_URI = playlist_link
        for original, replacement in {"https://":"", "http://":"", "open.": "", ".com": "", "/":":"}.items():
            playlist_original_URI = playlist_original_URI.replace(original, replacement)
        playlist_original_URI = playlist_original_URI.split("?")[0]
        # print(playlist_URI)

        # Get attributes of playlist
        try:
            results = sp.playlist(playlist_original_URI)

        except Exception as str_error:
            return render_template("link.html", error="Invalid playlist URL.")
        
        # Original playlist data (may be written if user has specifications)
        playlist_name = results['name']
        playlist_desc = results['description']
        playlist_visibility = results['public']        
        
        # Get form data for playlist        
        if request.form.get("playlist_name"):
            playlist_name = request.form.get("playlist_name")
        playlist_name.strip()

        if request.form.get("playlist_desc"):
            playlist_desc = request.form.get("playlist_desc")
        playlist_desc.strip()

        if request.form.get("playlist_visibility") in ["True", "False"]:
            playlist_visibility = bool(request.form.get("playlist_visibility").strip())

        # Generate playlist args based on form responses
        playlist_args = {
            "name": playlist_name,
            "public": playlist_visibility,
            "collaborative": False,
            "description": playlist_desc
        }

        # Get user_id based on Spotipy object
        user_id = sp.me()['id']
        playlist_response = sp.user_playlist_create(user_id, playlist_args["name"], public=playlist_args["public"], collaborative=playlist_args["collaborative"], description=playlist_args["description"])
        
        # Ensure new playlist was created
        if not playlist_response:
            raise RuntimeError("New playlist could not be created")

        # Get playlist_uri (similar to id) of new playlist
        playlist_uri = playlist_response['uri']

        tracks = results['tracks']['items']
        # print(results)
        
        if results['tracks']['next']:
            results = sp.next(results['tracks'])
            # print(results)
            tracks.extend(results['items'])

            while results['next']:
                results = sp.next(results)
                # print(results)
                tracks.extend(results['items'])

        # try:
        #     while results['next']:
        #         results = sp.next(results)
        #         tracks.extend(results['tracks']['items'])

        # except Exception as str_error:
        #     return render_template("link.html", error=str_error)
        

        # tracks are stored here results['tracks']['items'][0 (index)]['track']['uri']
        track_uris = []
        for track in tracks:
            track_uris.append(track['track']['uri'])
        
        added_songs = []
        not_added = []

        # If there is at least one URI in track_uris
        if not len(track_uris) == 0:
            # Keep a list of added track_uris
            temp_track_uris = []
            counter = 0

            while not len(track_uris) == 0:
                for try_count in range(0, 6):  # try 6 times
                    try:
                        this_uri = track_uris[0]

                        # Search for the song
                        results = sp.track(this_uri)
                        # print(results)

                        # If a match is found,
                        if results and len(results) > 0:
                            # then add it to the list of trackIDs (if not already there)
                            if this_uri not in temp_track_uris:
                                added_songs.append(
                                    {
                                        'name': results['name'],
                                        'artist': results['artists'][0]['name']
                                    }
                                )
                                print(results['name'])
                                temp_track_uris.append(this_uri)
                        
                        else:
                            not_added.append(this_uri)
                        
                        if len(temp_track_uris) >= 5 or len(track_uris) == 1:
                            print()
                            print('adding last {} song(s)...'.format(len(temp_track_uris)))
                            sp.user_playlist_add_tracks(user_id, playlist_uri, temp_track_uris)
                            print('last {} song(s) successfully added'.format(len(temp_track_uris)))
                            temp_track_uris.clear()
                            print()

                        track_uris.pop(0)
                        break
                    except Exception as str_error:
                        print(str_error)
                        sleep(2)
                        pass

        return render_template("result.html", origin="Import By Link", added_songs=added_songs, not_added=not_added)

    else:
        return render_template("link.html")


@app.route("/text", methods=["GET", "POST"])
@login_required
def import_by_text():
    if request.method == "POST":
        # Make Spotipy object with access token
        sp = spotipy.Spotify(auth=session["response_data"]["access_token"])

        # Get form data for playlist
        playlist_name = request.form.get("playlist_name")
        if not playlist_name:
            playlist_name = "importspotify playlist"
        playlist_name.strip()

        playlist_desc = request.form.get("playlist_desc")
        if not playlist_desc:
            playlist_desc = "playlist created with importspotify"
        playlist_desc.strip()

        playlist_paste = request.form.get("playlist_paste")
        if not playlist_paste:
            playlist_paste = ""
        playlist_paste.strip()

        playlist_visibility = request.form.get("playlist_visibility")
        if playlist_visibility not in ["True", "False", True, False]:
            playlist_visibility = "False"
        bool(playlist_visibility.strip())

        print(playlist_paste)

        # Generate playlist args based on form responses
        playlist_args = {
            "name": playlist_name,
            "public": playlist_visibility,
            "collaborative": False,
            "description": playlist_desc
        }

        # Get user_id based on Spotipy object
        user_id = sp.me()['id']
        playlist_response = sp.user_playlist_create(user_id, playlist_args["name"], public=playlist_args["public"], collaborative=playlist_args["collaborative"], description=playlist_args["description"])
        
        # Ensure new playlist was created
        if not playlist_response:
            raise RuntimeError("New playlist could not be created")

        # Get playlist_uri (similar to id) of playlist
        playlist_uri = playlist_response['uri']
        
        # Convert pasted song data into array
        paste_list = playlist_paste.splitlines()
        added_songs = []
        not_added = []

        # If there is at least one line in the paste
        if not len(paste_list) == 0:
            # Keep a list of added track_uris
            track_uris = []
            counter = 0

            while not len(paste_list) == 0:
                for try_count in range(0, 6):  # try 6 times
                    try:
                        line = paste_list[0]

                        # Search for the song
                        results = sp.search(line, type="track", limit="1")

                        # If a match is found,
                        if len(results['tracks']['items']) > 0:
                            # then add it to the list of trackIDs (if not already there)
                            if results['tracks']['items'][0]['uri'] not in track_uris:
                                added_songs.append(
                                    {
                                        'name': results['tracks']['items'][0]['name'],
                                        'artist': results['tracks']['items'][0]['artists'][0]['name']
                                    }
                                )
                                print(results['tracks']['items'][0]['name'])
                                track_uris.append(results['tracks']['items'][0]['uri'])
                        
                        else:
                            not_added.append(line)
                        
                        if len(track_uris) >= 5 or len(paste_list) == 1:
                            print()
                            print('adding last {} song(s)...'.format(len(track_uris)))
                            sp.user_playlist_add_tracks(user_id, playlist_uri, track_uris)
                            print('last {} song(s) successfully added'.format(len(track_uris)))
                            track_uris.clear()
                            print()

                        paste_list.pop(0)
                        break
                    except Exception as str_error:
                        sleep(2)
                        pass

        return render_template("result.html", origin="Import By Text", added_songs=added_songs, not_added=not_added)

    else:
        return render_template("text.html")


@app.route("/login")
def login():
    # Auth Step 1: Authorization
    auth_url = "{}?{}".format(SPOTIFY_AUTH_URL, urllib.parse.urlencode(auth_query_parameters))
    return redirect(auth_url)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run()