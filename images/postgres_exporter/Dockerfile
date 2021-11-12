FROM alpine:3.14.3@sha256:230cdd0ecad7d678b69b033748ac07183a26115ab1050a5d464105eafbe57859 AS extract

ARG TARGETOS
ARG TARGETARCH
ARG version=0.10.0
RUN wget "https://github.com/prometheus-community/postgres_exporter/releases/download/v${version}/postgres_exporter-${version}.${TARGETOS}-${TARGETARCH}.tar.gz" -O /tmp/postgres_exporter.tar.gz \
 && tar -C /usr/local/bin --strip-components 1 -xzf /tmp/postgres_exporter.tar.gz "postgres_exporter-${version}.${TARGETOS}-${TARGETARCH}/postgres_exporter" \
 && rm -f /tmp/postgres_exporter.tar.gz

EXPOSE 9187
USER nobody
ENTRYPOINT ["/usr/local/bin/postgres_exporter"]
