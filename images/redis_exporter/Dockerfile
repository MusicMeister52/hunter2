FROM oliver006/redis_exporter:v1.31.0-alpine@sha256:963ecce3d3a41634d792423a930b419d896ad841fe1c1d6867e6e0e37b92fd08 AS target-amd64

FROM oliver006/redis_exporter:v1.31.0-arm64@sha256:ea35342af7ca14a7d23e3f1199b30677065591566939e588bda6ee6b3ca2e7da AS target-arm64

FROM target-$TARGETARCH
