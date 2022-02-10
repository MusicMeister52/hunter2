FROM alpine:3.15.0@sha256:21a3deaa0d32a8057914f36584b5288d2e5ecc984380bc0118285c70fa8c9300 AS extract

ARG TARGETOS
ARG TARGETARCH
ARG version=0.10.0
RUN wget "https://github.com/prometheus-community/postgres_exporter/releases/download/v${version}/postgres_exporter-${version}.${TARGETOS}-${TARGETARCH}.tar.gz" -O /tmp/postgres_exporter.tar.gz \
 && tar -C /usr/local/bin --strip-components 1 -xzf /tmp/postgres_exporter.tar.gz "postgres_exporter-${version}.${TARGETOS}-${TARGETARCH}/postgres_exporter" \
 && rm -f /tmp/postgres_exporter.tar.gz

EXPOSE 9187
USER nobody
ENTRYPOINT ["/usr/local/bin/postgres_exporter"]
