FROM golang:1.25-alpine AS builder

RUN sed -i 's/dl-cdn.alpinelinux.org/mirror.leaseweb.com/g' /etc/apk/repositories

RUN apk update && apk add --no-cache git protobuf-dev build-base

RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.32
RUN go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.3

WORKDIR /app

COPY . .

RUN mkdir -p genproto/payment && \
    protoc --proto_path=protos \
    --go_out=./genproto/payment --go_opt=paths=source_relative \
    --go-grpc_out=./genproto/payment --go-grpc_opt=paths=source_relative \
    protos/payment.proto

RUN cd genproto && go mod init genproto

ENV GOPROXY=direct

RUN go mod tidy
RUN go mod download

RUN go build -ldflags="-w -s" -o /bin/api-gateway ./cmd/api

FROM alpine:latest

RUN apk update && apk add --no-cache ca-certificates

WORKDIR /app

COPY --from=builder /bin/api-gateway .
COPY .env .
COPY cert.pem .
COPY key.pem .

EXPOSE 8443

ENTRYPOINT ["./api-gateway"]