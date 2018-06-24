#!/usr/bin/python3 -u
from scipy.io import netcdf
from scipy.ndimage import zoom
from PIL import Image, ImageOps, ImageChops
from time import sleep

import subprocess
import numpy as np
import os
import gc

from tempfile import NamedTemporaryFile
from urllib.request import urlopen
import json
import datetime

# Format for URLs (spaces added by yours truly)
#                                                         <sensor>-<level>-<product short name>/<year>/<julian day>/<hour>/OR_<sensor>-<level>-<product short name>-M<scanning mode>-C<channel>-G<GOES Satellite>-s<start time>  _e<end time>    _c<central time>.nc
#https://storage.cloud.google.com/gcp-public-data-goes-16/ABI     -L2     -CMIPF               /2018  /070         /20    /OR_ABI     -L2     -CMIPF               -M3               C02       _G16              _s20180702000416_e20180702011183_c20180702011253.nc

# Path to store tempfiles to
TEMP = '/tmp'
STORAGE = '/home/bnitkin/goesr'
# URL to fetch directory listings from
#        https://www.googleapis.com/storage/v1/b/gcp-public-data-goes-16/o?prefix=ABI-L2-CMIPF/    2018/070/21/OR_ABI-L2-CMIPF-M3C01
DIR_LIST = 'https://www.googleapis.com/storage/v1/b/gcp-public-data-goes-16/o?prefix=ABI-L2-CMIPF/{date:%Y/%j/%H}/OR_ABI-L2-CMIPF-M3C{channel:02}'
# Size to chunk downloads into, bytes
CHUNK_SIZE = 5000000 # 5MB
# Final size of the generated images. Refer to the "Channel 2 is X by Y" message for the full size.
# This must be a common denominator to all layers. (10848, 5424, 2712, 1356, ...)
FINAL_SIZE = (10848, 10848)
FINAL_SIZE = (5424,  5424)
FINAL_SIZE = (2712,  2712)

THUMB_SIZE = (1000, 1000)

# Polling time - how often to check the API for new images (seconds)
# Full-disk scans come every 15 minutes.
POLL_TIME = 5*60

# How much timestamps can differ while being considered identical (seconds)
TIME_FUZZ = 60

class Timer(object):
    """A simple lap timer. On each call of lap(), it returns the elapsed time since the last call."""
    def __init__(self):
        self.last  = datetime.datetime.now()
        self.start = self.last
    def lap(self):
        old = self.last
        self.last = datetime.datetime.now()
        return (self.last - old).total_seconds()
    def total(self):
        self.lap()
        return (self.last - self.start).total_seconds()
    def delay(self, seconds):
        # Delays for the number of seconds since the last lap.
        # Reset the lap counter on exit.
        sleepTime = seconds - self.lap()
        if sleepTime > 0:
            print('Sleeping for {} seconds'.format(sleepTime))
            sleep(sleepTime)
        else:
            print('Period already expired ({}s ago)'.format(-sleepTime))
        self.lap()

def getLatestUrl(channel, offset=0):
    """ Gets the URL to the most recent GOES-R image of the specified channel."""
    #url = DIR_LIST.format(date=datetime.datetime.utcnow(), channel=channel)
    # Use local time - 7 hrs in the past.
    url = DIR_LIST.format(date=datetime.datetime.utcnow() - datetime.timedelta(seconds=offset), channel=channel)
    if offset == 0: print('Fetching file list:', url)
    text = urlopen(url, timeout=15).read().decode('utf-8')
    try: obj = json.loads(text)['items'][-1]
    except KeyError:
        # If nothing matches this hour, try an hour ago.
        if offset == 0:
            print(' - No data found for this hour; trying an hour ago')
            return getLatestUrl(channel, offset=3600)
        # If that also fails, die.
        print('No files matched the query.')
        raise
    return obj

def downloadFile(src, dest, size = 0):
    handle = urlopen(src, timeout=15)
    chunk = 'not an empty string'

    with open(dest, 'wb') as output:
        # Download the file!
        while chunk:
            print('Downloaded{: 4.1f} of{: 0.1f}MB: {}'.format(output.tell()/1E6, int(size)/1E6, dest), end='\r')
            chunk = handle.read(CHUNK_SIZE)
            output.write(chunk)
        output.flush()
        print()

def getLatestData(channel, obj, last=''):
    timer = Timer()
    filename = TEMP + '/' + os.path.basename(obj['name'])

    # Download file to /tmp and convert to netCDF3. If it's there already, cool.
    if not os.path.isfile(filename):
        try:
            downloadFile(obj['mediaLink'], filename, obj['size'])
            print(' - Converting netcdf4 to netcdf3', timer.lap())
            with NamedTemporaryFile(delete=False) as scratchNC:
                # Use nccopy to convert, then copy the netcdf3 file over the existing path.
                subprocess.check_call(('nccopy', '-3', filename, scratchNC.name))
                print(' - Moving back to original location', timer.lap())
                os.remove(                filename)
                os.rename(scratchNC.name, filename)
        except:
            # If something goes wrong, kill the file rather than leaving a corrupted download.
            os.remove(filename)
            raise
    else: # file already existed
        print('Downloaded:', filename, timer.lap())

    # Read it as CDF; pull out the reflectance data.
    print(' - Reading netCDF', timer.lap())
    with netcdf.netcdf_file(filename, 'r') as g16nc:
        print(' - Extracting reflectance', timer.lap())
        reflectance = g16nc.variables['CMI'][:] # Extract the reflectance

        zoom_factor = [FINAL_SIZE[0]/reflectance.shape[0], FINAL_SIZE[1]/reflectance.shape[1]]
        print(' - Channel {} is {} by {}; resizing by {}'.format(channel, g16nc.variables['CMI'].shape[0], g16nc.variables['CMI'].shape[1], zoom_factor), timer.lap())
        reflectance = zoom(reflectance, zoom_factor, order=1)

    # Optional: delete the netcdf to avoid clogging up the disk.
    # (On a 10GB disk, that's important)
    os.remove(filename)

    print(' - Ensuring all values are positive', timer.lap())
    np.maximum(reflectance, 0, reflectance)

    print(' - Applying gamma correction', timer.lap())
    reflectance = reflectance ** 0.55

    print(' - Scaling for improved contrast'.format(channel), timer.lap())
    reflectance *= 5

    print(' - Converting to image', timer.lap())
    image = Image.fromarray(reflectance).convert(mode='L')
    
    gc.collect()

    print(' - Total time:', timer.total())
    return image

def makeImage(lastTime = 0):
    timer = Timer()
    print('Downloading latest images')
    # Decide which file to download (obj includes filesize, a link, and some other stuff)
    obj = {} # Obj is a dictionary of file attributes - the latest image availiable for the specified channel.
    for channel in [1, 2, 3]:
        obj[channel] = getLatestUrl(channel)
        obj[channel]['time'] = int(obj[channel]['name'].split('_')[-1][1:-3])

    # Pick out a timestamp to use elsewhere.
    timestamp = obj[1]['time']

    # Check that all timestamps are "close"
    if   ((-TIME_FUZZ <= (obj[1]['time'] - obj[2]['time']) <= TIME_FUZZ)
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
        return lastTime

    # Check that the image has updated (no sense making duplicates)
    if timestamp == lastTime:
        print('Images have not changed since last check ({})'.format(obj[1]['time']))
        return lastTime

    # Getting to work - insert a break.
    print()

    blue   = getLatestData(1, obj[1]) # Load Channel 1 - Blue Visible
    red    = getLatestData(2, obj[2]) # Load channel 2 - Red visible
    veggie = getLatestData(3, obj[3]) # Load Channel 3 - Veggie Near IR

    # Clean up the NC files before continuing.
    gc.collect()

    print('Making a pseudo-green channel', timer.lap())
    # Derived from Planet Labs data, CC > 0.9
    # true_green = 0.48358168 * ch_2 + 0.45706946 * ch_1 + 0.06038137 * ch_3
    green = ImageChops.add(Image.eval(blue,   lambda x: x*0.45706946),
            ImageChops.add(Image.eval(red,    lambda x: x*0.48358168),
                           Image.eval(veggie, lambda x: x*0.06038137 )))

    print('Colorizing channels', timer.lap())
    red    = ImageOps.colorize(red,    (0, 0, 0), (255, 0, 0))
    veggie = ImageOps.colorize(veggie, (0, 0, 0), (0, 255, 0))
    green  = ImageOps.colorize(green , (0, 0, 0), (0, 255, 0))
    blue   = ImageOps.colorize(blue,   (0, 0, 0), (0, 0, 255))

    print('Generating geocolor and truecolor outputs', timer.lap())
    #geocolor  = ImageChops.add(ImageChops.add(red, veggie), blue)
    #geocolor.save(STORAGE+'/geocolor-{}.png'.format(timestamp))

    truecolor = ImageChops.add(ImageChops.add(red,  green), blue)
    truecolor.save(STORAGE+'/truecolor-{}.jpg'.format(timestamp))
    truecolor.resize(THUMB_SIZE).save(STORAGE+'/truecolor-thumb-{}.jpg'.format(timestamp))

    # Make a symlink pointing to the latest for javascript to point at.
    try: os.remove(                                           STORAGE+'/truecolor-latest.jpg')
    except FileNotFoundError: pass
    os.symlink(STORAGE+'/truecolor-{}.jpg'.format(timestamp), STORAGE+'/truecolor-latest.jpg')
    try: os.remove(                                           STORAGE+'/truecolor-thumb-latest.jpg')
    except FileNotFoundError: pass
    os.symlink(STORAGE+'/truecolor-thumb-{}.jpg'.format(timestamp), STORAGE+'/truecolor-thumb-latest.jpg')


    print('Done!', timer.lap())
    print('Total time:', timer.total())
    print()

    return timestamp

lastTime = 0
while True:
    timer = Timer()
    lastTime = makeImage(lastTime)
    timer.delay(5*60)
