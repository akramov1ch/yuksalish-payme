package service

import (
	"context"
	"fmt"
	"log"
	"math/rand"
	"strings"
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
	UpdateStudentsBatch(ctx context.Context, students []*models.Student) error
	DeleteStudentsBatch(ctx context.Context, accountIDs []string) error
}

type managementService struct {
	db          *pgxpool.Pool
	branchRepo  repository.BranchRepository
	studentRepo repository.StudentRepository
}

func NewManagementService(db *pgxpool.Pool, branchRepo repository.BranchRepository, studentRepo repository.StudentRepository) ManagementService {
	rand.New(rand.NewSource(time.Now().UnixNano()))
	return &managementService{
		db:          db,
		branchRepo:  branchRepo,
		studentRepo: studentRepo,
	}
}

// --- Yordamchi funksiya ---
func normalizeString(s *string) string {
	if s == nil {
		return ""
	}
	return strings.ToLower(strings.ReplaceAll(*s, " ", ""))
}

// --- Branch Methods ---
func (s *managementService) CreateBranch(ctx context.Context, branch *models.Branch) (*models.Branch, error) {
	return s.branchRepo.Create(ctx, branch)
}
func (s *managementService) GetBranch(ctx context.Context, id string) (*models.Branch, error) {
	uid, err := uuid.Parse(id)
	if err != nil { return nil, err }
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
	if err != nil { return err }
	return s.branchRepo.Delete(ctx, uid)
}

// --- Student Methods ---
func (s *managementService) CreateStudent(ctx context.Context, student *models.Student) (*models.Student, error) {
	if student.AccountID == nil || *student.AccountID == "" {
		for {
			newID := fmt.Sprintf("YM%05d", rand.Intn(100000))
			existingStudent, err := s.studentRepo.GetByAccountID(ctx, newID)
			if err != nil { return nil, fmt.Errorf("ID check error: %w", err) }
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
	log.Printf("INFO: CreateStudentsBatch chaqirildi. Jami kelganlar: %d", len(students))

	if len(students) == 0 {
		return []*models.Student{}, nil
	}

	var finalResult []*models.Student
	var studentsToInsert []*models.Student
	var accountIDsToFetch []string
	
	// Batch ichida dublikatlarni oldini olish uchun map
	processedIDsInBatch := make(map[string]bool)

	for i, student := range students {
		// 1. Agar Account ID berilgan bo'lsa (Sheetdan kelgan bo'lsa)
		if student.AccountID != nil && *student.AccountID != "" {
			providedID := *student.AccountID

			// A) Batch ichida bu ID oldin kelganmi?
			if processedIDsInBatch[providedID] {
				log.Printf("OGOHLANTIRISH [%d]: ID '%s' batch ichida takrorlandi. O'tkazib yuboriladi.", i, providedID)
				continue
			}

			// B) Bazada borligini tekshiramiz
			existingStudent, err := s.studentRepo.GetByAccountID(ctx, providedID)
			if err != nil {
				return nil, fmt.Errorf("ID tekshirishda xatolik: %w", err)
			}

			if existingStudent != nil {
				// HOLAT: Account ID bazada BOR.
				log.Printf("INFO [%d]: ID '%s' bazada mavjud. O'sha o'quvchi qaytariladi.", i, providedID)
				finalResult = append(finalResult, existingStudent)
				processedIDsInBatch[providedID] = true
			} else {
				// HOLAT: Account ID bazada YO'Q.
				log.Printf("INFO [%d]: ID '%s' bazada yo'q. Shu ID bilan yaratiladi.", i, providedID)
				
				studentsToInsert = append(studentsToInsert, student)
				accountIDsToFetch = append(accountIDsToFetch, providedID)
				processedIDsInBatch[providedID] = true
			}
		} else {
			// HOLAT: Account ID umuman berilmagan (bo'sh).
			var idToUse string
			for {
				newID := fmt.Sprintf("YM%05d", rand.Intn(100000))
				
				// Bazani tekshiramiz
				existing, _ := s.studentRepo.GetByAccountID(ctx, newID)
				
				// Batchni ham tekshiramiz
				if existing == nil && !processedIDsInBatch[newID] {
					idToUse = newID
					break
				}
			}
			student.AccountID = &idToUse
			studentsToInsert = append(studentsToInsert, student)
			accountIDsToFetch = append(accountIDsToFetch, idToUse)
			processedIDsInBatch[idToUse] = true
		}
	}

	// Endi faqat yangilarini (yoki ID si yo'qlarni) bazaga yozamiz
	if len(studentsToInsert) > 0 {
		tx, err := s.db.Begin(ctx)
		if err != nil {
			return nil, fmt.Errorf("tranzaksiyani boshlashda xatolik: %w", err)
		}
		defer tx.Rollback(ctx)

		log.Printf("INFO: %d ta yangi o'quvchi bazaga yozilmoqda...", len(studentsToInsert))
		_, err = s.studentRepo.CreateStudentsBatch(ctx, tx, studentsToInsert)
		if err != nil {
			return nil, fmt.Errorf("ommaviy yozishda xatolik: %w", err)
		}

		if err := tx.Commit(ctx); err != nil {
			return nil, fmt.Errorf("commit xatoligi: %w", err)
		}

		// Yozilganlarni qayta o'qib olamiz (UUID lari bilan birga)
		createdStudents, err := s.studentRepo.GetStudentsByAccountIDs(ctx, accountIDsToFetch)
		if err != nil {
			return nil, fmt.Errorf("yaratilganlarni o'qishda xatolik: %w", err)
		}
		
		finalResult = append(finalResult, createdStudents...)
	}

	return finalResult, nil
}

func (s *managementService) UpdateStudentsBatch(ctx context.Context, students []*models.Student) error {
	if len(students) == 0 {
		return nil
	}
	tx, err := s.db.Begin(ctx)
	if err != nil {
		return fmt.Errorf("tranzaksiyani boshlashda xatolik: %w", err)
	}
	defer tx.Rollback(ctx)

	if err := s.studentRepo.UpdateStudentsBatch(ctx, tx, students); err != nil {
		return err
	}

	return tx.Commit(ctx)
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