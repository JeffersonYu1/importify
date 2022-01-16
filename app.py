import base64
import datetime
import html
import json
import os
import re
import requests
import spotipy
import time
import urllib.parse

from flask import Flask, flash, redirect, render_template, Response, request, session, stream_with_context
from flask_session import Session
from functools import wraps
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from tempfile import mkdtemp
from time import sleep

# Spotify URLS
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/en/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com"
API_VERSION = "v1"
SPOTIFY_API_URL = "{}/{}".format(SPOTIFY_API_BASE_URL, API_VERSION)

# Server-side Parameters
REDIRECT_URI = "{}/callback/q".format(os.environ.get("SPOTIPY_REDIRECT_URL"))
SCOPE = "user-library-read user-library-modify playlist-modify-private playlist-modify-public ugc-image-upload"
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

if not os.environ.get("SPOTIPY_REDIRECT_URL"):
    raise RuntimeError("SPOTIPY_REDIRECT_URL not set")

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
        elif datetime.datetime.now() >= session.get("response_data").get("expire_datetime"):
            session["status"] = "expired"
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

    # print(response_data)
    # access_token = response_data["access_token"]
    # refresh_token = response_data["refresh_token"]
    # token_type = response_data["token_type"]
    # expires_in = response_data["expires_in"]

    response_data["expire_datetime"] = datetime.datetime.now() + datetime.timedelta(
        seconds=max(response_data["expires_in"] - 100, 0))
    session["status"] = "active"
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
        def generate():
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
                return render_template("link.html", error=str_error)
            
            # Original playlist data (may be written if user has specifications)
            playlist_name = html.unescape(results['name'])
            playlist_desc = html.unescape(results['description'])
            playlist_visibility = results['public']
            playlist_cover_url = results['images'][0]['url']     
            
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
            try:
                sp.playlist_upload_cover_image(playlist_uri, base64.b64encode(requests.get(playlist_cover_url).content))
            except Exception as str_error:
                print("playlist cover not uploaded.")
                print(str_error)
                pass

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
            
            num_bins = 100

            # Tracks Data (uri, name, artists)
            tracks_data = []
            added_songs = []
            not_added = []    

            for track in tracks:
                if 'track' in track and track['track'] and 'uri' in track['track'] and track['track']['uri']:
                    tracks_data.append(
                        {
                            'uri': track['track']['uri'],
                            'name': track['track']['name'],
                            'artist': track['track']['artists'][0]['name']
                        }
                    )

            # If there is at least one element in tracks_data
            if not len(tracks_data) == 0:
                # Keep a list of added track_uris
                temp_track_uris = []

                while not len(tracks_data) == 0:
                    this_uri = tracks_data[0]['uri']

                    if "spotify:local" in this_uri:
                        yield("0A3B0" + str(this_uri))
                        # not_added.append(this_uri)
                    
                    else:
                        temp_track_uris.append(this_uri)
                        # added_songs.append(
                        #     {
                        #         'name': tracks_data[0]['name'],
                        #         'artist': tracks_data[0]['artist']
                        #     }
                        # )
                        yield("0A3B1" + tracks_data[0]['name'] +
                                "0B4C" + tracks_data[0]['artist'])

                    tracks_data.pop(0)

                    if len(temp_track_uris) == num_bins or len(tracks_data) == 0: 
                        for try_count in range(0, 6):  # try 6 times
                            try:
                                sp.user_playlist_add_tracks(user_id, playlist_uri, temp_track_uris)
                                break
                            except Exception as str_error:
                                print(str_error)
                                if try_count == 5:
                                    return render_template("link.html", error=str_error)
                                    raise RuntimeError("Error while adding tracks.")
                                sleep(1)
                                pass
                        
                        temp_track_uris.clear()

        songs_string = generate()
        return Response(stream_with_context(stream_template("result2.html", origin="Import By Link", songs_string=songs_string)))

    else:
        return render_template("link.html")


@app.route("/text", methods=["GET", "POST"])
@login_required
def import_by_text():
    if request.method == "POST":
        def generate():
            # Make Spotipy object with access token
            sp = spotipy.Spotify(auth=session["response_data"]["access_token"])

            # Get form data for playlist
            playlist_name = request.form.get("playlist_name")
            if not playlist_name:
                playlist_name = "importify playlist"
            playlist_name.strip()

            playlist_desc = request.form.get("playlist_desc")
            if not playlist_desc:
                playlist_desc = "playlist created with importify"
            playlist_desc.strip()

            playlist_paste = request.form.get("playlist_paste")
            if not playlist_paste:
                playlist_paste = ""
            playlist_paste.strip()

            playlist_visibility = request.form.get("playlist_visibility")
            if playlist_visibility not in ["True", "False", True, False]:
                playlist_visibility = "False"
            bool(playlist_visibility.strip())

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

            num_bins = 100

            # If there is at least one line in the paste
            if not len(paste_list) == 0:
                # Keep a list of added track_uris
                track_uris = []
                counter = 0

                while not len(paste_list) == 0:
                    line = line_parse(paste_list[0])
                    # print("line:", line)

                    if line.replace(' ', '') == '':
                        paste_list.pop(0)
                        continue

                    # Search for the song
                    for try_count in range(0, 6):  # try 6 times
                        try:
                            results = sp.search(line, type="track", limit="1")
                            break
                        except Exception as str_error:
                            print(str_error)
                            if try_count == 5:
                                print("Could not search for song. Continuing...")
                            sleep(2)
                            pass

                    # If a match is found,
                    if len(results['tracks']['items']) > 0:
                        # then add it to the list of trackIDs (if not already there)
                        if results['tracks']['items'][0]['uri'] not in track_uris:
                            yield("0A3B1" + results['tracks']['items'][0]['name'] +
                                "0B4C" + results['tracks']['items'][0]['artists'][0]['name'])
                            # added_songs.append(
                            #     {
                            #         'name': results['tracks']['items'][0]['name'],
                            #         'artist': results['tracks']['items'][0]['artists'][0]['name']
                            #     }
                            # )
                            # print(results['tracks']['items'][0]['name'])
                            track_uris.append(results['tracks']['items'][0]['uri'])
                    
                    else:
                        yield("0A3B0" + str(line))
                        # not_added.append(line)
                    
                    if len(track_uris) == num_bins or len(paste_list) == 1:
                        for try_count in range(0, 6):  # try 6 times
                            try:
                                sp.user_playlist_add_tracks(user_id, playlist_uri, track_uris)
                                track_uris.clear()
                                break
                            except Exception as str_error:
                                print(str_error)
                                if try_count == 5:
                                    return render_template("text.html", error=str_error)
                                sleep(2)
                                pass

                    paste_list.pop(0)

        songs_string = generate()
        return Response(stream_with_context(stream_template("result2.html", origin="Import By Text", songs_string=songs_string)))

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


def line_parse(line):
    # dictionary of string:replacement
    replace = {
        ', ': ',',
        ',': ' ',
        ' - ': '-',
        ' – ': '-',
        ' — ': '-',
        '-': ' ',
        '.ncm': '',
        '.mp3': '',
        '.m4a': '',
        '.aac': '',
        '.flac': '',
        '.mp4': '',
        '.wav': '',
        '.wma': ''
    }

    for original, replacement in replace.items():
        line = line.replace(original, replacement)
    
    line = re.sub('^\s*\d+\.', '', line)
    
    return line


def stream_template(template_name, **context):
    app.update_template_context(context)
    t = app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    rv.disable_buffering()
    return rv


if __name__ == "__main__":
    app.run()