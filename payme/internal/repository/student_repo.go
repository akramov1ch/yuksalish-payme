package repository

import (
	"context"
	"fmt"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"payme/internal/models"
)

// O'ZGARTIRILDI: Interfeysga yangi metod qo'shildi
type StudentRepository interface {
	GetStudentAndBranchByAccountID(ctx context.Context, accountID string) (*models.Student, *models.Branch, error)
	UpdateStudentBalance(ctx context.Context, tx pgx.Tx, id uuid.UUID, newBalance int64) error
	GetStudentByID(ctx context.Context, id uuid.UUID) (*models.Student, error)
	GetStudentAndBranchByStudentID(ctx context.Context, studentID uuid.UUID) (*models.Student, *models.Branch, error)
	Create(ctx context.Context, student *models.Student) (*models.Student, error)
	GetByAccountID(ctx context.Context, accountID string) (*models.Student, error)
	GetAll(ctx context.Context) ([]models.Student, error)
	Update(ctx context.Context, student *models.Student) (*models.Student, error)
	DeleteByAccountID(ctx context.Context, accountID string) error
	CreateStudentsBatch(ctx context.Context, tx pgx.Tx, students []*models.Student) (int64, error)
	DeleteStudentsByAccountIDs(ctx context.Context, tx pgx.Tx, accountIDs []string) (int64, error)
	GetStudentsByAccountIDs(ctx context.Context, tx pgx.Tx, accountIDs []string) ([]*models.Student, error) // YANGI METOD
}

type pgStudentRepository struct {
	db *pgxpool.Pool
}

func NewStudentRepository(db *pgxpool.Pool) StudentRepository {
	return &pgStudentRepository{db: db}
}

// YANGI FUNKSIYA QO'SHILDI
func (r *pgStudentRepository) GetStudentsByAccountIDs(ctx context.Context, tx pgx.Tx, accountIDs []string) ([]*models.Student, error) {
	query := `SELECT id, account_id, branch_id, parent_name, discount_percent, balance, full_name, group_name, phone, contract_number, status, created_at, updated_at 
			  FROM students 
			  WHERE account_id = ANY($1)`
	
	var rows pgx.Rows
	var err error

	// Agar tranzaksiya mavjud bo'lsa, tranzaksiya orqali so'rov yuboramiz
	if tx != nil {
		rows, err = tx.Query(ctx, query, accountIDs)
	} else {
		rows, err = r.db.Query(ctx, query, accountIDs)
	}

	if err != nil {
		return nil, fmt.Errorf("error querying students by account ids: %w", err)
	}
	defer rows.Close()

	var students []*models.Student
	for rows.Next() {
		var s models.Student
		err := rows.Scan(
			&s.ID, &s.AccountID, &s.BranchID, &s.ParentName, &s.DiscountPercent,
			&s.Balance, &s.FullName, &s.GroupName, &s.Phone, &s.ContractNumber, &s.Status, &s.CreatedAt, &s.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("error scanning student row by account_ids: %w", err)
		}
		students = append(students, &s)
	}
	return students, nil
}


func (r *pgStudentRepository) CreateStudentsBatch(ctx context.Context, tx pgx.Tx, students []*models.Student) (int64, error) {
	if len(students) == 0 {
		return 0, nil
	}

	rows := make([][]interface{}, len(students))
	for i, s := range students {
		rows[i] = []interface{}{
			s.AccountID, s.BranchID, s.ParentName, s.DiscountPercent,
			s.FullName, s.GroupName, s.Phone, s.ContractNumber,
		}
	}

	columnNames := []string{
		"account_id", "branch_id", "parent_name", "discount_percent",
		"full_name", "group_name", "phone", "contract_number",
	}

	copyCount, err := tx.CopyFrom(
		ctx,
		pgx.Identifier{"students"},
		columnNames,
		pgx.CopyFromRows(rows),
	)

	if err != nil {
		return 0, fmt.Errorf("ommaviy o'quvchi qo'shishda xatolik: %w", err)
	}

	return copyCount, nil
}

func (r *pgStudentRepository) DeleteStudentsByAccountIDs(ctx context.Context, tx pgx.Tx, accountIDs []string) (int64, error) {
	if len(accountIDs) == 0 {
		return 0, nil
	}

	query := `DELETE FROM students WHERE account_id = ANY($1)`

	cmdTag, err := tx.Exec(ctx, query, accountIDs)
	if err != nil {
		return 0, fmt.Errorf("ommaviy o'quvchi o'chirishda xatolik: %w", err)
	}

	return cmdTag.RowsAffected(), nil
}

func (r *pgStudentRepository) Create(ctx context.Context, s *models.Student) (*models.Student, error) {
	query := `INSERT INTO students (account_id, branch_id, parent_name, discount_percent, full_name, group_name, phone, contract_number)
			  VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id, balance, status, created_at, updated_at`
	err := r.db.QueryRow(ctx, query, s.AccountID, s.BranchID, s.ParentName, s.DiscountPercent, s.FullName, s.GroupName, s.Phone, s.ContractNumber).Scan(
		&s.ID, &s.Balance, &s.Status, &s.CreatedAt, &s.UpdatedAt)
	if err != nil {
		return nil, fmt.Errorf("error creating student: %w", err)
	}
	return s, nil
}

func (r *pgStudentRepository) GetByAccountID(ctx context.Context, accountID string) (*models.Student, error) {
	query := `SELECT id, account_id, branch_id, parent_name, discount_percent, balance, full_name, group_name, phone, contract_number, status, created_at, updated_at FROM students WHERE account_id = $1`
	var student models.Student
	err := r.db.QueryRow(ctx, query, accountID).Scan(
		&student.ID, &student.AccountID, &student.BranchID, &student.ParentName, &student.DiscountPercent,
		&student.Balance, &student.FullName, &student.GroupName, &student.Phone, &student.ContractNumber, &student.Status, &student.CreatedAt, &student.UpdatedAt,
	)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("error scanning student row by account_id: %w", err)
	}
	return &student, nil
}

func (r *pgStudentRepository) GetAll(ctx context.Context) ([]models.Student, error) {
	query := `SELECT id, account_id, branch_id, parent_name, discount_percent, balance, full_name, group_name, phone, contract_number, status, created_at, updated_at FROM students`
	rows, err := r.db.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("error getting all students: %w", err)
	}
	defer rows.Close()

	var students []models.Student
	for rows.Next() {
		var s models.Student
		err := rows.Scan(&s.ID, &s.AccountID, &s.BranchID, &s.ParentName, &s.DiscountPercent, &s.Balance, &s.FullName, &s.GroupName, &s.Phone, &s.ContractNumber, &s.Status, &s.CreatedAt, &s.UpdatedAt)
		if err != nil {
			return nil, fmt.Errorf("error scanning student row: %w", err)
		}
		students = append(students, s)
	}
	return students, nil
}

func (r *pgStudentRepository) Update(ctx context.Context, s *models.Student) (*models.Student, error) {
	query := `UPDATE students SET branch_id = $1, parent_name = $2, discount_percent = $3, full_name = $4, group_name = $5, phone = $6, contract_number = $7, status = $8, updated_at = NOW()
			  WHERE account_id = $9 RETURNING id, account_id, branch_id, parent_name, discount_percent, balance, full_name, group_name, phone, contract_number, status, created_at, updated_at`
	err := r.db.QueryRow(ctx, query, s.BranchID, s.ParentName, s.DiscountPercent, s.FullName, s.GroupName, s.Phone, s.ContractNumber, s.Status, s.AccountID).Scan(
		&s.ID, &s.AccountID, &s.BranchID, &s.ParentName, &s.DiscountPercent, &s.Balance, &s.FullName, &s.GroupName, &s.Phone, &s.ContractNumber, &s.Status, &s.CreatedAt, &s.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("error updating student: %w", err)
	}
	return s, nil
}

func (r *pgStudentRepository) DeleteByAccountID(ctx context.Context, accountID string) error {
	query := `DELETE FROM students WHERE account_id = $1`
	cmdTag, err := r.db.Exec(ctx, query, accountID)
	if err != nil {
		return fmt.Errorf("error deleting student by account_id: %w", err)
	}
	if cmdTag.RowsAffected() != 1 {
		return fmt.Errorf("no student found to delete with account_id: %s", accountID)
	}
	return nil
}

func (r *pgStudentRepository) GetStudentByID(ctx context.Context, id uuid.UUID) (*models.Student, error) {
	query := `SELECT id, account_id, branch_id, parent_name, discount_percent, balance, full_name, group_name, phone, contract_number, status, created_at, updated_at 
			  FROM students 
			  WHERE id = $1`
	var student models.Student
	err := r.db.QueryRow(ctx, query, id).Scan(
		&student.ID, &student.AccountID, &student.BranchID, &student.ParentName, &student.DiscountPercent,
		&student.Balance, &student.FullName, &student.GroupName, &student.Phone, &student.ContractNumber, &student.Status, &student.CreatedAt, &student.UpdatedAt,
	)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("error scanning student row by id: %w", err)
	}
	return &student, nil
}

func (r *pgStudentRepository) GetStudentAndBranchByAccountID(ctx context.Context, accountID string) (*models.Student, *models.Branch, error) {
	query := `
		SELECT
			s.id, s.account_id, s.branch_id, s.parent_name, s.discount_percent,
			s.balance, s.full_name, s.group_name, s.phone, s.contract_number, s.status, s.created_at, s.updated_at,
			b.id, b.name, b.monthly_fee, b.mfo_code, b.account_number, b.merchant_id
		FROM students s
		JOIN branches b ON s.branch_id = b.id
		WHERE s.account_id = $1
	`
	var student models.Student
	var branch models.Branch
	err := r.db.QueryRow(ctx, query, accountID).Scan(
		&student.ID, &student.AccountID, &student.BranchID, &student.ParentName, &student.DiscountPercent,
		&student.Balance, &student.FullName, &student.GroupName, &student.Phone, &student.ContractNumber, &student.Status, &student.CreatedAt, &student.UpdatedAt,
		&branch.ID, &branch.Name, &branch.MonthlyFee, &branch.MfoCode, &branch.AccountNumber, &branch.MerchantID,
	)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil, nil
		}
		return nil, nil, fmt.Errorf("error scanning student and branch info row: %w", err)
	}
	return &student, &branch, nil
}

func (r *pgStudentRepository) GetStudentAndBranchByStudentID(ctx context.Context, studentID uuid.UUID) (*models.Student, *models.Branch, error) {
	query := `
		SELECT
			s.id, s.account_id, s.branch_id, s.parent_name, s.discount_percent,
			s.balance, s.full_name, s.group_name, s.phone, s.contract_number, s.status, s.created_at, s.updated_at,
			b.id, b.name, b.monthly_fee, b.mfo_code, b.account_number, b.merchant_id
		FROM students s
		JOIN branches b ON s.branch_id = b.id
		WHERE s.id = $1
	`
	var student models.Student
	var branch models.Branch
	err := r.db.QueryRow(ctx, query, studentID).Scan(
		&student.ID, &student.AccountID, &student.BranchID, &student.ParentName, &student.DiscountPercent,
		&student.Balance, &student.FullName, &student.GroupName, &student.Phone, &student.ContractNumber, &student.Status, &student.CreatedAt, &student.UpdatedAt,
		&branch.ID, &branch.Name, &branch.MonthlyFee, &branch.MfoCode, &branch.AccountNumber, &branch.MerchantID,
	)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil, nil
		}
		return nil, nil, fmt.Errorf("error scanning student and branch info row by student id: %w", err)
	}
	return &student, &branch, nil
}

func (r *pgStudentRepository) UpdateStudentBalance(ctx context.Context, tx pgx.Tx, id uuid.UUID, newBalance int64) error {
	query := `UPDATE students SET balance = $1, updated_at = NOW() WHERE id = $2`
	cmdTag, err := tx.Exec(ctx, query, newBalance, id)
	if err != nil {
		return fmt.Errorf("error executing update student balance query: %w", err)
	}
	if cmdTag.RowsAffected() != 1 {
		return fmt.Errorf("expected 1 row to be affected, but got %d", cmdTag.RowsAffected())
	}
	return nil
}