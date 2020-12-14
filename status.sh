#!/bin/bash
[ 'a'$1 == 'awatch' ] && (watch -n15 'bash -c "~bnitkin/status.sh | cut -c -$COLUMNS"'; exit)

# PID of each process and the last line of each logfile
echo -e "videogen:  $(pidof -x videogen.py || echo -e \\t) \t| $(echo /tmp/*webm)"
echo -e "compositor:$(pidof -x GOES16.sci.py             ) \t| $(tac ~bnitkin/logs/log.txt | grep -m1 '^Total')\t| 600s max"
echo -e "server:    $(pidof -x goesServer.py             ) \t| $(tail -n1 ~bnitkin/logs/server.txt)"
echo ''
# List of processes that these guys spawn
echo '%CPU %MEM CMD'
ps -p "`pidof -x GOES16.sci.py nccopy videogen.py ffmpeg goesServer.py`" -o %cpu=,%mem=,cmd= | sort -k3 -t' '
echo ''
echo ''
free -t --mega
echo ''
df   -h ~bnitkin
