from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
import requests
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'users.db'

TMDB_API_KEY = '639e38c46d00490d497c4e098bbf21d2'
TMDB_BASE_URL = 'https://api.themoviedb.org/3'


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
    error = None
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", 
                       (request.form['username'], request.form['password']))
        user = cursor.fetchone()
        if user:
            session['username'] = request.form['username']
            return redirect(url_for('home'))
        else:
            error = 'Invalid username or password.'
    return render_template('login.html', error=error)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                           (request.form['username'], request.form['password']))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            error = 'Username already exists.'
    return render_template('signup.html', error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/account')
def account():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('account.html', username=session['username'])


def fetch_movies(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json().get('results', [])
    except requests.RequestException as e:
        print(f"TMDB API Request Failed: {e}")
        return []

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


    recent_releases = recent_english + recent_tamil
    upcoming_movies = upcoming_english + upcoming_tamil

    return render_template(
        'home.html',
        username=session['username'],
        trending=trending_movies,
        recent=recent_releases,
        upcoming=upcoming_movies
    )


if __name__ == '__main__':
    app.run(debug=True)
