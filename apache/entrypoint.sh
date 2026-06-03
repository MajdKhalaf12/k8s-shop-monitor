#!/bin/sh
set -e
BACKEND0="${WEBAPP_BACKEND_0:-webapp1:8000}"
BACKEND1="${WEBAPP_BACKEND_1:-webapp2:8000}"
sed -e "s|WEBAPP_BACKEND_0|${BACKEND0}|g" \
    -e "s|WEBAPP_BACKEND_1|${BACKEND1}|g" \
    /usr/local/apache2/conf/httpd.conf.in > /usr/local/apache2/conf/httpd.conf
exec httpd-foreground
