
# Simple little makefile to update video if and only if the output images have changed.
/home/bnitkin/goesr/video-${TIME}.mp4: /home/bnitkin/goesr/truecolor-thumb-*.png
	/home/bnitkin/videogen.py ${TIME}
