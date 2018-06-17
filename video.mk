
# Simple little makefile to update video if and only if the output images have changed.
/home/bnitkin/goesr/video-${TIME}.webm: /home/bnitkin/goesr/truecolor-thumb-*.jpg
	/home/bnitkin/videogen.py ${TIME}
