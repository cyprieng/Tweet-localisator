# Tweet locator
Tweet-locator is a website that try to localize a tweet without geolocalization activated. It is an implementation of [this paper](https://www.aaai.org/ocs/index.php/ICWSM/ICWSM13/paper/viewFile/6063/6397) with some modifications. You can try an online version [here](http://cyprien.guillemot.me/tweet-locator/).

Please note that the localization of a tweet currently takes about one minute.

# How to run it
If you want to run it yourself, install all the dependencies: `pip install -r requirements.txt`.

Then you need to create a twitter app and get a key for the Google Maps API. Then set these environment variables:
* TWITTER_CONSUMER_KEY
* TWITTER_CONSUMER_SECRET
* TWITTER_TOKEN
* TWITTER_TOKEN_SECRET
* GOOGLE_MAPS_KEY

You can fill `env.sh` and run `source env.sh`.

Finally you can run `python app.py PORT_NUMBER` or `./run.sh`, and your web server will be ready.
