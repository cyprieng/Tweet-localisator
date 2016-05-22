import logging
import re
import requests
import shapefile
import string

from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
from matplotlib.path import Path

from twitter_custom import TwitterCustom


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def find_word(w, s):
    """Search a word in a string

    Args:
        w: word to search
        s: string where the word is searched

    Returns:
        Match occurence (cf re module)
    """
    return re.compile(ur'\b({0})\b'.format(w), flags=re.IGNORECASE).search(s)


def get_geoname_area(locations):
    """Get a list of poly (describing a geographic location) matching the given locations.

    Args:
        locations: list of location string

    Returns:
        A list of polygones
    """
    # Filter locations (more than 3 letters) and remove punctuation
    exclude = set(string.punctuation)
    locations_2 = [''.join(ch for ch in l if ch not in exclude) for l in locations]
    locations = [l for l in locations_2 if len(l) > 3]

    logger.info(u'Searching polys for {0}'.format(locations))

    polys = []

    for loc in locations:
        data = requests.get(u'https://nominatim.openstreetmap.org/search/{0}?format=json&limit=10&polygon=1'.format(loc)).json()
        polys += [d['polygonpoints'] for d in data if 'polygonpoints' in d.keys()]

    return polys


def get_time_zone_area(time_zone):
    """Get a poly (describing a geographic location) matching the given time_zone.

    Args:
        time_zone: time_zone to find

    Returns:
        A polygone
    """
    tz = shapefile.Reader("data/tz/tz_world_mp")
    records = tz.records()

    index_tz = 0
    for name in records:
        if time_zone in name[0]:
            return tz.shape(index_tz).points
        index_tz += 1

    logger.warning(u'Timezone: {0} not found'.format(time_zone))

    return []


def add_z(poly, z):
    """Add a dimension in the given poly with the given value.

    Args:
        poly: polygone to modify.
        z: value of the new dimension.

    Returns:
        Polygone with a new dimension.
    """
    for p in poly:
        p.append(z)
    return poly


def aggregate_polys(polygones):
    """Aggregates the given 3D polygones.

    Args:
        polygones: list of polygones.

    Returns:
        A list of x, y, z
    """
    # Make path
    paths = [Path([[p[0], p[1]] for p in poly]) for poly in polygones]

    x = []
    y = []
    z = []
    for poly in polygones:
        for point in poly:
            x.append(point[0])
            y.append(point[1])
            z_temp = point[2]

            # Cumulate z for intersecting poly
            for i in range(0, len(polygones) - 1):
                if not polygones[i] == poly:
                    if paths[i].contains_point([point[0], point[1]]):
                        z_temp += polygones[i][0][2]

            z.append(z_temp)

    return x, y, z


def make_graph(x, y, z):
    """Show a graph for the given coordinates.

    Args:
        x: x coordinates.
        y: y coordinates.
        z: z coordinates.
    """
    fig = plt.figure()
    ax = Axes3D(fig)

    ax.plot_trisurf(x, y, z)

    ax.set_xlim3d(min(x), max(x))
    ax.set_ylim3d(min(y), max(y))
    ax.set_zlim3d(min(z), max(z))
    plt.show()


def get_max_poly(x, y, z):
    """Extract the poly with the bigger z.

    Args:
        x: x coordinates.
        y: y coordinates.
        z: z coordinates.

    Returns:
        A polygone
    """
    max_poly = []
    z_max = max(z)
    for i in range(0, len(z) - 1):
        if z[i] == z_max:
            max_poly.append([x[i], y[i]])
    return max_poly


def determinate_tweet_location(tweet_id):
    """Determinate the most probable location of the tweet with the given id.

    Args:
        tweet_id: Id of the tweet to analyse.

    Returns:
        A polygone representing the most probable location.
    """
    t = TwitterCustom()
    tweet = t.get_tweet(tweet_id)
    polys = []

    # Get area by geoname in tweet
    poly = get_geoname_area(tweet['text'].split())
    if poly:
        for p in poly:
            polys.append(add_z(p, 3))

    # Get area by timezone
    p = get_time_zone_area(tweet['user']['time_zone'])
    if p:
        polys.append(add_z(p, 1))

    # Get area by user localisation in profile
    poly = get_geoname_area(tweet['user']['location'].split())
    if poly:
        for p in poly:
            polys.append(add_z(p, 3))

    x, y, z = aggregate_polys(polys)
    return get_max_poly(x, y, z)
