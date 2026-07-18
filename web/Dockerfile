FROM nginxinc/nginx-unprivileged:1.27-alpine

ARG GIT_SHA=unknown
ENV NAILS_GIT_SHA=${GIT_SHA}

COPY --chown=101:101 --chmod=0444 web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --chown=101:101 backend/app/web_static /usr/share/nginx/html/web

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=6 \
  CMD wget -qO- http://127.0.0.1:8080/web-health | grep -q 'ok'
