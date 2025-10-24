package main

import (
	"fmt"
	"log"
	"net"
	"os"

	"payme/genproto/payment"
	"payme/internal/config"
	"payme/internal/grpc_server"
	"payme/internal/repository"
	"payme/internal/service"
	"payme/pkg/db"

	"google.golang.org/grpc"
)

func main() {
	cfg, err := config.LoadConfig()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	botServiceAddr := os.Getenv("BOT_GRPC_SERVICE_ADDR")
	if botServiceAddr == "" {
		log.Fatalf("BOT_GRPC_SERVICE_ADDR muhit o'zgaruvchisi o'rnatilmagan")
	}

	dbPool, err := db.NewPostgresDB(cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer dbPool.Close()

	studentRepo := repository.NewStudentRepository(dbPool)
	paymentRepo := repository.NewPaymentRepository(dbPool)
	txRepo := repository.NewTransactionRepository(dbPool)
	branchRepo := repository.NewBranchRepository(dbPool)

	paymentService := service.NewPaymentService(dbPool, studentRepo, txRepo, paymentRepo, botServiceAddr)
	
	managementService := service.NewManagementService(dbPool, branchRepo, studentRepo)

	grpcServer := grpc_server.NewGRPCServer(paymentService, managementService)

	lis, err := net.Listen("tcp", fmt.Sprintf(":%s", cfg.AppPort))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	s := grpc.NewServer()
	payment.RegisterPaymentServiceServer(s, grpcServer)
	payment.RegisterManagementServiceServer(s, grpcServer)

	log.Printf("gRPC server %v manzilida ishga tushdi...", lis.Addr())
	if err := s.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}