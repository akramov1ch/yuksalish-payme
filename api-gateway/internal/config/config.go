package config

import (
	"os"
	"github.com/joho/godotenv"
)

type Config struct {
	AppPort             string
	PaymeServiceAddress string
	CertFilePath        string
	KeyFilePath         string
	PaymeLogin          string
	PaymePassword       string
}

func LoadConfig() (*Config, error) {
	if err := godotenv.Load(); err != nil {
	}
	
	return &Config{
		AppPort:             getEnv("API_GATEWAY_PORT", "8443"),
		PaymeServiceAddress: getEnv("PAYME_GRPC_SERVICE_ADDR", "localhost:9000"),
		CertFilePath:        getEnv("CERT_FILE_PATH", "cert.pem"),
		KeyFilePath:         getEnv("KEY_FILE_PATH", "key.pem"),
		PaymeLogin:          getEnv("PAYME_LOGIN", ""),
		PaymePassword:       getEnv("PAYME_PASSWORD", ""),
	}, nil
}

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}