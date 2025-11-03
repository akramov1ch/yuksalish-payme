package config

import (
	"fmt"
	"os"

	"github.com/joho/godotenv"
)

type Config struct {
	AppPort      string
	DatabaseURL  string
}

func LoadConfig() (*Config, error) {
	_ = godotenv.Load()

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		return nil, fmt.Errorf("DATABASE_URL environment variable is not set")
	}

	appPort := os.Getenv("APP_PORT")
	if appPort == "" {
		appPort = "443"
	}

	return &Config{
		AppPort:      appPort,
		DatabaseURL:  dbURL,
	}, nil
}