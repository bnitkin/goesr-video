#!/usr/bin/python3
# Simple script to turn a bunch of photos into a video
import os, sys, glob, subprocess

FRAMES = 15*24*2 # 2 days of data
FRAMERATE = '8' # frames per second (real time is four frames per hour)
SRC =  '/home/bnitkin/goesr/truecolor-thumb-*.jpg'
DEST = '/home/bnitkin/goesr/video-{}.webm'
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
        '-c:v', 'libvpx-vp9',
        '-crf', '30', '-b:v', '0',     # Constant quality (31 is suggested for 1080p)
        '/tmp/video-{}.webm'.format(sys.argv[1])), stdin=subprocess.PIPE)  # Write to a tempfile

    for path in files:
        with open(path, 'rb') as image:
            ffmpeg.stdin.write(image.read())
    ffmpeg.stdin.close()
    ffmpeg.wait()

    # Finally, move to the output area. 
    # This ensures that the final move is atomic, and reduces web-frontend screwups.
    os.rename('/tmp/video-{}.webm'.format(sys.argv[1]), DEST.format(sys.argv[1]))

main()
