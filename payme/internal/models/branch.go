package models

import (
	"time"
	"github.com/google/uuid"
)

type Branch struct {
	ID            uuid.UUID `json:"id" db:"id"`
	Name          string    `json:"name" db:"name"`
	MonthlyFee    int64     `json:"monthly_fee" db:"monthly_fee"`
	MfoCode       string    `json:"mfo_code" db:"mfo_code"`
	AccountNumber string    `json:"account_number" db:"account_number"`
	MerchantID    *string   `json:"merchant_id" db:"merchant_id"`
	TopicID       int64     `json:"topic_id" db:"topic_id"` // YANGI QO'SHILDI
	CreatedAt     time.Time `json:"created_at" db:"created_at"`
}