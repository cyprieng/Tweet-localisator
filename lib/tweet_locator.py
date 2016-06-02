import logging
import re
import requests
import shapefile
import string

from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
from matplotlib.path import Path
from nltk.tag import pos_tag

from twitter_custom import TwitterCustom


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_geoname_area(locations):
    """Get a list of poly (describing a geographic location) matching the given locations.

    Args:
        locations: list of location string

    Returns:
        A list of polygons
    """
    # Filter locations (more than 3 letters) and remove punctuation
    exclude = set(string.punctuation)
    locations_2 = [''.join(ch for ch in l if ch not in exclude) for l in locations]
    locations = [l for l in locations_2 if len(l) > 3]

    # Get only proper nouns
    tagged_sent = pos_tag(locations)
    locations = [word for word,pos in tagged_sent if pos == 'NNP']

    logger.info(u'Searching polys for {0}'.format(locations))

    polys = []

    for loc in locations:
        data = requests.get(u'https://nominatim.openstreetmap.org/search/{0}?format=json&limit=10&polygon=1&addressdetails=1'.format(loc)).json()
        logger.info(u'Matched {0} with {1}'.format(loc, [d['display_name'] for d in data]))
        polys += [[[float(point[0]), float(point[1]), float(d['importance'])] for point in d['polygonpoints']] for d in data if 'polygonpoints' in d.keys()]

    return polys


def get_time_zone_area(time_zone):
    """Get a poly (describing a geographic location) matching the given time_zone.

    Args:
        time_zone: time_zone to find

    Returns:
        A polygon
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
        poly: polygon to modify.
        z: value of the new dimension.

    Returns:
        Polygon with a new dimension.
    """
    for p in poly:
        if len(p) == 2:
            p.append(z)
        else:
            p[2] += z
    return poly


def accumulate_polys(polygons):
    """Accumulate polys. For each intersecting polys, addition the z.

    Args:
        polygons: list of polygons.

    Returns:
        A list of polygons.
    """
    # Make path
    paths = [Path([[p[0], p[1]] for p in poly]) for poly in polygons]

    poly_agg = []
    for poly in polygons:
        temp_poly = []

        for point in poly:
            z_temp = point[2]

            # Cumulate z for intersecting poly
            for i in range(0, len(polygons) - 1):
                if not polygons[i] == poly:
                    if paths[i].contains_point([point[0], point[1]]):
                        z_temp += polygons[i][0][2]

            temp_poly.append([point[0], point[1], z_temp])

        poly_agg.append(temp_poly)

    return poly_agg


def get_max_poly(polys):
    """Get the polys with the highter z.

    Args:
        polys: list of polygons.

    Returns:
        A list of polygons with the highter z.
    """
    max_poly = []
    z_max = max([max([point[2] for point in poly]) for poly in polys])
    logger.info(u'Maximum z: {0}'.format(z_max))
    for poly in polys:
        max_poly_temp = []
        for point in poly:
            if point[2] == z_max:
                max_poly_temp.append(point)
        if max_poly_temp:
            max_poly.append(max_poly_temp)
    return max_poly


def determinate_tweet_location(tweet_id):
    """Determinate the most probable location of the tweet with the given id.

    Args:
        tweet_id: Id of the tweet to analyse.

    Returns:
        A polygon representing the most probable location.
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

    polys_agg = accumulate_polys(polys)
    return get_max_poly(polys_agg)
