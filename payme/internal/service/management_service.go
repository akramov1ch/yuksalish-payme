package service

import (
	"context"
	"fmt"
	"math/rand"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"payme/internal/models"
	"payme/internal/repository"
)

type ManagementService interface {
	CreateBranch(ctx context.Context, branch *models.Branch) (*models.Branch, error)
	GetBranch(ctx context.Context, id string) (*models.Branch, error)
	ListBranches(ctx context.Context) ([]models.Branch, error)
	UpdateBranch(ctx context.Context, branch *models.Branch) (*models.Branch, error)
	DeleteBranch(ctx context.Context, id string) error

	CreateStudent(ctx context.Context, student *models.Student) (*models.Student, error)
	GetStudentByAccountId(ctx context.Context, accountId string) (*models.Student, error)
	ListStudents(ctx context.Context) ([]models.Student, error)
	UpdateStudent(ctx context.Context, student *models.Student) (*models.Student, error)
	DeleteStudentByAccountId(ctx context.Context, accountId string) error

	CreateStudentsBatch(ctx context.Context, students []*models.Student) ([]*models.Student, error)
	DeleteStudentsBatch(ctx context.Context, accountIDs []string) error
}

type managementService struct {
	db          *pgxpool.Pool 
	branchRepo  repository.BranchRepository
	studentRepo repository.StudentRepository
}

func NewManagementService(db *pgxpool.Pool, branchRepo repository.BranchRepository, studentRepo repository.StudentRepository) ManagementService {
	return &managementService{
		db:          db,
		branchRepo:  branchRepo,
		studentRepo: studentRepo,
	}
}

func (s *managementService) CreateBranch(ctx context.Context, branch *models.Branch) (*models.Branch, error) {
	return s.branchRepo.Create(ctx, branch)
}

func (s *managementService) GetBranch(ctx context.Context, id string) (*models.Branch, error) {
	uid, err := uuid.Parse(id)
	if err != nil {
		return nil, err
	}
	return s.branchRepo.GetByID(ctx, uid)
}

func (s *managementService) ListBranches(ctx context.Context) ([]models.Branch, error) {
	return s.branchRepo.GetAll(ctx)
}

func (s *managementService) UpdateBranch(ctx context.Context, branch *models.Branch) (*models.Branch, error) {
	return s.branchRepo.Update(ctx, branch)
}

func (s *managementService) DeleteBranch(ctx context.Context, id string) error {
	uid, err := uuid.Parse(id)
	if err != nil {
		return err
	}
	return s.branchRepo.Delete(ctx, uid)
}

func (s *managementService) CreateStudent(ctx context.Context, student *models.Student) (*models.Student, error) {
	if student.AccountID == nil || *student.AccountID == "" {
		for {
			newID := fmt.Sprintf("YM%06d", rand.New(rand.NewSource(time.Now().UnixNano())).Intn(1000000))
			existingStudent, err := s.studentRepo.GetByAccountID(ctx, newID)
			if err != nil {
				return nil, fmt.Errorf("mavjud account ID'ni tekshirishda xatolik: %w", err)
			}
			if existingStudent == nil {
				student.AccountID = &newID
				break
			}
		}
	}
	return s.studentRepo.Create(ctx, student)
}

func (s *managementService) GetStudentByAccountId(ctx context.Context, accountId string) (*models.Student, error) {
	return s.studentRepo.GetByAccountID(ctx, accountId)
}

func (s *managementService) ListStudents(ctx context.Context) ([]models.Student, error) {
	return s.studentRepo.GetAll(ctx)
}

func (s *managementService) UpdateStudent(ctx context.Context, student *models.Student) (*models.Student, error) {
	return s.studentRepo.Update(ctx, student)
}

func (s *managementService) DeleteStudentByAccountId(ctx context.Context, accountId string) error {
	return s.studentRepo.DeleteByAccountID(ctx, accountId)
}

func (s *managementService) CreateStudentsBatch(ctx context.Context, students []*models.Student) ([]*models.Student, error) {
	for _, student := range students {
		if student.AccountID == nil || *student.AccountID == "" {
			for {
				newID := fmt.Sprintf("YM%06d", rand.New(rand.NewSource(time.Now().UnixNano())).Intn(1000000))

				existingStudent, err := s.studentRepo.GetByAccountID(ctx, newID)
				if err != nil {
					return nil, fmt.Errorf("mavjud account ID'ni tekshirishda xatolik: %w", err)
				}
				if existingStudent == nil {
					student.AccountID = &newID
					break 
				}
			}
		}
	}

	tx, err := s.db.Begin(ctx)
	if err != nil {
		return nil, fmt.Errorf("tranzaksiyani boshlashda xatolik: %w", err)
	}
	defer tx.Rollback(ctx) 
	_, err = s.studentRepo.CreateStudentsBatch(ctx, tx, students)
	if err != nil {
		return nil, err 
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, fmt.Errorf("tranzaksiyani tasdiqlashda xatolik: %w", err)
	}

	return students, nil
}

func (s *managementService) DeleteStudentsBatch(ctx context.Context, accountIDs []string) error {
	if len(accountIDs) == 0 {
		return nil
	}

	tx, err := s.db.Begin(ctx)
	if err != nil {
		return fmt.Errorf("tranzaksiyani boshlashda xatolik: %w", err)
	}
	defer tx.Rollback(ctx)

	_, err = s.studentRepo.DeleteStudentsByAccountIDs(ctx, tx, accountIDs)
	if err != nil {
		return err
	}

	return tx.Commit(ctx)
}