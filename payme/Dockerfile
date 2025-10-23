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

RUN mkdir -p genproto/bot_admin && \
    protoc --proto_path=protos \
    --go_out=./genproto/bot_admin --go_opt=paths=source_relative \
    --go-grpc_out=./genproto/bot_admin --go-grpc_opt=paths=source_relative \
    protos/bot_admin.proto

RUN cd genproto && go mod init genproto

ENV GOPROXY=direct
RUN go mod tidy
RUN go mod download
RUN go build -ldflags="-w -s" -o /bin/payme ./cmd/api

FROM alpine:latest

RUN apk update && apk add --no-cache ca-certificates curl && \
    curl -L https://github.com/golang-migrate/migrate/releases/download/v4.17.1/migrate.linux-amd64.tar.gz | tar xvz && \
    mv migrate /usr/local/bin/migrate

WORKDIR /app

COPY --from=builder /bin/payme .
COPY .env .
COPY ./migrations ./migrations
COPY ./start.sh .

RUN chmod +x ./start.sh

EXPOSE 9000

CMD ["./start.sh"]