package models

import (
	"time"
	"github.com/google/uuid"
)

type Student struct {
	ID              uuid.UUID `json:"id" db:"id"`
	AccountID       *string   `json:"account_id" db:"account_id"`
	BranchID        uuid.UUID `json:"branch_id" db:"branch_id"`
	ParentName      string    `json:"parent_name" db:"parent_name"`
	DiscountPercent float64   `json:"discount_percent" db:"discount_percent"`
	Balance         int64     `json:"balance" db:"balance"`
	FullName        *string   `json:"full_name" db:"full_name"`
	GroupName       *string   `json:"group_name" db:"group_name"`
	Phone           *string   `json:"phone" db:"phone"`
	ContractNumber  *string   `json:"contract_number" db:"contract_number"`
	Status          bool      `json:"status" db:"status"` // YANGI QO'SHILDI
	CreatedAt       time.Time `json:"created_at" db:"created_at"`
	UpdatedAt       time.Time `json:"updated_at" db:"updated_at"`
}