import os

from flask import Flask
from flask import jsonify
from flask import render_template
from flask import request

from lib.tweet_locator import determinate_tweet_location

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def home():
    """Return the home page or map if tweet_id is send"""
    if request.form.get('tweetId'):
        tweet_ids = request.form['tweetId'].split(',')
        polys = []
        for tweet_id in tweet_ids:
            polys.append(determinate_tweet_location(tweet_id))
        return render_template('map.html', polys=polys, maps_key=os.environ['GOOGLE_MAPS_KEY'])
    return render_template('home.html')


@app.route('/api', methods=['GET'])
def api():
    """API"""
    if request.args.get('tweetIds'):
        tweet_ids = request.args.get('tweetIds').split(',')
        polys = []
        for tweet_id in tweet_ids:
            polys.append(determinate_tweet_location(tweet_id))
        return jsonify({'results': [{'tweet': p[1], 'geojson': {'type': 'MultiPolygon', 'coordinates': p[0]}} for p in polys]})
    return (jsonify({'error': 'no tweet ids specified'}), 400)

if __name__ == "__main__":
    app.run()
