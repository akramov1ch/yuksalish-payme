package service

import (
	"context"
	"log"
	"payme/genproto/bot_admin"
	"payme/genproto/payment"
	"payme/internal/models"
	"payme/internal/repository"
	"payme/pkg/utils"
	"regexp"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type AccountParams struct {
	ID string `json:"id" validate:"required"`
}

type CheckPerformTransactionParams struct {
	Amount  int64         `json:"amount" validate:"required"`
	Account AccountParams `json:"account" validate:"required"`
}

type CreateTransactionParams struct {
	ID      string        `json:"id" validate:"required"`
	Time    int64         `json:"time" validate:"required"`
	Amount  int64         `json:"amount" validate:"required"`
	Account AccountParams `json:"account" validate:"required"`
}

type TransactionParams struct {
	ID     string `json:"id" validate:"required"`
	Reason *int   `json:"reason,omitempty"`
}

type GetStatementParams struct {
	From int64 `json:"from" validate:"required"`
	To   int64 `json:"to" validate:"required"`
}

type CheckPerformTransactionResponse struct {
	Allow      bool                  `json:"allow"`
	Additional StudentAdditionalInfo `json:"additional"`
}

type StudentAdditionalInfo struct {
	FullName      *string `json:"full_name"`
	ParentName    string  `json:"parent_name"`
	BranchName    string  `json:"branch_name"`
	GroupName     *string `json:"group_name"`
	GroupNumber   string  `json:"group_number"`
	AmountToPay   int64   `json:"amount_to_pay"`
	MfoCode       string  `json:"mfo_code"`
	AccountNumber string  `json:"account_number"`
}

type Receiver struct {
	ID     *string `json:"id"`
	Amount int64   `json:"amount"`
}

type CreateTransactionResponse struct {
	CreateTime  int64       `json:"create_time"`
	Transaction string      `json:"transaction"`
	State       int         `json:"state"`
	Receivers   []*Receiver `json:"receivers"`
}

type PerformTransactionResponse struct {
	Transaction string `json:"transaction"`
	PerformTime int64  `json:"perform_time"`
	State       int    `json:"state"`
}

type CancelTransactionResponse struct {
	Transaction string `json:"transaction"`
	CancelTime  int64  `json:"cancel_time"`
	State       int    `json:"state"`
}

type CheckTransactionResponse struct {
	CreateTime  int64  `json:"create_time"`
	PerformTime int64  `json:"perform_time"`
	CancelTime  int64  `json:"cancel_time"`
	Transaction string `json:"transaction"`
	State       int    `json:"state"`
	Reason      *int   `json:"reason"`
}

type PaymentService interface {
	CheckPerformTransaction(ctx context.Context, params CheckPerformTransactionParams) (*CheckPerformTransactionResponse, error)
	CreateTransaction(ctx context.Context, params CreateTransactionParams) (*CreateTransactionResponse, error)
	PerformTransaction(ctx context.Context, params TransactionParams) (*PerformTransactionResponse, error)
	CancelTransaction(ctx context.Context, params TransactionParams) (*CancelTransactionResponse, error)
	CheckTransaction(ctx context.Context, params TransactionParams) (*CheckTransactionResponse, error)
	GetStatement(ctx context.Context, params *payment.GetStatementRequest) (*payment.GetStatementResponse, error)
}

type paymentService struct {
	db          *pgxpool.Pool
	studentRepo repository.StudentRepository
	txRepo      repository.TransactionRepository
	paymentRepo repository.PaymentRepository
	botClient   bot_admin.BotAdminServiceClient
}

func NewPaymentService(db *pgxpool.Pool, studentRepo repository.StudentRepository, txRepo repository.TransactionRepository, paymentRepo repository.PaymentRepository, botServiceAddr string) PaymentService {
	conn, err := grpc.NewClient(botServiceAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Printf("[OGOHLANTIRISH] Telegram bot gRPC servisiga ulanib bo'lmadi: %v", err)
	}

	return &paymentService{
		db:          db,
		studentRepo: studentRepo,
		txRepo:      txRepo,
		paymentRepo: paymentRepo,
		botClient:   bot_admin.NewBotAdminServiceClient(conn),
	}
}

func (s *paymentService) sendPaymentNotification(student *models.Student, branch *models.Branch, amount int64, performTime int64) {
	if s.botClient == nil {
		log.Println("[OGOHLANTIRISH] Bot klienti ishga tushirilmagan, xabarnoma yuborilmadi.")
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Second*5)
	defer cancel()

	// time.UnixMilli mahalliy vaqtni (Toshkent) qaytaradi, chunki Dockerda TZ sozlangan
	t := time.UnixMilli(performTime)
	paymentTimeStr := t.Format("2006-01-02 15:04:05")

	req := &bot_admin.NotifyPaymentSuccessRequest{
		StudentName:    *student.FullName,
		BranchName:     branch.Name,
		GroupName:      *student.GroupName,
		Amount:         amount,
		PaymentTime:    paymentTimeStr,
		TopicId:        branch.TopicID, // YANGI: Topic ID ni botga yuboramiz
	}

	if student.AccountID != nil {
		req.AccountId = *student.AccountID
	}
	if student.ContractNumber != nil {
		req.ContractNumber = *student.ContractNumber
	}

	log.Printf("[INFO] Botga yuborilayotgan xabarnoma ma'lumotlari: %+v", req)

	_, err := s.botClient.NotifyPaymentSuccess(ctx, req)
	if err != nil {
		log.Printf("[XATOLIK] Telegram botga xabarnoma yuborishda xatolik: %v", err)
	} else {
		log.Printf("[INFO] To'lov haqida xabarnoma botga muvaffaqiyatli yuborildi.")
	}
}

func (s *paymentService) CheckPerformTransaction(ctx context.Context, params CheckPerformTransactionParams) (*CheckPerformTransactionResponse, error) {
	if params.Amount < 1 {
		return nil, utils.ErrInvalidAmount
	}

	student, branch, err := s.studentRepo.GetStudentAndBranchByAccountID(ctx, params.Account.ID)
	if err != nil || student == nil || branch == nil {
		return nil, utils.ErrUserNotFound
	}

	if !student.Status {
		log.Printf("Nofaol talaba (ID: %s) uchun to'lovga urinish bo'ldi.", params.Account.ID)
		return nil, utils.ErrUserNotFound
	}

	var amountToPay int64 = branch.MonthlyFee
	if student.DiscountPercent > 0 {
		amountToPay = branch.MonthlyFee - int64(float64(branch.MonthlyFee)*(student.DiscountPercent/100.0))
	}

	return &CheckPerformTransactionResponse{
		Allow: true,
		Additional: StudentAdditionalInfo{
			FullName:      student.FullName,
			ParentName:    student.ParentName,
			BranchName:    branch.Name,
			GroupName:     student.GroupName,
			GroupNumber:   extractGroupNumber(student.GroupName),
			AmountToPay:   amountToPay,
			MfoCode:       branch.MfoCode,
			AccountNumber: branch.AccountNumber,
		},
	}, nil
}

func (s *paymentService) CreateTransaction(ctx context.Context, params CreateTransactionParams) (*CreateTransactionResponse, error) {
	if params.Amount < 1 {
		return nil, utils.ErrInvalidAmount
	}

	student, branch, err := s.studentRepo.GetStudentAndBranchByAccountID(ctx, params.Account.ID)
	if err != nil || student == nil || branch == nil || branch.MerchantID == nil {
		return nil, utils.ErrUserNotFound
	}

	if !student.Status {
		return nil, utils.ErrUserNotFound
	}

	existingTx, _ := s.txRepo.GetTransactionByPaymeTxID(ctx, params.ID)
	if existingTx != nil {
		if existingTx.State != models.StatePending {
			return nil, utils.ErrCouldNotPerform
		}
		return &CreateTransactionResponse{
			CreateTime:  existingTx.CreateTime,
			Transaction: strconv.FormatInt(existingTx.ID, 10),
			State:       int(existingTx.State),
			Receivers:   []*Receiver{{ID: branch.MerchantID, Amount: existingTx.Amount}},
		}, nil
	}

	tx, err := s.db.Begin(ctx)
	if err != nil {
		return nil, utils.ErrInternalServer
	}
	defer tx.Rollback(ctx)

	newTxModel := &models.Transaction{
		PaymeTxID:  params.ID,
		StudentID:  student.ID,
		Amount:     params.Amount,
		CreateTime: params.Time,
		State:      models.StatePending,
	}

	createdTx, err := s.txRepo.CreateTransaction(ctx, tx, newTxModel)
	if err != nil {
		return nil, utils.ErrInternalServer
	}
	if err := tx.Commit(ctx); err != nil {
		return nil, utils.ErrInternalServer
	}

	return &CreateTransactionResponse{
		CreateTime:  createdTx.CreateTime,
		Transaction: strconv.FormatInt(createdTx.ID, 10),
		State:       int(createdTx.State),
		Receivers:   []*Receiver{{ID: branch.MerchantID, Amount: createdTx.Amount}},
	}, nil
}

func (s *paymentService) PerformTransaction(ctx context.Context, params TransactionParams) (*PerformTransactionResponse, error) {
	tx, err := s.db.Begin(ctx)
	if err != nil {
		return nil, utils.ErrInternalServer
	}
	defer tx.Rollback(ctx)

	transaction, err := s.txRepo.GetTransactionByPaymeTxID(ctx, params.ID)
	if err != nil || transaction == nil {
		return nil, utils.ErrTransactionNotFound
	}

	if transaction.State != models.StatePending {
		if transaction.State == models.StatePerformed {
			return &PerformTransactionResponse{
				Transaction: strconv.FormatInt(transaction.ID, 10),
				PerformTime: transaction.PerformTime,
				State:       int(transaction.State),
			}, nil
		}
		return nil, utils.ErrCouldNotPerform
	}

	student, branch, err := s.studentRepo.GetStudentAndBranchByStudentID(ctx, transaction.StudentID)
	if err != nil || student == nil || branch == nil {
		return nil, utils.ErrCouldNotPerform
	}

	if !student.Status {
		return nil, utils.ErrCouldNotPerform
	}

	newBalance := student.Balance + transaction.Amount
	if err := s.studentRepo.UpdateStudentBalance(ctx, tx, student.ID, newBalance); err != nil {
		return nil, utils.ErrInternalServer
	}

	// O'ZGARISH: .UTC() olib tashlandi. Endi konteyner vaqti (Toshkent) ishlatiladi.
	payment := &models.Payment{
		StudentID:  student.ID,
		Month:      time.Now(), // Toshkent vaqti
		AmountPaid: transaction.Amount,
		PaidAt:     time.Now(), // Toshkent vaqti
	}
	if err := s.paymentRepo.CreatePayment(ctx, tx, payment); err != nil {
		return nil, utils.ErrInternalServer
	}

	performTime := time.Now().UnixMilli()
	updatedTx, err := s.txRepo.UpdateTransactionState(ctx, tx, transaction.PaymeTxID, models.StatePerformed, performTime, 0, nil)
	if err != nil {
		return nil, utils.ErrCouldNotPerform
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, utils.ErrInternalServer
	}

	go s.sendPaymentNotification(student, branch, updatedTx.Amount, updatedTx.PerformTime)

	return &PerformTransactionResponse{
		Transaction: strconv.FormatInt(updatedTx.ID, 10),
		PerformTime: updatedTx.PerformTime,
		State:       int(updatedTx.State),
	}, nil
}

func (s *paymentService) CancelTransaction(ctx context.Context, params TransactionParams) (*CancelTransactionResponse, error) {
	if params.Reason == nil {
		return nil, utils.ErrInvalidParams
	}

	tx, err := s.db.Begin(ctx)
	if err != nil {
		return nil, utils.ErrInternalServer
	}
	defer tx.Rollback(ctx)

	transaction, err := s.txRepo.GetTransactionByPaymeTxID(ctx, params.ID)
	if err != nil || transaction == nil {
		return nil, utils.ErrTransactionNotFound
	}

	var newState models.TransactionState
	if transaction.State == models.StatePending {
		newState = models.StateCancelled
	} else if transaction.State == models.StatePerformed {
		return nil, utils.ErrCouldNotCancel
	} else {
		return &CancelTransactionResponse{
			Transaction: strconv.FormatInt(transaction.ID, 10),
			CancelTime:  transaction.CancelTime,
			State:       int(transaction.State),
		}, nil
	}

	cancelTime := time.Now().UnixMilli()
	updatedTx, err := s.txRepo.UpdateTransactionState(ctx, tx, transaction.PaymeTxID, newState, transaction.PerformTime, cancelTime, params.Reason)
	if err != nil {
		return nil, utils.ErrCouldNotCancel
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, utils.ErrInternalServer
	}

	return &CancelTransactionResponse{
		Transaction: strconv.FormatInt(updatedTx.ID, 10),
		CancelTime:  updatedTx.CancelTime,
		State:       int(updatedTx.State),
	}, nil
}

func (s *paymentService) CheckTransaction(ctx context.Context, params TransactionParams) (*CheckTransactionResponse, error) {
	transaction, err := s.txRepo.GetTransactionByPaymeTxID(ctx, params.ID)
	if err != nil || transaction == nil {
		return nil, utils.ErrTransactionNotFound
	}

	response := &CheckTransactionResponse{
		CreateTime:  transaction.CreateTime,
		PerformTime: transaction.PerformTime,
		CancelTime:  transaction.CancelTime,
		Transaction: strconv.FormatInt(transaction.ID, 10),
		State:       int(transaction.State),
		Reason:      transaction.Reason,
	}

	return response, nil
}

func (s *paymentService) GetStatement(ctx context.Context, params *payment.GetStatementRequest) (*payment.GetStatementResponse, error) {
	transactions, err := s.txRepo.GetTransactionsByTimeRange(ctx, params.From, params.To)
	if err != nil {
		log.Printf("GetStatement uchun tranzaksiyalarni olib bo'lmadi: %v", err)
		return nil, utils.ErrInternalServer
	}

	var resultTransactions []*payment.StatementTransaction
	for _, tx := range transactions {
		student, branch, err := s.studentRepo.GetStudentAndBranchByStudentID(ctx, tx.StudentID)
		if err != nil || student == nil || branch == nil {
			log.Printf("Tranzaksiya uchun o'quvchi yoki filial topilmadi (student_id: %s)", tx.StudentID)
			continue
		}

		grpcTx := &payment.StatementTransaction{
			Id:          tx.PaymeTxID,
			Time:        tx.CreateTime,
			Amount:      tx.Amount,
			Account:     &payment.Account{Id: *student.AccountID},
			CreateTime:  tx.CreateTime,
			PerformTime: tx.PerformTime,
			CancelTime:  tx.CancelTime,
			Transaction: strconv.FormatInt(tx.ID, 10),
			State:       int32(tx.State),
			Receivers: []*payment.Receiver{
				{
					Id:     *branch.MerchantID,
					Amount: tx.Amount,
				},
			},
		}
		if tx.Reason != nil {
			reason := int32(*tx.Reason)
			grpcTx.Reason = &reason
		}
		resultTransactions = append(resultTransactions, grpcTx)
	}

	return &payment.GetStatementResponse{
		Transactions: resultTransactions,
	}, nil
}

func extractGroupNumber(groupName *string) string {
	if groupName == nil || *groupName == "" {
		return "Noma'lum"
	}
	re := regexp.MustCompile(`[\d\w-]+`)
	match := re.FindString(*groupName)
	if match != "" {
		return match
	}
	return "Noma'lum"
}