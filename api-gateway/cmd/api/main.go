package main

import (
	"api-gateway/internal/config"
	"api-gateway/internal/grpc_client"
	"api-gateway/internal/handler"
	"fmt"
	"log"

	"github.com/gin-gonic/gin"
)

func main() {
	cfg, err := config.LoadConfig()
	if err != nil {
		log.Fatalf("So'zlamalarni yuklashda xatolik: %v", err)
	}
	if cfg.PaymePassword == "" {
		log.Fatalf("DIQQAT: PAYME_PASSWORD muhit o'zgaruvchisi .env faylida o'rnatilmagan!")
	}
	if cfg.PaymeLogin == "" {
		log.Fatalf("DIQQAT: PAYME_LOGIN muhit o'zgaruvchisi .env faylida o'rnatilmagan!")
	}

	grpcClient, err := grpc_client.NewGrpcClient(cfg.PaymeServiceAddress)
	if err != nil {
		log.Fatalf("gRPC servislariga ulanishda xatolik: %v", err)
	}

	rpcHandler := handler.NewRPCHandler(grpcClient, cfg) 
	router := gin.New()
	router.Use(gin.Logger(), gin.Recovery())

	router.POST("/rpc", rpcHandler.HandleRequest)

	log.Printf("API Gateway (HTTPS/JSON-RPC) %s portda ishga tushdi...", cfg.AppPort)
	if err := router.RunTLS(fmt.Sprintf(":%s", cfg.AppPort), cfg.CertFilePath, cfg.KeyFilePath); err != nil {
		log.Fatalf("HTTPS serverni ishga tushirishda xatolik: %v", err)
	}
}