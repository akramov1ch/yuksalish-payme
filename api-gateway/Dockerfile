# 1-BOSQICH: Build qilish uchun muhit
FROM golang:1.25-alpine AS builder

WORKDIR /app

# Bog'liqlik fayllarini nusxalash
COPY go.mod go.sum ./

# Vendor papkasini Docker ichida yaratish. Bu har doim to'g'ri ishlashini ta'minlaydi.
RUN go mod vendor

# Qolgan barcha kodlarni nusxalash
COPY . .

# Build qilishda -mod=vendor flag'idan foydalanamiz
RUN go build -mod=vendor -ldflags="-w -s" -o /bin/api-gateway ./cmd/api


# 2-BOSQICH: Yakuniy image'ni yaratish
FROM alpine:latest

RUN apk update && apk add --no-cache ca-certificates

WORKDIR /app

# Build qilingan dasturni va faqat kerakli fayllarni nusxalash
COPY --from=builder /bin/api-gateway .
COPY .env .
COPY cert.pem .
COPY key.pem .

EXPOSE 8443

ENTRYPOINT ["./api-gateway"]