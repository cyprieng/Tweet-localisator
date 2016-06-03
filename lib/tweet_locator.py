import csv
import logging
import math
from multiprocessing.pool import ThreadPool
import re
import requests
import shapefile
import string

from langid.langid import LanguageIdentifier, model
from nltk.tag import pos_tag
from shapely.geometry import Point, Polygon

from twitter_custom import TwitterCustom

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_polys_from_osm(osm_data):
    """Get polygons from Open Street Map data.

    Args:
        osm_data: Open Street Map data

    Returns:
        List of polygons
    """
    polys = []
    if osm_data and 'polygon' in osm_data[0]['geojson']['type'].lower():
        for p in osm_data[0]['geojson']['coordinates']:
            if isinstance(p[0][0], list):
                for p2 in p:
                    polys.append([[float(point[0]), float(point[1]), float(osm_data[0]['importance'])] for point in p2])
            else:
                polys.append([[float(point[0]), float(point[1]), float(osm_data[0]['importance'])] for point in p])
    return polys


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
        data = requests.get(u'https://nominatim.openstreetmap.org/search/{0}?format=json&limit=10&polygon_geojson=1&addressdetails=1'.format(loc)).json()
        logger.info(u'Matched {0} with {1}'.format(loc, [d['display_name'] for d in data]))
        polys += get_polys_from_osm(data)

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


def get_country_by_language(text):
    """Get the country which speak the language of the given text.

    Args:
        text: the text.

    Returns:
        A list of country
    """
    identifier = LanguageIdentifier.from_modelstring(model, norm_probs=True)
    lang = identifier.classify(text)[0]

    countries_matching = []
    with open('./data/country.csv', 'rb') as csvfile:
        countries = csv.reader(csvfile, delimiter=';', quotechar='|')
        for country in countries:
            if lang in country[51].replace(' ', '').split(','):
                countries_matching.append(country[4].strip())

    logger.info(u'Matched text with countries: {0}'.format(countries_matching))
    return countries_matching


def get_country_polygons(country):
    """Get the polygons of the given country.

    Args:
        country: name of the country.

    Returns:
        A list of polygons.
    """
    logger.info(u'Searching poly for country: {0}'.format(country))
    data = requests.get(u'https://nominatim.openstreetmap.org/search/{0}?format=json&limit=1&polygon_geojson=1'.format(country)).json()
    return get_polys_from_osm(data)


def get_polys_from_language(text):
    """Get the polys for the given text by taking into account the language.

    Args:
        text: the text.

    Returns:
        A list of polygons.
    """
    polys = []
    countries = get_country_by_language(text)
    pool = ThreadPool(processes=len(countries))
    results = []
    for country in countries:
        results.append(pool.apply_async(get_country_polygons, (country, )))

    for r in results:
        polys += r.get()
    return polys


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
    poly_agg = []

    # Check which polygon we need to check with which poly
    poly_box = []
    for poly in polygons:
        poly_box.append({
            'max_x': max([point[0] for point in poly]),
            'min_x': min([point[0] for point in poly]),
            'max_y': max([point[1] for point in poly]),
            'min_y': min([point[1] for point in poly])
        })

    poly_to_check = []
    i = 0
    for poly in polygons:
        logger.info(u'Checking intersecting poly with poly: {0}/{1}'.format(i, len(polygons)))
        poly_to_check_temp = []
        for j in range(0, len(polygons)):
            if poly != polygons[j] and (not ((poly_box[i]['min_x'] > poly_box[j]['max_x']) or (poly_box[j]['min_x'] > poly_box[i]['max_x']))) and (not ((poly_box[i]['min_y'] > poly_box[j]['max_y']) or (poly_box[j]['min_y'] > poly_box[i]['max_y']))):
                poly_to_check_temp.append(j)
        poly_to_check.append(poly_to_check_temp)
        i += 1

    # Reduce poly precision
    for i in range(0, len(polygons)):
        polygons[i] = [p for j, p in enumerate(polygons[i]) if j % math.ceil(float(len(polygons[i])) / 100.) == 0]

    index = 0
    for poly in polygons:
        temp_poly = []
        logger.info(u'Accumulate poly: {0} with {1} polys'.format(index, len(poly_to_check[index])))

        if poly_to_check[index]:
            for point in poly:
                z_temp = point[2]

                # Cumulate z for intersecting poly
                for i in poly_to_check[index]:
                    if Point(point[0], point[1]).within(Polygon(polygons[i])):
                        z_temp += polygons[i][0][2]

                temp_poly.append([point[0], point[1], z_temp])
            poly_agg.append(temp_poly)
        else:
            poly_agg.append(poly)

        index += 1

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

    # Get area by language
    poly = get_polys_from_language(tweet['text'] + tweet['user']['description'])
    if poly:
        for p in poly:
            polys.append(add_z(p, 1))

    polys_agg = accumulate_polys(polys)
    return get_max_poly(polys_agg)
