FROM alpine:3.15.2@sha256:ceeae2849a425ef1a7e591d8288f1a58cdf1f4e8d9da7510e29ea829e61cf512 AS extract

ARG TARGETOS
ARG TARGETARCH
ARG version=0.10.0
RUN wget "https://github.com/prometheus-community/postgres_exporter/releases/download/v${version}/postgres_exporter-${version}.${TARGETOS}-${TARGETARCH}.tar.gz" -O /tmp/postgres_exporter.tar.gz \
 && tar -C /usr/local/bin --strip-components 1 -xzf /tmp/postgres_exporter.tar.gz "postgres_exporter-${version}.${TARGETOS}-${TARGETARCH}/postgres_exporter" \
 && rm -f /tmp/postgres_exporter.tar.gz

EXPOSE 9187
USER nobody
ENTRYPOINT ["/usr/local/bin/postgres_exporter"]
