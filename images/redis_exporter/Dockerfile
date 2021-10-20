FROM oliver006/redis_exporter:v1.29.0-alpine@sha256:3dd3f75612f809fee7e4202bd0e20251f3418a3e45a0848be7e491e089c83700 AS target-amd64

FROM oliver006/redis_exporter:v1.29.0-arm64@sha256:dae9240246e0a0fa6e8d8e6f85cdcea677db68db8ba72907c6be66323761b212 AS target-arm64

FROM target-$TARGETARCH
