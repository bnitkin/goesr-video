#!/usr/bin/python3 -u
"""Create true-color imagery from GOES-R using the Google Compute data NOAA manages."""
import gc
import os

from time import sleep
from tempfile import NamedTemporaryFile
from urllib.request import urlopen
import json
import datetime

import subprocess
import numpy as np
from scipy.io import netcdf
from scipy.ndimage import zoom

from PIL import Image, ImageOps, ImageChops

# Format for URLs (spaces added by yours truly)
#                                                         <sensor>-<level>-<product short name>/<year>/<julian day>/<hour>/OR_<sensor>-<level>-<product short name>-M<scanning mode>-C<channel>-G<GOES Satellite>-s<start time>  _e<end time>    _c<central time>.nc
#https://storage.cloud.google.com/gcp-public-data-goes-16/ABI     -L2     -CMIPF               /2018  /070         /20    /OR_ABI     -L2     -CMIPF               -M3               C02       _G16              _s20180702000416_e20180702011183_c20180702011253.nc

# Path to keep images and thumbnails long-term
STORAGE = '/home/bnitkin/goesr'

# URL to fetch directory listings from
#        https://www.googleapis.com/storage/v1/b/gcp-public-data-goes-16/o?prefix=ABI-L2-CMIPF/    2018/070/21/OR_ABI-L2-CMIPF-M3C01
DIR_LIST = 'https://www.googleapis.com/storage/v1/b/gcp-public-data-goes-16/o?prefix=ABI-L2-CMIPF/{date:%Y/%j/%H}/OR_ABI-L2-CMIPF-M6C{channel:02}'

# Size to chunk downloads into, bytes
CHUNK_SIZE = 5000000 # 5MB

# Final size of the generated images. Refer to the "Channel 2 is X by Y"
# message for the full size.
# This must be a common denominator to all layers. (10848, 5424, 2712, 1356, ...)
#FINAL_SIZE = (10848, 10848)
#FINAL_SIZE = (5424, 5424)
FINAL_SIZE = (2712, 2712)

# Thumbnail size. Thumbs are generated from the larger downscaled images.
THUMB_SIZE = (1000, 1000)

# Polling time - how often to check the API for new images (seconds)
# Full-disk scans come every 10 minutes.
POLL_TIME = 5*60

# How much timestamps can differ while being considered identical (seconds)
# Images are timestamped with a lot of precision; layers can come in a few seconds
# from each other, even as part of the same scan
TIME_FUZZ = 60

# Internally, timestamps are accurate to 1/10th of a second. Convert to that.
TIME_FUZZ *= 10

class Timer():
    """A simple lap timer. On each call of lap(), it
    returns the elapsed time since the last call."""
    def __init__(self):
        """Setup the timer."""
        self.last = datetime.datetime.now()
        self.start = self.last
    def lap(self):
        """Drop a marker. Return the time since lap() was last called."""
        old = self.last
        self.last = datetime.datetime.now()
        return (self.last - old).total_seconds()
    def total(self):
        """Get time since timer was started."""
        self.lap()
        return (self.last - self.start).total_seconds()
    def delay(self, seconds):
        """Delays for the number of seconds since the last lap.
        Reset the lap counter on exit."""
        sleep_time = seconds - self.lap()
        if sleep_time > 0:
            print('Sleeping for {} seconds'.format(sleep_time))
            sleep(sleep_time)
        else:
            print('Period already expired ({}s ago)'.format(-sleep_time))
        self.lap()

def get_image_list(url):
    """Given a URL to a google bucket, return a list of items inside.
    Or an empty list, if it's empty. This compensates for the 'items'
    key missing in empty folders."""
    response = json.loads(urlopen(url, timeout=15).read().decode('utf-8'))
    try:
        return response['items']
    except KeyError:
        return []

def get_next_url(channel, timestamp):
    """Gets the URL to the image immediately after the given timestamp.
    If the provided timestamp is the latest, it's returned."""
    # Query for current and prior hour. Should give 6-12 image results.
    prior = DIR_LIST.format(
        date=datetime.datetime.utcnow() - datetime.timedelta(seconds=3600), channel=channel)
    current = DIR_LIST.format(
        date=datetime.datetime.utcnow(), channel=channel)
    #print('Fetching file list:', current)
    image_list = get_image_list(prior) + get_image_list(current)
    # Generate a timestamp for each image. Return the first image whose
    # timestamp is greater than the provided one.
    image = {}
    for image in image_list:
        if get_time(image) > timestamp + TIME_FUZZ:
            return image
    return image

def download_file(src, dest, size=0):
    """Downloads a file, given a source and destination.
    Basically wget, but native."""
    handle = urlopen(src, timeout=15)
    chunk = 'not an empty string'

    print(' - Downloading{: 0.1f}MB: {}'.format(int(size)/1E6, src))
    # Download the file!
    while chunk:
        chunk = handle.read(CHUNK_SIZE)
        dest.write(chunk)
    dest.flush()

def process_layer(obj):
    """Process a single layer into something human eyes can appreciate.
    Handles netcdf downscaling and gamma correction, then returns a
    monochrome image layer."""
    timer = Timer()

    # Download the netcdf4; convert to netcdf3, and extract the reflectance channel.
    # Then delete the sources.
    with NamedTemporaryFile() as download3, NamedTemporaryFile() as download4:
        download_file(obj['mediaLink'], download4, obj['size'])
        # netcdf3 reads much faster than netcdf4. Not sure why.
        print(' - Converting netcdf4 to netcdf3', timer.lap())
        subprocess.check_call(('nccopy', '-3', download4.name, download3.name))

        print(' - Reading netCDF', timer.lap())
        with netcdf.netcdf_file(download3.name, 'r') as g16nc:
            print(' - Extracting reflectance', timer.lap())
            reflectance = g16nc.variables['CMI'][:] # Extract the reflectance

            zoom_factor = [FINAL_SIZE[0]/reflectance.shape[0], FINAL_SIZE[1]/reflectance.shape[1]]
            print(' - Channel is {} by {}; resizing by {}'.format(
                g16nc.variables['CMI'].shape[0],
                g16nc.variables['CMI'].shape[1],
                zoom_factor),
                  timer.lap())
            reflectance = zoom(reflectance, zoom_factor, order=1)

    print(' - Ensuring all values are positive', timer.lap())
    np.maximum(reflectance, 0, reflectance)

    print(' - Applying gamma correction', timer.lap())
    reflectance = reflectance ** 0.55

    print(' - Scaling for improved contrast', timer.lap())
    reflectance *= 5

    print(' - Converting to image', timer.lap())
    image = Image.fromarray(reflectance).convert(mode='L')

    gc.collect()

    print(' - Layer time:', timer.total())
    return image

def get_time(handle):
    """Convert a JSON data descriptor to a datestamp.
    'name' is of the form:
    ABI-L2-CMIPF/2020/358/00/OR_ABI-L2-CMIPF-M6C03_G16_s20203580040209_e20203580049517_c20203580049598.nc
    So splitting on underscores and taking the last gets:
    c20203580049598.nc
    Then we strip off the 'c' and '.nc'. The final timestamp is:
    20203580049598
    YYYYDDDHHMMSSmmm
    """
    return int(handle['name'].split('_')[-1][1:-3])

def make_image(last_time=0):
    """Put it all together. Download three images, compose them into color, and
    save them to sensibly-named files"""
    timer = Timer()
    print('Downloading latest images')
    # Decide which file to download (obj includes filesize, a link, and some other stuff)
    obj = {} # Obj is a dictionary of file attributes. Next image availiable for each channel.
    for channel in [1, 2, 3]:
        obj[channel] = get_next_url(channel, last_time)
        obj[channel]['time'] = get_time(obj[channel])

    # Pick out a timestamp to use elsewhere.
    timestamp = obj[1]['time']

    # Check that all timestamps are "close"
    if ((-TIME_FUZZ <= (obj[1]['time'] - obj[2]['time']) <= TIME_FUZZ)
         and (-TIME_FUZZ <= (obj[1]['time'] - obj[3]['time']) <= TIME_FUZZ)
         and (-TIME_FUZZ <= (obj[2]['time'] - obj[3]['time']) <= TIME_FUZZ)):
        print('Images are time-synchronous ({}, {}, and {})'.format(
            obj[1]['time'],
            obj[2]['time'],
            obj[3]['time']))
    else:
        # If not, try again later.
        print('Images are not time-synchronous ({}, {}, and {})'.format(
            obj[1]['time'],
            obj[2]['time'],
            obj[3]['time']))
        return last_time

    # Check that the image has updated (no sense making duplicates)
    if timestamp == last_time:
        print('Images have not changed since last check ({})'.format(obj[1]['time']))
        return last_time

    # Getting to work - insert a break.
    print()
    print('Layers were captured {} ago.'.format(
            datetime.datetime.utcnow() -
            datetime.datetime.strptime(str(last_time), '%Y%j%H%M%S%f')))

    print('Processing blue layer')
    blue = process_layer(obj[1]) # Load Channel 1 - Blue Visible
    print('Processing red layer')
    red = process_layer(obj[2]) # Load channel 2 - Red visible
    print('Processing veggie layer')
    veggie = process_layer(obj[3]) # Load Channel 3 - Veggie Near IR

    # Clean up the NC files before continuing.
    gc.collect()

    print('Making a pseudo-green channel', timer.lap())
    # Derived from Planet Labs data, CC > 0.9
    # true_green = 0.48358168 * ch_2 + 0.45706946 * ch_1 + 0.06038137 * ch_3
    green = ImageChops.add(Image.eval(blue,   lambda x: x*0.45706946),
            ImageChops.add(Image.eval(red,    lambda x: x*0.48358168),
                           Image.eval(veggie, lambda x: x*0.06038137)))

    print('Colorizing channels', timer.lap())
    red    = ImageOps.colorize(red,   (0, 0, 0), (255, 0, 0))
    green  = ImageOps.colorize(green, (0, 0, 0), (0, 255, 0))
    blue   = ImageOps.colorize(blue,  (0, 0, 0), (0, 0, 255))
    #veggie = ImageOps.colorize(veggie, (0, 0, 0), (0, 255, 0))

    print('Generating color outputs', timer.lap())
    # Uncomment this and veggie for 'geocolor', using the veggie layer as green.
    # It's not true color and looks a little funny.
    #geocolor  = ImageChops.add(ImageChops.add(red, veggie), blue)
    #geocolor.save(STORAGE+'/geocolor-{}.png'.format(timestamp))

    truecolor = ImageChops.add(ImageChops.add(red, green), blue)
    truecolor.save(STORAGE+'/truecolor-{}.jpg'.format(timestamp))
    truecolor.resize(THUMB_SIZE).save(STORAGE+'/truecolor-thumb-{}.jpg'.format(timestamp))

    # Make a symlink pointing to the latest for javascript to point at.
    # Symlink + move is atomic.
    os.symlink(STORAGE+'/truecolor-{}.jpg'.format(timestamp),
               STORAGE+'/truecolor-latest.jpg.tmp')
    os.symlink(STORAGE+'/truecolor-thumb-{}.jpg'.format(timestamp),
               STORAGE+'/truecolor-thumb-latest.jpg.tmp')
    os.rename(STORAGE+'/truecolor-latest.jpg.tmp', STORAGE+'/truecolor-latest.jpg')
    os.rename(STORAGE+'/truecolor-thumb-latest.jpg.tmp', STORAGE+'/truecolor-thumb-latest.jpg')

    print('Finished writing', timer.lap())
    print('Total time:', timer.total())
    print()

    return timestamp

def main():
    """Simple mainloop to call the image generator every 5 mins."""
    # Bogus but correctly-sized timestamp
    # (First day of 2000; stroke of midnight)
    last_time = 20010010000000
    while True:
        # Every five minutes, try to build a new image set.
        # make_image will return early if there's no new data.
        timer = Timer()
        last_time = make_image(last_time)
        timer.delay(2*60)
if __name__ == '__main__':
    main()
