import os

from flask import Flask
from flask import render_template
from flask import request

from lib.tweet_locator import determinate_tweet_location

app = Flask(__name__)


@app.route('/')
def home():
    """Return the home page"""
    return render_template('home.html')


@app.route('/map', methods=['GET', 'POST'])
def map():
    """Get the map for the given tweet"""
    if request.form['tweetId']:
        tweet_id = request.form['tweetId']
        poly = determinate_tweet_location(tweet_id)
        return render_template('map.html', poly=poly, mps_key=os.environ['GOOGLE_MAPS_KEY'])

if __name__ == "__main__":
    app.run()
