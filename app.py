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
    tweet_ids = request.form.get('tweetId')
    if tweet_ids:
        tweet_ids = tweet_ids.split(',')
    else:
        tweet_ids = []

    weight_text = int(request.form.get('weightText'))
    weight_timezone = int(request.form.get('weightTimezone'))
    weight_location_field = int(request.form.get('weightLocationField'))
    weight_language = int(request.form.get('weightLanguage'))
    weight_url = int(request.form.get('weightURL'))
    weight_geolocalization = int(request.form.get('weightGeolocalization'))

    polys = []
    for tweet_id in tweet_ids:
        polys.append(determinate_tweet_location(tweet_id, weight_text=weight_text, weight_timezone=weight_timezone,
                                                weight_location_field=weight_location_field,
                                                weight_language=weight_language, weight_url=weight_url,
                                                weight_geolocalization=weight_geolocalization))
    return render_template('map.html', polys=polys, maps_key=os.environ['GOOGLE_MAPS_KEY'])


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
