FROM nginx:1.27-alpine

COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY backend/app/web_static /usr/share/nginx/html/web

RUN rm -f /usr/share/nginx/html/index.html \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/run

USER nginx
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=6 \
  CMD wget -qO- http://127.0.0.1:8080/web-health | grep -q 'ok'
