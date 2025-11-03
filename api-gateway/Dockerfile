FROM golang:1.25-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./

RUN go mod vendor

COPY . .

RUN go build -mod=vendor -ldflags="-w -s" -o /bin/api-gateway ./cmd/api


FROM alpine:latest

RUN apk update && apk add --no-cache ca-certificates

WORKDIR /app

COPY --from=builder /bin/api-gateway .
COPY .env .
COPY cert.pem .
COPY key.pem .

EXPOSE 8443

ENTRYPOINT ["./api-gateway"]