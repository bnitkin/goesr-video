echo 'videogen  ' `pidof -x videogen.py`
echo 'compositor' `pidof -x GOES16.sci.py`
echo 'server    ' `pidof -x goesServer.py`
echo
echo
ps -p "`pidof -x GOES16.sci.py nccopy videogen.py ffmpeg goesServer.py`" -o %cpu,%mem,cmd
echo
free -h
