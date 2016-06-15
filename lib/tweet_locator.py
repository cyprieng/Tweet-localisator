import csv
import json
import logging
import math
from multiprocessing.pool import ThreadPool
import requests
import shapefile
import urllib

from langid.langid import LanguageIdentifier, model
from shapely.geometry import Point
from shapely.geometry import Polygon as ShpPolygon

from twitter_custom import TwitterCustom

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Polygon(object):
    def __init__(self, points, origin=None, exclude_with=None):
        self.points = points
        self.origin = origin
        self.exclude_with = exclude_with


def get_polys_from_osm(osm_data, limit=None):
    """Get polygons from Open Street Map data.

    Args:
        osm_data: Open Street Map data

    Returns:
        List of polygons
    """
    polys = []
    counter = 1
    for result in osm_data:
        if (limit is None or limit >= counter) and 'polygon' in result['geojson']['type'].lower():
            counter += 1
            for p in result['geojson']['coordinates']:
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
    locations = [loc.replace('#', '').replace('?', '') for loc in locations if loc.replace('#', '')[0].isupper() and len(loc) > 3]

    logger.info(u'Searching polys for {0}'.format(locations))

    polys = []

    for loc in locations:
        data = requests.get(u'https://nominatim.openstreetmap.org/search/{0}?format=json&limit=10&polygon_geojson=1&addressdetails=1'.format(urllib.quote_plus(loc.encode('utf8')))).json()
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
    data = requests.get(u'https://nominatim.openstreetmap.org/search/{0}?format=json&limit=1&polygon_geojson=1'.format(urllib.quote_plus(country.encode('utf8')))).json()
    return get_polys_from_osm(data, limit=1)


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


def get_polys_from_tld(url):
    """Get a list of polys from the URL TLD.

    Args:
        url: url to analyse.

    Returns:
        A list of polygons.
    """
    tld = '.' + url.split('.')[-1]

    polys = []
    with open('./data/countries.json') as f:
        data = json.loads(f.read())
        for country in data:
            if tld in country['tld']:
                polys += get_country_polygons(country['name']['common'])
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
            'max_x': max([point[0] for point in poly.points]),
            'min_x': min([point[0] for point in poly.points]),
            'max_y': max([point[1] for point in poly.points]),
            'min_y': min([point[1] for point in poly.points])
        })

    poly_to_check = []
    i = 0
    for poly in polygons:
        poly_to_check_temp = []
        for j in range(0, len(polygons)):
            if not (poly.exclude_with is not None and poly.exclude_with == polygons[j].origin) and poly != polygons[j] and (not ((poly_box[i]['min_x'] > poly_box[j]['max_x']) or (poly_box[j]['min_x'] > poly_box[i]['max_x']))) and (not ((poly_box[i]['min_y'] > poly_box[j]['max_y']) or (poly_box[j]['min_y'] > poly_box[i]['max_y']))):
                poly_to_check_temp.append(j)
        poly_to_check.append(poly_to_check_temp)
        i += 1

    # Reduce poly precision
    for i in range(0, len(polygons)):
        polygons[i].points = [p for j, p in enumerate(polygons[i].points) if j % math.ceil(float(len(polygons[i].points)) / 100.) == 0]

    index = 0
    for poly in polygons:
        temp_poly = []
        logger.info(u'Accumulate poly: {0} with {1} polys'.format(index, len(poly_to_check[index])))

        if poly_to_check[index]:
            for point in poly.points:
                z_temp = point[2]

                # Cumulate z for intersecting poly
                for i in poly_to_check[index]:
                    if not (poly.exclude_with is not None and poly.exclude_with == polygons[i].origin) and Point(point[0], point[1]).within(ShpPolygon(polygons[i].points)):
                        z_temp += polygons[i].points[0][2]

                temp_poly.append([point[0], point[1], z_temp])
            poly_agg.append(temp_poly)
        else:
            poly_agg.append(poly.points)

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

    if polys:
        z_max = max([max([point[2] for point in poly]) for poly in polys])
        logger.info(u'Maximum z: {0}'.format(z_max))
        for poly in polys:
            max_poly_temp = []
            for point in poly:
                if point[2] == z_max:
                    max_poly_temp.append([point[0], point[1]])
            if max_poly_temp:
                max_poly.append(max_poly_temp)
    return (max_poly, z_max)


def determinate_tweet_location(tweet_id, weight_text=5, weight_timezone=2, weight_location_field=4,
                               weight_language=1, weight_url=1, weight_geolocalization=20, aggregate=True, ignore_previous=False):
    """Determinate the most probable location of the tweet with the given id.

    Args:
        tweet_id: Id of the tweet to analyse.

    Returns:
        A polygon representing the most probable location.
    """
    weight_text = int(weight_text) if weight_text is not None else 5
    weight_timezone = int(weight_timezone) if weight_timezone is not None else 2
    weight_location_field = int(weight_location_field) if weight_location_field is not None else 4
    weight_language = int(weight_language) if weight_language is not None else 1
    weight_url = int(weight_url) if weight_url is not None else 1
    weight_geolocalization = int(weight_geolocalization) if weight_geolocalization is not None else 20

    t = TwitterCustom()
    tweet = t.get_tweet(tweet_id)
    polys = []

    pool = ThreadPool(processes=4)

    if weight_text > 0:
        poly_text = pool.apply_async(get_geoname_area, (tweet['text'].split(), ))
    if weight_timezone > 0:
        poly_tz = pool.apply_async(get_time_zone_area, (tweet['user']['time_zone'], ))
    if weight_location_field > 0:
        poly_location = pool.apply_async(get_geoname_area, (tweet['user']['location'].split(), ))
    if weight_language > 0:
        poly_language = pool.apply_async(get_polys_from_language, (tweet['text'] + tweet['user']['description'], ))

    if 'url' in tweet['user']['entities'] and weight_url > 0:
        poly_tld = pool.apply_async(get_polys_from_tld, (tweet['user']['entities']['url']['urls'][0]['expanded_url'], ))

    # Get area by geoname in tweet
    if weight_text > 0:
        poly = poly_text.get()
        if poly:
            for p in poly:
                polys.append(Polygon(add_z(p, weight_text), origin='geoname in tweet'))

    # Get area by timezone
    if weight_timezone > 0:
        poly = poly_tz.get()
        if poly:
            polys.append(Polygon(add_z(poly, weight_timezone), origin='timezone', exclude_with='timezone'))

    # Get area by user localisation in profile
    if weight_location_field > 0:
        poly = poly_location.get()
        if poly:
            for p in poly:
                polys.append(Polygon(add_z(p, weight_location_field), origin='profile location'))

    # Get area by language
    if weight_language > 0:
        poly = poly_language.get()
        if poly:
            for p in poly:
                polys.append(Polygon(add_z(p, weight_language), origin='language', exclude_with='language'))

    # Get area by TLD
    if 'url' in tweet['user']['entities'] and weight_url > 0:
        poly = poly_tld.get()
        if poly:
            for p in poly:
                polys.append(Polygon(add_z(p, weight_url), origin='TLD'))

    # Geolocalization
    if tweet['place'] and weight_geolocalization > 0:
        polys += [Polygon(add_z(p, weight_geolocalization), origin='tweet place') for p in tweet['place']['bounding_box']['coordinates']]

    # Get location of previous tweet
    if not ignore_previous:
        previous_tweet = t.return_previous_tweet(tweet)
        polys_previous = determinate_tweet_location(previous_tweet['id'], weight_text=weight_text,
                                                    weight_timezone=weight_timezone,
                                                    weight_location_field=weight_location_field,
                                                    weight_language=weight_language, weight_url=weight_url,
                                                    weight_geolocalization=weight_geolocalization, ignore_previous=True)[0]
        polys += [Polygon(add_z(p, 3), origin='previous tweet') for p in polys_previous]

    if aggregate:
        polys_agg = accumulate_polys(polys)
        final_poly, z_max = get_max_poly(polys_agg)
    else:
        final_poly = [p.points for p in polys]
        z_max = 0.
    return ([p for p in final_poly if len(p) > 2], tweet, round(z_max, 2))
