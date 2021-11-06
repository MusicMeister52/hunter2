FROM oliver006/redis_exporter:v1.30.0-alpine@sha256:65d43b66bee76200c2328bed6b6cb8ebcc20404418b17230180357dcc812bd9c AS target-amd64

FROM oliver006/redis_exporter:v1.30.0-arm64@sha256:2ce9a91ef80a7991f6530b73ab500660073be8f6e75c01b29495184b78f1b7f8 AS target-arm64

FROM target-$TARGETARCH
