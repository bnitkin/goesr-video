#!/usr/bin/python3
# Simple script to turn a bunch of photos into a video
import os, sys, glob, subprocess

FRAMES = 15*24*2 # 2 days of data
SRC =  '/home/bnitkin/goesr/truecolor-thumb-*.jpg'
DEST = '/home/bnitkin/goesr/video-{}.webm'
FRAMES = {'day':     24*4-1,
          'two-day': 24*4*2-1,
          'week':    24*4*7-1,
          'month':   24*4*31-1,
          'year':    24*4*365-1}

# frames per second (real time is four frames per hour)
RATE   = {'day':     '8',
          'two-day': '8',
          'week':    '16',
          'month':   '4',
          'year':    '8'}


def main():
    files = sorted(glob.glob(SRC))[-FRAMES[sys.argv[1]]:]
    print('Encoding the following', len(files), 'files:', files)

    # for month and year settings, use daily pictures instead of 15-minutes.
    # This iterates backwards, inserting every 24*4 images from the most recent.
    files_decimate = []
    if sys.argv[1] in ['month', 'year']:
        for index in range(len(files)):
             if index%(24*4) == 0:
                 print(len(files) - index - 1)
                 print(files[len(files) - index - 1])
                 files_decimate.insert(0, files[len(files) - index - 1])
        print('Decimated to', len(files_decimate), 'files:', files_decimate)
        files = files_decimate

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
        '-c:v', 'libvpx-vp9',
        '-crf', '30', '-b:v', '0',     # Constant quality (31 is suggested for 1080p)
        tmpfile), stdin=subprocess.PIPE)  # Write to a tempfile

    for path in files:
        with open(path, 'rb') as image:
            ffmpeg.stdin.write(image.read())
    ffmpeg.stdin.close()
    ffmpeg.wait()

    # Finally, move to the output area. 
    # This ensures that the final move is atomic, and reduces web-frontend screwups.
    os.rename('/tmp/video-{}.webm'.format(sys.argv[1]), DEST.format(sys.argv[1]))

main()
