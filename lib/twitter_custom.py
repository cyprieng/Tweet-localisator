from twitter import *


class TwitterCustom(object):
    """Class helping the integration with twitter.
    """

    def __init__(self):
        """Init the twitter API with the credentials.
        """
        consumer_key = 'xxxxxxxxx'
        consumer_secret = 'xxxxxxxxx'
        access_token = 'xxxxxxxxx'
        access_token_secret = 'xxxxxxxxx'

        self.api = Twitter(auth=OAuth(access_token, access_token_secret, consumer_key, consumer_secret))

    def get_tweet(self, id):
        """Get a tweet by its id.

        Args:
            id: id of the tweet to retrieve.

        Returns:
            Dict representing the tweet
        """
        return self.api.statuses.show(_id=id)
