# 1-BOSQICH: Build qilish uchun muhit
FROM golang:1.25-alpine AS builder

WORKDIR /app

# Barcha bog'liqlik fayllarini va vendor papkasini nusxalash uchun avval mod fayllarini olamiz
COPY go.mod go.sum ./

# Bog'liqliklarni yuklab olib, vendor papkasini yaratamiz
# (Bu qadam lokalda qilingan bo'lsa ham, Docker ichida ham takrorlash ishonchlilikni oshiradi)
RUN go mod download
RUN go mod vendor

# Loyihaning qolgan barcha kodini, shu jumladan vendor papkasini nusxalash
COPY . .

# Dasturni build qilish. -mod=vendor flagi muhim!
RUN go build -mod=vendor -ldflags="-w -s" -o /bin/payme ./cmd/api


# 2-BOSQICH: Yakuniy image'ni yaratish
FROM alpine:latest

# Kerakli utility'larni o'rnatamiz (migrate uchun)
RUN apk update && apk add --no-cache ca-certificates curl && \
    curl -L https://github.com/golang-migrate/migrate/releases/download/v4.17.1/migrate.linux-amd64.tar.gz | tar xvz && \
    mv migrate /usr/local/bin/migrate

WORKDIR /app

# Build qilingan dasturni va kerakli fayllarni nusxalash
COPY --from=builder /bin/payme .
COPY .env .
COPY ./migrations ./migrations
COPY ./start.sh .

RUN chmod +x ./start.sh

EXPOSE 9000

CMD ["./start.sh"]