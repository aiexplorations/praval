# Test fixture for RELEASE.2024-11-07T00-52-20Z. Official binary images
# are no longer available. Build the verified upstream commit instead.
FROM golang:1.23.4-alpine3.20 AS build
RUN apk add --no-cache git
WORKDIR /src
RUN git init \
    && git remote add origin https://github.com/minio/minio.git \
    && git fetch --depth 1 origin cefc43e4daa4cbb490ef6726ea374e26a93eb85e \
    && git checkout --detach FETCH_HEAD
ENV CGO_ENABLED=0 GOMAXPROCS=2
RUN go build -trimpath -o /minio .

FROM alpine:3.20.3
RUN apk add --no-cache ca-certificates
COPY --from=build /minio /usr/local/bin/minio
ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data"]
