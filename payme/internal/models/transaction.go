package models

import (
	"time"

	"github.com/google/uuid"
)

type TransactionState int

const (
	StateCancelled TransactionState = -1
	StatePending   TransactionState = 1
	StatePerformed TransactionState = 2
)

type Transaction struct {
	ID          int64          `json:"id" db:"id"` 
	PaymeTxID   string         `json:"payme_tx_id" db:"payme_tx_id"`
	StudentID   uuid.UUID      `json:"student_id" db:"student_id"`
	Amount      int64          `json:"amount" db:"amount"`
	CreateTime  int64          `json:"create_time" db:"create_time"`
	PerformTime int64          `json:"perform_time" db:"perform_time"`
	CancelTime  int64          `json:"cancel_time" db:"cancel_time"`
	State       TransactionState `json:"state" db:"state"`
	Reason      *int           `json:"reason,omitempty" db:"reason"`
	CreatedAt   time.Time      `json:"created_at" db:"created_at"`
	UpdatedAt   time.Time      `json:"updated_at" db:"updated_at"`
}