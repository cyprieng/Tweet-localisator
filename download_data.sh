#!/bin/bash

wget http://biogeo.ucdavis.edu/data/gadm2.8/gadm28_levels.shp.zip
mkdir ./data/geoname
unzip gadm28_levels.shp.zip -d ./data/geoname
rm gadm28_levels.shp.zip
