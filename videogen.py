#!/usr/bin/python3
# Simple script to turn a bunch of photos into a video
import os, sys, glob, subprocess
from datetime import datetime

#sys.argv[2]

FRAMES = 15*24*2 # 2 days of data
SRC =  '/home/bnitkin/goesr/truecolor-thumb-*.jpg'
DEST = '/home/bnitkin/goesr/video-{}.webm'
FRAMES = {'day':     24*6-1,
          'two-day': 24*6*2-1,
          'week':    24*6*7-1,
          'month':   31,
          'year':    365}

# frames per second (real time is four frames per hour)
RATE   = {'day':     '12',
          'two-day': '12',
          'week':    '24',
          'month':   '4',
          'year':    '8'}


def main():
    files = sorted(glob.glob(SRC))
    crf = '31'
    if sys.argv[1] == 'week': crf = '45'
    if sys.argv[1] == 'year': crf = '37'

    # for month and year settings, use daily pictures instead of 15-minutes.
    # This uses some cleverness to find the file closest to noon for each day.
    if sys.argv[1] in ['month', 'year']:
        # Build a sorted list of file mtime and path
        files = [(os.path.getmtime(f), f) for f in files]
        files_daily = []
	# 1640Z is local noon for GOES-East.
        noon = datetime.utcnow().replace(hour=16, minute=40, second=0).timestamp()
        for index in range(FRAMES[sys.argv[1]]):
            ideal_time = noon - 3600*24*index
            file       = min(files, key=lambda f: abs(f[0] - ideal_time))[1]
            # Insist that "noon" imagery be +/- an hour of noon.
            if abs(os.path.getmtime(file) - ideal_time) > 3600: continue
            files_daily.insert(0, file)
        files = files_daily
    else:
        files = files[-FRAMES[sys.argv[1]]:]

    print('Encoding the following', len(files), 'files:', files)

    tmpfile =  '/tmp/video-{}.webm'.format(sys.argv[1])
    if os.path.isfile(tmpfile):
        print("ERROR: output file {} already exists. Aborting.".format(tmpfile))
        exit(1)
    open(tmpfile, 'w').close() # Touch tmpfile (ffmpeg takes a while to flush its output)

    ffmpeg = subprocess.Popen(('ffmpeg',
        '-framerate', RATE[sys.argv[1]], # Framerate from RATE
        '-y',                          # Overwrite output path
        '-f', 'image2pipe', '-i', '-', # Read images from stdin
        '-pix_fmt', 'yuv420p',         # Force older pixel format to make Firefox happy.
        '-c:v', 'libvpx-vp9', '-an',
# Settings to make it go a litte faster, but at a quality tradeoff.
#        '-cpu-used', '2',
#        '-speed', '3',
        '-crf', crf, '-b:v', '0',     # Constant quality (31 is suggested for 1080p)
        tmpfile,
# Uncomment the below to add a mp4 output. Should work on Safari, but doesn't...
#        '-c:v', 'h264', '-c:a', 'aac',
#        '-pix_fmt', 'yuv420p',
#        '-preset', 'veryfast',
#        '-crf', '30', '-b:v', '0',     # Constant quality (18-24 is suggested for mp4)
#        tmpfile.replace('webm', 'mp4')
        ), stdin=subprocess.PIPE)      # Write to a tempfile

    for path in files:
        with open(path, 'rb') as image:
            ffmpeg.stdin.write(image.read())
    ffmpeg.stdin.close()
    ffmpeg.wait()

    # Finally, move to the output area. 
    # This ensures that the final move is atomic, and reduces web-frontend screwups.
    os.rename('/tmp/video-{}.webm'.format(sys.argv[1]), DEST.format(sys.argv[1]))
#    os.rename('/tmp/video-{}.mp4'.format(sys.argv[1]), DEST.format(sys.argv[1]).replace('webm', 'mp4'))

main()
