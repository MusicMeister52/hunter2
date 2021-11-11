FROM oliver006/redis_exporter:v1.31.1-alpine@sha256:d7e25dfb6476c03d8e549af7880ae44f3f3e33e2e4853ac3063da96fd7590d22 AS target-amd64

FROM oliver006/redis_exporter:v1.31.1-arm64@sha256:7b3d9f9772bf859eefb2cb2c735ca10107440f6ebff6ba169b38bc2f94a59248 AS target-arm64

FROM target-$TARGETARCH
