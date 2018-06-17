# GOES-R Video Generator
This is a simple video-generator leveraging the wonders of free online stuff.
It uses the GOES-R red, blue, and veggie bands to generate a near-realtime, true-color
video of the past few days of weather.

With the most recent GOES satellites, NOAA has been posting near-realtime imagery to a
Google Cloud bucket for public use
(https://console.cloud.google.com/storage/browser/gcp-public-data-goes-16)

Google also offers a very small VPS as a free demo, which I used to set the project up.
See it live at bluemarble.nitk.in!

People usually discuss the frameworks they used, but this is pretty basic.
It uses the latest in Javascript, HTML, and Python,
with a bit of shell and make thrown in for good measure.

This code should be fairly easy to use - you'll need to modify paths to remove my username,
but everything works!

# Details
The project consists of three largely independent components:
 - Image processing
 - Video generation
 - HTTP server
Cron acts as a job supervisor to hold everything together. (Again, quick and dirty).

## Image processing
GOES16.sci.py implements the image processing. When started, it goes into an infinite loop:
   - Poll the Cloud Bucket API
   - Check that all images are time-synchronized
   - Check if images have changed
   - If so, process into a JPG file
   - If not, wait 5 minutes and try again.

Image processing is a fairly simple pipeline. For each layer (red, blue, veggie):
   - Download the layer
   - Convert from netCDF4 to netCDF3
      - netCDF4 is newer, but the Python bindings for it are 5x slower than the netCDF3 libraries.
      - nccopy is used for the conversion
   - Scale to a managable size
      - layers start as 10848 pixels square, which swamps the VPS
   - Ensure all values are positive
      - Negatives show up sometimes and mess up gamma correction
   - Apply gamma correction
      - Fancy word for taking x^0.55 for each pixel value
   - Convert from numpy array to a PIL image
      - Saves space and prepares for final formatting

Finally, the images are combined
   - Create a green channel using red, blue, and veggie
   - Stack the layers to make a composite
   - Scale down to a thumbnail size for video-ing

## Video generation
The video generation is as dumb as a rock. `Cron` periodically calls a makefile;
the makefile checks whether the videos need regeneration, and they're rebuilt if so.

Refer to the `crontab` sample for cron rules. The makefile `video.mk` allows cron to
call the script every few minutes without undue overhead.

The script `videogen.py` looks at all the files in the output directory, finds the newest
(up to a configured limit) and compiles them into a video with ffmpeg.

The length of the video and output filename are configured programatically by the FRAMES
dictionary. `day`, `two-day`, `week`, `month`, and `year` all do about what you'd expect.

## HTTP Server
The final component of the whole setup is a simple Python HTTP server. You could use Apache
(or Nginx, or anything else), but on a disk-constrained server, I chose to use what was installed.

It just hosts `index.html` and the videos.

The HTML file allows a user to select between the different generated videos, and automatically
refreshes the videos to keep them near realtime.

## Glue
`Cron` provides the glue for this project. The rules included periodically run the video generator,
and will automatically restart both the HTTP server and the image processor if either die.

