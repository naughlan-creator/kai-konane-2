# syntax=docker/dockerfile:1
FROM nginx:1.27-alpine

# Opt in to the image's resolver detection. Its 15-local-resolvers script
# returns early unless this is set, leaving NGINX_LOCAL_RESOLVERS undefined and
# the resolver directive un-substituted -- nginx then refuses to start.
ENV NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1

# templates/, not conf.d/. The nginx image runs envsubst over anything here at
# startup and writes the result into conf.d, which is what lets one image serve
# both compose and Container Apps.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80
