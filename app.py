import os
import sys

from flask import Flask
from flask import render_template
from flask.ext.socketio import emit
from flask.ext.socketio import SocketIO

from lib.tweet_locator import determinate_tweet_location

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.DEBUG)

app = Flask(__name__)

socketio = SocketIO(app)


@app.route('/')
def home():
    """Return the home page"""
    return render_template('home.html')


@socketio.on('connect')
def connect():
    emit('response', {'data': 'Connected'})


@socketio.on('disconnect')
def disconnect():
    log.info('Client disconnected')


@socketio.on('load map')
def load_map(tweet_id):
    poly = determinate_tweet_location(tweet_id)
    log.info(u'Finished to determine tweet {0} location'.format(tweet_id))
    emit('map ready', {'poly': poly, 'maps_key': os.environ['GOOGLE_MAPS_KEY']})


if __name__ == "__main__":
    log.info(u'Starting server on port: {0}'.format(int(sys.argv[1])))
    socketio.run(app, port=int(sys.argv[1]))
