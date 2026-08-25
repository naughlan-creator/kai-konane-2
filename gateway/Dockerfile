# syntax=docker/dockerfile:1
FROM nginx:1.27-alpine

# Tells a registry which repository built this image. GHCR uses it to link
# the package to the repo automatically -- without it the packages exist but
# do not appear on the repo page, and have to be connected by hand.
LABEL org.opencontainers.image.source="https://github.com/naughlan-creator/kai-konane-2" \
      org.opencontainers.image.description="The single public entrypoint. Routes /api to the api." \
      org.opencontainers.image.licenses="MIT"


# Opt in to the image's resolver detection. Its 15-local-resolvers script
# returns early unless this is set, leaving NGINX_LOCAL_RESOLVERS undefined and
# the resolver directive un-substituted -- nginx then refuses to start.
ENV NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1

# templates/, not conf.d/. The nginx image runs envsubst over anything here at
# startup and writes the result into conf.d, which is what lets one image serve
# both compose and Container Apps.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80
