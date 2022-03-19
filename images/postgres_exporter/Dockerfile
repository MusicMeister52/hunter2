FROM alpine:3.15.1@sha256:d6d0a0eb4d40ef96f2310ead734848b9c819bb97c9d846385c4aca1767186cd4 AS extract

ARG TARGETOS
ARG TARGETARCH
ARG version=0.10.0
RUN wget "https://github.com/prometheus-community/postgres_exporter/releases/download/v${version}/postgres_exporter-${version}.${TARGETOS}-${TARGETARCH}.tar.gz" -O /tmp/postgres_exporter.tar.gz \
 && tar -C /usr/local/bin --strip-components 1 -xzf /tmp/postgres_exporter.tar.gz "postgres_exporter-${version}.${TARGETOS}-${TARGETARCH}/postgres_exporter" \
 && rm -f /tmp/postgres_exporter.tar.gz

EXPOSE 9187
USER nobody
ENTRYPOINT ["/usr/local/bin/postgres_exporter"]
