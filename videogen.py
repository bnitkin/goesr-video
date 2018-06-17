#!/usr/bin/python3
# Simple script to turn a bunch of photos into a video
import sys, glob, subprocess

FRAMES = 15*24*2 # 2 days of data
FRAMERATE = '8' # frames per second (real time is four frames per hour)
SRC =  '/home/bnitkin/goesr/truecolor-thumb-*'
DEST = '/home/bnitkin/goesr/video-{}.mp4'
FRAMES = {'day':     24*4,
          'two-day': 24*4*2,
          'week':    24*4*7,
          'month':   24*4*31,
          'year':    24*4*365}

def main():
    files = sorted(glob.glob(SRC))[-FRAMES[sys.argv[1]]:]
    print('Encoding the following', len(files), 'files:', files)

    ffmpeg = subprocess.Popen(('ffmpeg',
        '-framerate', FRAMERATE,       # 10fps video
        '-y',                          # Overwrite output path
        '-f', 'image2pipe', '-i', '-', # Read images from stdin
        '-pix_fmt', 'yuv420p',         # Force older pixel format to make Firefox happy.
        DEST.format(sys.argv[1])), stdin=subprocess.PIPE)  # Write to DEST

    for path in files:
        with open(path, 'rb') as image:
            ffmpeg.stdin.write(image.read())
    ffmpeg.stdin.close()
    ffmpeg.wait()

main()
