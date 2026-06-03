FROM httpd:2.4-alpine
RUN apk add --no-cache openssl mod_qos 2>/dev/null || true
RUN sed -i \
    's/#LoadModule rewrite_module/LoadModule rewrite_module/' \
    /usr/local/apache2/conf/httpd.conf && \
    sed -i \
    's/#LoadModule proxy_module/LoadModule proxy_module/' \
    /usr/local/apache2/conf/httpd.conf && \
    sed -i \
    's/#LoadModule proxy_http_module/LoadModule proxy_http_module/' \
    /usr/local/apache2/conf/httpd.conf && \
    sed -i \
    's/#LoadModule proxy_balancer_module/LoadModule proxy_balancer_module/' \
    /usr/local/apache2/conf/httpd.conf && \
    sed -i \
    's/#LoadModule slotmem_shm_module/LoadModule slotmem_shm_module/' \
    /usr/local/apache2/conf/httpd.conf && \
    sed -i \
    's/#LoadModule status_module/LoadModule status_module/' \
    /usr/local/apache2/conf/httpd.conf && \
    sed -i \
    's/#LoadModule headers_module/LoadModule headers_module/' \
    /usr/local/apache2/conf/httpd.conf && \
    sed -i \
    's/#LoadModule ssl_module/LoadModule ssl_module/' \
    /usr/local/apache2/conf/httpd.conf && \
    sed -i \
    's/#LoadModule socache_shmcb_module/LoadModule socache_shmcb_module/' \
    /usr/local/apache2/conf/httpd.conf && \
    sed -i \
    's/#LoadModule lbmethod_byrequests_module/LoadModule lbmethod_byrequests_module/' \
    /usr/local/apache2/conf/httpd.conf
COPY httpd.conf /usr/local/apache2/conf/httpd.conf.in
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p /logs /usr/local/apache2/conf/ssl
EXPOSE 80 443
ENTRYPOINT ["/entrypoint.sh"]
