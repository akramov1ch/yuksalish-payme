package models

import (
	"time"

	"github.com/google/uuid"
)

type Payment struct {
	ID              uuid.UUID `json:"id" db:"id"`
	StudentID       uuid.UUID `json:"student_id" db:"student_id"`
	Month           time.Time `json:"month" db:"month"`
	AmountPaid      int64     `json:"amount_paid" db:"amount_paid"`
	DiscountApplied int64     `json:"discount_applied" db:"discount_applied"`
	PaidAt          time.Time `json:"paid_at" db:"paid_at"`
	CreatedAt       time.Time `json:"created_at" db:"created_at"`
	UpdatedAt       time.Time `json:"updated_at" db:"updated_at"`
}