from flask import Flask, render_template, request, redirect, url_for, session, g, flash
import sqlite3
import requests
from datetime import datetime, timedelta
import os
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.permanent_session_lifetime = timedelta(days=7)
DATABASE = 'users.db'

TMDB_API_KEY = '639e38c46d00490d497c4e098bbf21d2'
TMDB_BASE_URL = 'https://api.themoviedb.org/3'
GENRE_MAP = {
    "action": 28,
    "adventure": 12,
    "animation": 16,
    "comedy": 35,
    "crime": 80,
    "documentary": 99,
    "drama": 18,
    "family": 10751,
    "fantasy": 14,
    "history": 36,
    "horror": 27,
    "music": 10402,
    "mystery": 9648,
    "romance": 10749,
    "science fiction": 878,
    "tv movie": 10770,
    "thriller": 53,
    "war": 10752,
    "western": 37
}

# Create database if not exists
def init_db():
    if not os.path.exists('users.db'):
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                mobile TEXT,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

init_db()

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db:
        db.close()


@app.route('/')
def welcome():
    return render_template('welcome.html')


@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session.permanent = True
            session['username'] = username
            flash("Login Successful!", "info")
            return redirect(url_for('home'))
        else:
            flash("Invalid Credentials", "error")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        mobile = request.form['mobile']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (fullname, username, email, mobile, password) VALUES (?, ?, ?, ?, ?)",
                      (fullname, username, email, mobile, password))
            conn.commit()
            flash("Account created successfully!", "info")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists!", "error")
            return redirect(url_for('signup'))
        finally:
            conn.close()

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))

def get_account_details():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT fullname, username, email, mobile FROM users WHERE username=?", (session.get('username'),))
    result = cursor.fetchone()
    conn.close()
    return result

@app.route('/account')
def account():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT fullname, username, email, mobile FROM users WHERE username=?", (session['username'],))
    user = cursor.fetchone()
    conn.close()

    if user:
        return render_template('account.html',
                               name=user[0],
                               username=user[1],
                               email=user[2],
                               mobile=user[3])
    else:
        flash("User not found!", "error")
        return redirect(url_for('home'))

@app.route('/update_account', methods=['POST'])
def update_account():
    if 'username' not in session:
        return redirect('/login')

    # Get updated values from form
    new_name = request.form['name']
    new_username = request.form['username']
    new_email = request.form['email']
    new_mobile = request.form['mobile']
    current_username = session['username']

    # Update database
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET fullname=?, username=?, email=?, mobile=? WHERE username=?
    ''', (new_name, new_username, new_email, new_mobile, current_username))
    conn.commit()
    conn.close()

    session['username'] = new_username  
    return redirect('/account')


def fetch_movies(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json().get('results', [])
    except requests.RequestException as e:
        print(f"TMDB API Request Failed: {e}")
        return []

def fetch_movie_details(movie_id):
    """Fetch detailed movie info including runtime."""
    try:
        response = requests.get(
            f"{TMDB_BASE_URL}/movie/{movie_id}",
            params={'api_key': TMDB_API_KEY, 'language': 'en-US'},
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"TMDB Details API Failed: {e}")
        return {}

@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    movie = {}
    cast_list = []
    cast_data_full = []  # <-- NEW: full cast info with profile_path

    try:
        # Movie details
        details_url = f"{TMDB_BASE_URL}/movie/{movie_id}"
        details_params = {'api_key': TMDB_API_KEY}
        movie = requests.get(details_url, params=details_params).json()

        # Cast details
        cast_url = f"{TMDB_BASE_URL}/movie/{movie_id}/credits"
        cast_params = {'api_key': TMDB_API_KEY}
        credits_response = requests.get(cast_url, params=cast_params).json()
        cast = credits_response.get('cast', [])[:10]  # top 10 only

        # Keep your original list of names
        cast_list = [c['name'] for c in cast]
        # Add full cast info for images
        cast_data_full = cast  

    except requests.RequestException as e:
        print(f"Error fetching movie details: {e}")

    return render_template(
        'movie_details.html',
        movie=movie,
        cast_list=cast_list,        # unchanged (name list)
        cast_data=cast_data_full    # new variable for images
    )


@app.route('/search', methods=['GET'])
def search_page():
    query = request.args.get("q", "").lower().strip()
    movies = []

    if query:
        # --- Detect genre ---
        genre_id = None
        for name, gid in GENRE_MAP.items():
            if name in query:
                genre_id = gid
                break

        # --- Detect language ---
        lang = None
        if "tamil" in query:
            lang = "ta"
        elif "english" in query:
            lang = "en"
        elif "hindi" in query:
            lang = "hi"

        if genre_id or lang:
            # Use Discover API for genre/language searches
            discover_url = f"{TMDB_BASE_URL}/discover/movie"
            params = {
                "api_key": TMDB_API_KEY,
                "with_genres": genre_id if genre_id else "",
                "with_original_language": lang if lang else "",
                "sort_by": "popularity.desc"
            }
            response = requests.get(discover_url, params=params).json()
            movies = response.get("results", [])
        else:
            # Default search by keyword/title/actor
            search_url = f"{TMDB_BASE_URL}/search/movie"
            params = {"api_key": TMDB_API_KEY, "query": query}
            response = requests.get(search_url, params=params).json()
            movies = response.get("results", [])

    return render_template("search.html", query=query, movies=movies)


@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))

    today = datetime.today().date()
    thirty_days_ago = today - timedelta(days=30)
    tomorrow = today + timedelta(days=1)

    trending_movies = fetch_movies(
        f"{TMDB_BASE_URL}/trending/movie/week",
        params={'api_key': TMDB_API_KEY}
    )

    recent_english = fetch_movies(
        f"{TMDB_BASE_URL}/discover/movie",
        params={
            'api_key': TMDB_API_KEY,
            'language': 'en-US',
            'region': 'IN',
            'sort_by': 'release_date.desc',
            'release_date.gte': thirty_days_ago,
            'release_date.lte': today,
            'with_original_language': 'en'
        }
    )

    recent_tamil = fetch_movies(
        f"{TMDB_BASE_URL}/discover/movie",
        params={
            'api_key': TMDB_API_KEY,
            'language': 'ta-IN',
            'region': 'IN',
            'sort_by': 'release_date.desc',
            'release_date.gte': thirty_days_ago,
            'release_date.lte': today,
            'with_original_language': 'ta'
        }
    )

    upcoming_english = fetch_movies(
        f"{TMDB_BASE_URL}/discover/movie",
        params={
            'api_key': TMDB_API_KEY,
            'language': 'en-US',
            'region': 'IN',
            'sort_by': 'release_date.asc',
            'release_date.gte': tomorrow,
            'with_original_language': 'en'
        }
    )

    upcoming_tamil = fetch_movies(
        f"{TMDB_BASE_URL}/discover/movie",
        params={
            'api_key': TMDB_API_KEY,
            'language': 'ta-IN',
            'region': 'IN',
            'sort_by': 'release_date.asc',
            'release_date.gte': tomorrow,
            'with_original_language': 'ta'
        }
    )

    top_rated_hindi = fetch_movies(
        f"{TMDB_BASE_URL}/discover/movie",
        params={
            'api_key': TMDB_API_KEY,
            'with_original_language': 'hi',
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 100
        }
    )

    top_rated_tamil = fetch_movies(
        f"{TMDB_BASE_URL}/discover/movie",
        params={
            'api_key': TMDB_API_KEY,
            'with_original_language': 'ta',
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 100
        }
    )

    # Merge Hindi + Tamil
    top_rated_movies = top_rated_hindi[:5] + top_rated_tamil[:5]

    # Add runtime + overview
    enriched_top_rated = []
    for movie in top_rated_movies:
        details = fetch_movie_details(movie['id'])
        enriched_top_rated.append({
            'title': movie.get('title'),
            'backdrop_path': movie.get('backdrop_path'),
            'vote_average': movie.get('vote_average'),
            'overview': movie.get('overview'),
            'runtime': details.get('runtime', None),
            'release_date': movie.get('release_date')
        })

    recent_releases = recent_english + recent_tamil
    upcoming_movies = upcoming_english + upcoming_tamil

    return render_template(
        'home.html',
        username=session['username'],
        trending=trending_movies,
        recent=recent_releases,
        upcoming=upcoming_movies,
        top_rated=enriched_top_rated
    )

if __name__ == '__main__':
    app.run(debug=True)


