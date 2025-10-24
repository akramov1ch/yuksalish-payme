package grpc_client

import (
	"api-gateway/genproto/payment"
	"log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type GrpcClient struct {
	PaymentServiceClient payment.PaymentServiceClient
}

func NewGrpcClient(paymeAddr string) (*GrpcClient, error) {
	connPayme, err := grpc.NewClient(paymeAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Printf("payme servisiga ulanishda xatolik: %v", err)
		return nil, err
	}

	return &GrpcClient{
		PaymentServiceClient: payment.NewPaymentServiceClient(connPayme),
	}, nil
}