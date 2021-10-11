FROM oliver006/redis_exporter:v1.27.1-alpine@sha256:d08cab6d85799455e29e9ad5af101ffc8389e94c26efc36d6e0ffc773f7751fc AS target-amd64

FROM oliver006/redis_exporter:v1.27.1-arm64@sha256:388a4bef6466c9b89dddc0f97d2f5888d286f68350e4c5996f6ac73e4a7ac79a AS target-arm64

FROM target-$TARGETARCH
