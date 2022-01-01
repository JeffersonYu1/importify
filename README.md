# importspotify
Web app to ease creation of Spotify playlists by importing from other streaming applications or users' playlists. Written by Jefferson Yu.

## About the Project
### Motivation
This project started off as a [CS50x](https://cs50.harvard.edu/x/) final project. It is difficult to import playlists and songs from external applications into Spotify, as well as to copy other users' playlists into a personal library to make modifications. As a result, this project was built to alleviate part of the difficulty.

### Features
Using importspotify, users can log in to their Spotify accounts to import playlists by pasting track names into a text box, or by providing a Spotify playlist link to copy. 

For instance,
![Screenshot 2021-12-31 at 20-32-31 Import By Text importspotify](https://user-images.githubusercontent.com/43518772/147842842-0a87ce73-1279-4637-8434-d5c91e2a2720.png)

and
![Screenshot 2021-12-31 at 20-32-39 Import By Link importspotify](https://user-images.githubusercontent.com/43518772/147842844-6ed440d6-d4bb-405f-8659-256cb37b6799.png)

### Steps
* This project was built using the VSCode IDE. At first, I considered using the CS50 IDE because of my familiarity with it, but I wanted to challenge myself and explore the an industry-standard environment.
* I first set up VSCode by downloading and installing extensions for the languages I would be programming in, such as Python, HTML, and CSS. I then installed Python and set up a virtual environment for the project.
* From there, I installed dependencies from pip such as Flask. I tested Flask by creating a sample index.html page and having a basic redirect if a GET request was made. 

### Files
* The "importspotify" folder is dedicated for the virtual environment setup.
* The "static" folder holds static files for webpage display, including the JS and CSS files that are linked. "style.css" was implemented by me, while the other files. such as "bootstrap.min.css" or "jquery-3.6.0.min.js", are downloaded from the internet.
* The "templates" folder holds template files for webpages. All of the other .html files are extended from the layout.html template, as there are many shared elements, such as the Navbar and Footer, that are common across all pages of the site.
* "app.py" holds the Python code for responses to the GET and POST requests from the user. These methods determine the functionality of the site when a link is clicked or a form is submitted.
* "requirements.txt" lists the dependencies needed for "app.py" so that others can easily install at a later time. 

## Contact
* Jefferson Yu - [fu.yao.yu at hotmail dot com](mailto:fu.yao.yu@hotmail.com)
* Project link: https://github.com/JeffersonYu1/importspotify

## Acknowledgments
* [CS50x](https://cs50.harvard.edu/x/)
* [Spotipy](https://spotipy.readthedocs.io/en/2.19.0/) (Python library for Spotify Web API)
* [Spotify Authorization Flow Guide](https://github.com/drshrey/spotify-flask-auth-example)
