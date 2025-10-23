package repository

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"payme/internal/models"
)

type PaymentRepository interface {
	CreatePayment(ctx context.Context, tx pgx.Tx, payment *models.Payment) error
}

type pgPaymentRepository struct {
	db *pgxpool.Pool
}

func NewPaymentRepository(db *pgxpool.Pool) PaymentRepository {
	return &pgPaymentRepository{db: db}
}

func (r *pgPaymentRepository) CreatePayment(ctx context.Context, tx pgx.Tx, p *models.Payment) error {
	query := `
		INSERT INTO payments (student_id, month, amount_paid, discount_applied, paid_at)
		VALUES ($1, $2, $3, $4, $5)
	`
	_, err := tx.Exec(ctx, query, p.StudentID, p.Month, p.AmountPaid, p.DiscountApplied, p.PaidAt)
	if err != nil {
		return fmt.Errorf("error executing insert payment query: %w", err)
	}
	return nil
}