# Simple little makefile to update video if and only if the output images have changed.

LOCK=/tmp/${TIME}.lockfile
/home/bnitkin/goesr/video-${TIME}.webm: /home/bnitkin/goesr/truecolor-thumb-*.jpg
	# Enforce only one running copy of make per recipe at a time via the lockfile.
	[ ! -f ${LOCK} ]
	touch ${LOCK}
	/home/bnitkin/videogen.py ${TIME}
	rm ${LOCK}

