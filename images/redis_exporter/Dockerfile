FROM oliver006/redis_exporter:v1.28.0-alpine@sha256:46009aca7f6c336c520ff08344e3c28c185bf1118f8749af412f99eb5be10ac6 AS target-amd64

FROM oliver006/redis_exporter:v1.28.0-arm64@sha256:9826c3f1c891e34d3ad8c9059d1ac1740b6a40f3da9ac437b51a494a698717d3 AS target-arm64

FROM target-$TARGETARCH
