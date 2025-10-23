package repository

import (
	"context"
	"fmt"
	"payme/internal/models"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type TransactionRepository interface {
	GetTransactionByPaymeTxID(ctx context.Context, paymeTxID string) (*models.Transaction, error)
	CreateTransaction(ctx context.Context, tx pgx.Tx, transaction *models.Transaction) (*models.Transaction, error)
	UpdateTransactionState(ctx context.Context, tx pgx.Tx, paymeTxID string, state models.TransactionState, performTime, cancelTime int64, reason *int) (*models.Transaction, error)
	GetTransactionsByTimeRange(ctx context.Context, from, to int64) ([]models.Transaction, error)
}

type pgTransactionRepository struct {
	db *pgxpool.Pool
}

func NewTransactionRepository(db *pgxpool.Pool) TransactionRepository {
	return &pgTransactionRepository{db: db}
}

func (r *pgTransactionRepository) GetTransactionByPaymeTxID(ctx context.Context, paymeTxID string) (*models.Transaction, error) {
	query := `
		SELECT id, payme_tx_id, student_id, amount, create_time, perform_time, cancel_time, state, reason, created_at, updated_at
		FROM transactions
		WHERE payme_tx_id = $1
	`
	var t models.Transaction
	err := r.db.QueryRow(ctx, query, paymeTxID).Scan(
		&t.ID, &t.PaymeTxID, &t.StudentID, &t.Amount, &t.CreateTime, &t.PerformTime,
		&t.CancelTime, &t.State, &t.Reason, &t.CreatedAt, &t.UpdatedAt,
	)

	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("error scanning transaction row: %w", err)
	}
	return &t, nil
}

func (r *pgTransactionRepository) CreateTransaction(ctx context.Context, tx pgx.Tx, t *models.Transaction) (*models.Transaction, error) {
	query := `
		INSERT INTO transactions (payme_tx_id, student_id, amount, create_time, state)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id, created_at, updated_at
	`
	err := tx.QueryRow(ctx, query, t.PaymeTxID, t.StudentID, t.Amount, t.CreateTime, t.State).Scan(&t.ID, &t.CreatedAt, &t.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("error executing insert transaction query: %w", err)
	}
	return t, nil
}

func (r *pgTransactionRepository) UpdateTransactionState(ctx context.Context, tx pgx.Tx, paymeTxID string, state models.TransactionState, performTime, cancelTime int64, reason *int) (*models.Transaction, error) {
	query := `
		UPDATE transactions
		SET state = $2, perform_time = $3, cancel_time = $4, reason = $5, updated_at = NOW()
		WHERE payme_tx_id = $1
		RETURNING id, payme_tx_id, student_id, amount, create_time, perform_time, cancel_time, state, reason, created_at, updated_at
	`
	var updatedTx models.Transaction
	err := tx.QueryRow(ctx, query, paymeTxID, state, performTime, cancelTime, reason).Scan(
		&updatedTx.ID, &updatedTx.PaymeTxID, &updatedTx.StudentID, &updatedTx.Amount, &updatedTx.CreateTime,
		&updatedTx.PerformTime, &updatedTx.CancelTime, &updatedTx.State, &updatedTx.Reason,
		&updatedTx.CreatedAt, &updatedTx.UpdatedAt,
	)

	if err != nil {
		return nil, fmt.Errorf("error updating and scanning transaction row: %w", err)
	}
	return &updatedTx, nil
}

func (r *pgTransactionRepository) GetTransactionsByTimeRange(ctx context.Context, from, to int64) ([]models.Transaction, error) {
	query := `
		SELECT id, payme_tx_id, student_id, amount, create_time, perform_time, cancel_time, state, reason
		FROM transactions
		WHERE create_time >= $1 AND create_time <= $2
		ORDER BY create_time ASC
	`
	rows, err := r.db.Query(ctx, query, from, to)
	if err != nil {
		return nil, fmt.Errorf("error querying for transactions by time range: %w", err)
	}
	defer rows.Close()

	var transactions []models.Transaction
	for rows.Next() {
		var t models.Transaction
		
		if err := rows.Scan(&t.ID, &t.PaymeTxID, &t.StudentID, &t.Amount, &t.CreateTime, &t.PerformTime, &t.CancelTime, &t.State, &t.Reason); err != nil {
			return nil, fmt.Errorf("error scanning transaction row in time range: %w", err)
		}
		transactions = append(transactions, t)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error after iterating over transaction rows: %w", err)
	}

	return transactions, nil
}