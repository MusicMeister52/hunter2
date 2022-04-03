FROM alpine:3.15.3@sha256:f22945d45ee2eb4dd463ed5a431d9f04fcd80ca768bb1acf898d91ce51f7bf04 AS extract

ARG TARGETOS
ARG TARGETARCH
ARG version=0.10.0
RUN wget "https://github.com/prometheus-community/postgres_exporter/releases/download/v${version}/postgres_exporter-${version}.${TARGETOS}-${TARGETARCH}.tar.gz" -O /tmp/postgres_exporter.tar.gz \
 && tar -C /usr/local/bin --strip-components 1 -xzf /tmp/postgres_exporter.tar.gz "postgres_exporter-${version}.${TARGETOS}-${TARGETARCH}/postgres_exporter" \
 && rm -f /tmp/postgres_exporter.tar.gz

EXPOSE 9187
USER nobody
ENTRYPOINT ["/usr/local/bin/postgres_exporter"]
