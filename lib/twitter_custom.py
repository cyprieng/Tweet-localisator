import os

from twitter import *


class TwitterCustom(object):
    """Class helping the integration with twitter.
    """

    def __init__(self):
        """Init the twitter API with the credentials.
        """
        consumer_key = os.environ['TWITTER_CONSUMER_KEY']
        consumer_secret = os.environ['TWITTER_CONSUMER_SECRET']
        access_token = os.environ['TWITTER_TOKEN']
        access_token_secret = os.environ['TWITTER_TOKEN_SECRET']

        self.api = Twitter(auth=OAuth(access_token, access_token_secret, consumer_key, consumer_secret))

    def get_tweet(self, id):
        """Get a tweet by its id.

        Args:
            id: id of the tweet to retrieve.

        Returns:
            Dict representing the tweet
        """
        return self.api.statuses.show(_id=id)
