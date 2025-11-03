package repository

import (
	"context"
	"fmt"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"payme/internal/models"
)

type BranchRepository interface {
	Create(ctx context.Context, branch *models.Branch) (*models.Branch, error)
	GetByID(ctx context.Context, id uuid.UUID) (*models.Branch, error)
	GetAll(ctx context.Context) ([]models.Branch, error)
	Update(ctx context.Context, branch *models.Branch) (*models.Branch, error)
	Delete(ctx context.Context, id uuid.UUID) error
}

type pgBranchRepository struct {
	db *pgxpool.Pool
}

func NewBranchRepository(db *pgxpool.Pool) BranchRepository {
	return &pgBranchRepository{db: db}
}

func (r *pgBranchRepository) Create(ctx context.Context, b *models.Branch) (*models.Branch, error) {
	query := `INSERT INTO branches (name, monthly_fee, mfo_code, account_number, merchant_id)
			  VALUES ($1, $2, $3, $4, $5) RETURNING id, created_at`
	err := r.db.QueryRow(ctx, query, b.Name, b.MonthlyFee, b.MfoCode, b.AccountNumber, b.MerchantID).Scan(&b.ID, &b.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("error creating branch: %w", err)
	}
	return b, nil
}

func (r *pgBranchRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.Branch, error) {
	query := `SELECT id, name, monthly_fee, mfo_code, account_number, merchant_id, created_at FROM branches WHERE id = $1`
	var b models.Branch
	err := r.db.QueryRow(ctx, query, id).Scan(&b.ID, &b.Name, &b.MonthlyFee, &b.MfoCode, &b.AccountNumber, &b.MerchantID, &b.CreatedAt)
	if err != nil {
		if err == pgx.ErrNoRows { return nil, nil }
		return nil, fmt.Errorf("error getting branch by id: %w", err)
	}
	return &b, nil
}

func (r *pgBranchRepository) GetAll(ctx context.Context) ([]models.Branch, error) {
	query := `SELECT id, name, monthly_fee, mfo_code, account_number, merchant_id, created_at FROM branches`
	rows, err := r.db.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("error getting all branches: %w", err)
	}
	defer rows.Close()
	var branches []models.Branch
	for rows.Next() {
		var b models.Branch
		err := rows.Scan(&b.ID, &b.Name, &b.MonthlyFee, &b.MfoCode, &b.AccountNumber, &b.MerchantID, &b.CreatedAt)
		if err != nil {
			return nil, fmt.Errorf("error scanning branch row: %w", err)
		}
		branches = append(branches, b)
	}
	return branches, nil
}

func (r *pgBranchRepository) Update(ctx context.Context, b *models.Branch) (*models.Branch, error) {
	query := `UPDATE branches SET name = $1, monthly_fee = $2, mfo_code = $3, account_number = $4, merchant_id = $5
			  WHERE id = $6 RETURNING id, name, monthly_fee, mfo_code, account_number, merchant_id, created_at`
	err := r.db.QueryRow(ctx, query, b.Name, b.MonthlyFee, b.MfoCode, b.AccountNumber, b.MerchantID, b.ID).Scan(
		&b.ID, &b.Name, &b.MonthlyFee, &b.MfoCode, &b.AccountNumber, &b.MerchantID, &b.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("error updating branch: %w", err)
	}
	return b, nil
}

func (r *pgBranchRepository) Delete(ctx context.Context, id uuid.UUID) error {
	query := `DELETE FROM branches WHERE id = $1`
	cmdTag, err := r.db.Exec(ctx, query, id)
	if err != nil {
		return fmt.Errorf("error deleting branch: %w", err)
	}
	if cmdTag.RowsAffected() != 1 {
		return fmt.Errorf("no rows found to delete")
	}
	return nil
}