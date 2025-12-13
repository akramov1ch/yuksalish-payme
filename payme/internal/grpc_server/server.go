package grpc_server

import (
	"context"
	"payme/genproto/payment"
	"payme/internal/models"
	"payme/internal/service"
	"payme/pkg/utils"

	"github.com/google/uuid"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/emptypb"
)

type grpcServer struct {
	payment.UnimplementedPaymentServiceServer
	payment.UnimplementedManagementServiceServer
	paymentService    service.PaymentService
	managementService service.ManagementService
}

func NewGRPCServer(paymentService service.PaymentService, managementService service.ManagementService) *grpcServer {
	return &grpcServer{
		paymentService:    paymentService,
		managementService: managementService,
	}
}

func convertRPCErrorToGRPC(err error) error {
	if rpcErr, ok := err.(utils.RPCError); ok {
		var code codes.Code
		switch rpcErr.Code {
		case utils.ErrInvalidParams.Code, utils.ErrInvalidAmount.Code:
			code = codes.InvalidArgument
		case utils.ErrUserNotFound.Code, utils.ErrTransactionNotFound.Code:
			code = codes.NotFound
		case utils.ErrCouldNotPerform.Code, utils.ErrCouldNotCancel.Code:
			code = codes.FailedPrecondition
		default:
			code = codes.Internal
		}
		return status.Errorf(code, "%d:%s", rpcErr.Code, rpcErr.Message.RU)
	}
	return status.Errorf(codes.Internal, "unknown internal error: %v", err)
}


func (s *grpcServer) CheckPerformTransaction(ctx context.Context, req *payment.CheckPerformTransactionRequest) (*payment.CheckPerformTransactionResponse, error) {
	params := service.CheckPerformTransactionParams{
		Amount:  req.Amount,
		Account: service.AccountParams{ID: req.Account.Id},
	}
	res, err := s.paymentService.CheckPerformTransaction(ctx, params)
	if err != nil {
		return nil, convertRPCErrorToGRPC(err)
	}
	return &payment.CheckPerformTransactionResponse{
		Allow: res.Allow,
		Additional: &payment.StudentAdditionalInfo{
			FullName:      *res.Additional.FullName,
			ParentName:    res.Additional.ParentName,
			BranchName:    res.Additional.BranchName,
			GroupName:     *res.Additional.GroupName,
			GroupNumber:   res.Additional.GroupNumber,
			AmountToPay:   res.Additional.AmountToPay,
			MfoCode:       res.Additional.MfoCode,
			AccountNumber: res.Additional.AccountNumber,
		},
	}, nil
}

func (s *grpcServer) CreateTransaction(ctx context.Context, req *payment.CreateTransactionRequest) (*payment.CreateTransactionResponse, error) {
	params := service.CreateTransactionParams{
		ID:      req.Id,
		Time:    req.Time,
		Amount:  req.Amount,
		Account: service.AccountParams{ID: req.Account.Id},
	}
	res, err := s.paymentService.CreateTransaction(ctx, params)
	if err != nil {
		return nil, convertRPCErrorToGRPC(err)
	}

	grpcReceivers := make([]*payment.Receiver, 0, len(res.Receivers))
	for _, r := range res.Receivers {
		grpcReceivers = append(grpcReceivers, &payment.Receiver{
			Id:     *r.ID,
			Amount: r.Amount,
		})
	}

	return &payment.CreateTransactionResponse{
		CreateTime:  res.CreateTime,
		Transaction: res.Transaction,
		State:       int32(res.State),
		Receivers:   grpcReceivers,
	}, nil
}

func (s *grpcServer) PerformTransaction(ctx context.Context, req *payment.TransactionRequest) (*payment.PerformTransactionResponse, error) {
	params := service.TransactionParams{ID: req.Id}
	res, err := s.paymentService.PerformTransaction(ctx, params)
	if err != nil {
		return nil, convertRPCErrorToGRPC(err)
	}
	return &payment.PerformTransactionResponse{
		Transaction: res.Transaction,
		PerformTime: res.PerformTime,
		State:       int32(res.State),
	}, nil
}

func (s *grpcServer) CancelTransaction(ctx context.Context, req *payment.CancelTransactionRequest) (*payment.CancelTransactionResponse, error) {
	reason := int(req.Reason)
	params := service.TransactionParams{ID: req.Id, Reason: &reason}
	res, err := s.paymentService.CancelTransaction(ctx, params)
	if err != nil {
		return nil, convertRPCErrorToGRPC(err)
	}
	return &payment.CancelTransactionResponse{
		Transaction: res.Transaction,
		CancelTime:  res.CancelTime,
		State:       int32(res.State),
	}, nil
}

func (s *grpcServer) CheckTransaction(ctx context.Context, req *payment.TransactionRequest) (*payment.CheckTransactionResponse, error) {
	params := service.TransactionParams{ID: req.Id}
	res, err := s.paymentService.CheckTransaction(ctx, params)
	if err != nil {
		return nil, convertRPCErrorToGRPC(err)
	}

	var reason *int32
	if res.Reason != nil {
		val := int32(*res.Reason)
		reason = &val
	}

	return &payment.CheckTransactionResponse{
		CreateTime:  res.CreateTime,
		PerformTime: res.PerformTime,
		CancelTime:  res.CancelTime,
		Transaction: res.Transaction,
		State:       int32(res.State),
		Reason:      reason,
	}, nil
}

func (s *grpcServer) GetStatement(ctx context.Context, req *payment.GetStatementRequest) (*payment.GetStatementResponse, error) {
	res, err := s.paymentService.GetStatement(ctx, req)
	if err != nil {
		return nil, convertRPCErrorToGRPC(err)
	}
	return res, nil
}

func (s *grpcServer) CreateBranch(ctx context.Context, req *payment.CreateBranchRequest) (*payment.Branch, error) {
	branchModel := &models.Branch{
		Name:          req.Name,
		MonthlyFee:    req.MonthlyFee,
		MfoCode:       req.MfoCode,
		AccountNumber: req.AccountNumber,
		MerchantID:    &req.MerchantId,
		TopicID:       req.TopicId, // YANGI
	}
	created, err := s.managementService.CreateBranch(ctx, branchModel)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Internal server error: %v", err)
	}
	return &payment.Branch{
		Id:            created.ID.String(),
		Name:          created.Name,
		MonthlyFee:    created.MonthlyFee,
		MfoCode:       created.MfoCode,
		AccountNumber: created.AccountNumber,
		MerchantId:    *created.MerchantID,
		TopicId:       created.TopicID, // YANGI
	}, nil
}

func (s *grpcServer) GetBranch(ctx context.Context, req *payment.ByIdRequest) (*payment.Branch, error) {
	branch, err := s.managementService.GetBranch(ctx, req.Id)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "Branch not found: %v", err)
	}
	return &payment.Branch{
		Id:            branch.ID.String(),
		Name:          branch.Name,
		MonthlyFee:    branch.MonthlyFee,
		MfoCode:       branch.MfoCode,
		AccountNumber: branch.AccountNumber,
		MerchantId:    *branch.MerchantID,
		TopicId:       branch.TopicID, // YANGI
	}, nil
}

func (s *grpcServer) ListBranches(ctx context.Context, _ *emptypb.Empty) (*payment.ListBranchesResponse, error) {
	branches, err := s.managementService.ListBranches(ctx)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Internal server error: %v", err)
	}
	res := &payment.ListBranchesResponse{Branches: make([]*payment.Branch, 0, len(branches))}
	for _, b := range branches {
		res.Branches = append(res.Branches, &payment.Branch{
			Id:            b.ID.String(),
			Name:          b.Name,
			MonthlyFee:    b.MonthlyFee,
			MfoCode:       b.MfoCode,
			AccountNumber: b.AccountNumber,
			MerchantId:    *b.MerchantID,
			TopicId:       b.TopicID, // YANGI
		})
	}
	return res, nil
}

func (s *grpcServer) UpdateBranch(ctx context.Context, req *payment.Branch) (*payment.Branch, error) {
	uid, err := uuid.Parse(req.Id)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "Invalid UUID format: %v", err)
	}
	branchModel := &models.Branch{
		ID:            uid,
		Name:          req.Name,
		MonthlyFee:    req.MonthlyFee,
		MfoCode:       req.MfoCode,
		AccountNumber: req.AccountNumber,
		MerchantID:    &req.MerchantId,
		TopicID:       req.TopicId, // YANGI
	}
	updated, err := s.managementService.UpdateBranch(ctx, branchModel)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Internal server error: %v", err)
	}
	return &payment.Branch{
		Id:            updated.ID.String(),
		Name:          updated.Name,
		MonthlyFee:    updated.MonthlyFee,
		MfoCode:       updated.MfoCode,
		AccountNumber: updated.AccountNumber,
		MerchantId:    *updated.MerchantID,
		TopicId:       updated.TopicID, // YANGI
	}, nil
}

func (s *grpcServer) DeleteBranch(ctx context.Context, req *payment.ByIdRequest) (*emptypb.Empty, error) {
	err := s.managementService.DeleteBranch(ctx, req.Id)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Internal server error: %v", err)
	}
	return &emptypb.Empty{}, nil
}

func (s *grpcServer) CreateStudent(ctx context.Context, req *payment.CreateStudentRequest) (*payment.Student, error) {
	branchUUID, err := uuid.Parse(req.BranchId)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "Invalid Branch UUID format: %v", err)
	}
	studentModel := &models.Student{
		AccountID:       &req.AccountId,
		BranchID:        branchUUID,
		ParentName:      req.ParentName,
		DiscountPercent: req.DiscountPercent,
		FullName:        &req.FullName,
		GroupName:       &req.GroupName,
		Phone:           &req.Phone,
		ContractNumber:  &req.ContractNumber,
	}
	created, err := s.managementService.CreateStudent(ctx, studentModel)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Internal server error: %v", err)
	}
	
	contractNum := ""
	if created.ContractNumber != nil {
		contractNum = *created.ContractNumber
	}
	
	return &payment.Student{
		Id:              created.ID.String(),
		AccountId:       *created.AccountID,
		BranchId:        created.BranchID.String(),
		ParentName:      created.ParentName,
		DiscountPercent: created.DiscountPercent,
		Balance:         created.Balance,
		FullName:        *created.FullName,
		GroupName:       *created.GroupName,
		Phone:           *created.Phone,
		ContractNumber:  contractNum,
	}, nil
}

func (s *grpcServer) GetStudentByAccountId(ctx context.Context, req *payment.ByAccountIdRequest) (*payment.Student, error) {
	student, err := s.managementService.GetStudentByAccountId(ctx, req.AccountId)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Internal server error: %v", err)
	}
	if student == nil {
		return nil, status.Errorf(codes.NotFound, "Student with account_id '%s' not found", req.AccountId)
	}

	contractNum := ""
	if student.ContractNumber != nil {
		contractNum = *student.ContractNumber
	}

	return &payment.Student{
		Id:              student.ID.String(),
		AccountId:       *student.AccountID,
		BranchId:        student.BranchID.String(),
		ParentName:      student.ParentName,
		DiscountPercent: student.DiscountPercent,
		Balance:         student.Balance,
		FullName:        *student.FullName,
		GroupName:       *student.GroupName,
		Phone:           *student.Phone,
		ContractNumber:  contractNum,
	}, nil
}

func (s *grpcServer) ListStudents(ctx context.Context, _ *payment.ListRequest) (*payment.ListStudentsResponse, error) {
	students, err := s.managementService.ListStudents(ctx)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Internal server error: %v", err)
	}
	res := &payment.ListStudentsResponse{Students: make([]*payment.Student, 0, len(students))}
	for _, st := range students {
		contractNum := ""
		if st.ContractNumber != nil {
			contractNum = *st.ContractNumber
		}
		res.Students = append(res.Students, &payment.Student{
			Id:              st.ID.String(),
			AccountId:       *st.AccountID,
			BranchId:        st.BranchID.String(),
			ParentName:      st.ParentName,
			DiscountPercent: st.DiscountPercent,
			Balance:         st.Balance,
			FullName:        *st.FullName,
			GroupName:       *st.GroupName,
			Phone:           *st.Phone,
			ContractNumber:  contractNum,
		})
	}
	return res, nil
}

func (s *grpcServer) UpdateStudent(ctx context.Context, req *payment.Student) (*payment.Student, error) {
	if req.AccountId == "" {
		return nil, status.Errorf(codes.InvalidArgument, "AccountID is required for update")
	}
	branchUUID, err := uuid.Parse(req.BranchId)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "Invalid Branch UUID format: %v", err)
	}
	
	studentModel := &models.Student{
		AccountID:       &req.AccountId,
		BranchID:        branchUUID,
		ParentName:      req.ParentName,
		DiscountPercent: req.DiscountPercent,
		FullName:        &req.FullName,
		GroupName:       &req.GroupName,
		Phone:           &req.Phone,
		ContractNumber:  &req.ContractNumber,
		Status:          req.Status, // <--- MANA SHU QATOR YETISHMAYOTGAN EDI!
	}
	
	updated, err := s.managementService.UpdateStudent(ctx, studentModel)
	if err != nil {
		return nil, handleDBError(err)
	}

	contractNum := ""
	if updated.ContractNumber != nil {
		contractNum = *updated.ContractNumber
	}

	return &payment.Student{
		Id:              updated.ID.String(),
		AccountId:       *updated.AccountID,
		BranchId:        updated.BranchID.String(),
		ParentName:      updated.ParentName,
		DiscountPercent: updated.DiscountPercent,
		Balance:         updated.Balance,
		FullName:        *updated.FullName,
		GroupName:       *updated.GroupName,
		Phone:           *updated.Phone,
		ContractNumber:  contractNum,
		Status:          updated.Status, // Bu yerda to'g'ri qaytayotgan edi, lekin baza yangilanmagani uchun false qaytgan
	}, nil
}

func (s *grpcServer) DeleteStudentByAccountId(ctx context.Context, req *payment.ByAccountIdRequest) (*emptypb.Empty, error) {
	err := s.managementService.DeleteStudentByAccountId(ctx, req.AccountId)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Internal server error: %v", err)
	}
	return &emptypb.Empty{}, nil
}

func (s *grpcServer) CreateStudentsBatch(ctx context.Context, req *payment.CreateStudentsBatchRequest) (*payment.CreateStudentsBatchResponse, error) {
	studentsToCreate := make([]*models.Student, len(req.Students))
	for i, grpcStudent := range req.Students {
		branchUUID, err := uuid.Parse(grpcStudent.BranchId)
		if err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "Invalid Branch UUID format for student %s: %v", grpcStudent.FullName, err)
		}
		
		var accID *string
		if grpcStudent.AccountId != "" {
			val := grpcStudent.AccountId
			accID = &val
		}

		studentsToCreate[i] = &models.Student{
			AccountID:       accID,
			BranchID:        branchUUID,
			ParentName:      grpcStudent.ParentName,
			DiscountPercent: grpcStudent.DiscountPercent,
			FullName:        &grpcStudent.FullName,
			GroupName:       &grpcStudent.GroupName,
			Phone:           &grpcStudent.Phone,
			ContractNumber:  &grpcStudent.ContractNumber,
		}
	}

	createdStudents, err := s.managementService.CreateStudentsBatch(ctx, studentsToCreate)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Failed to create students in batch: %v", err)
	}

	grpcStudents := make([]*payment.Student, len(createdStudents))
	for i, modelStudent := range createdStudents {
		contractNum := ""
		if modelStudent.ContractNumber != nil {
			contractNum = *modelStudent.ContractNumber
		}
		grpcStudents[i] = &payment.Student{
			Id:              modelStudent.ID.String(),
			AccountId:       *modelStudent.AccountID,
			BranchId:        modelStudent.BranchID.String(),
			ParentName:      modelStudent.ParentName,
			DiscountPercent: modelStudent.DiscountPercent,
			FullName:        *modelStudent.FullName,
			GroupName:       *modelStudent.GroupName,
			Phone:           *modelStudent.Phone,
			ContractNumber:  contractNum,
		}
	}

	return &payment.CreateStudentsBatchResponse{Students: grpcStudents}, nil
}

func (s *grpcServer) UpdateStudentsBatch(ctx context.Context, req *payment.UpdateStudentsBatchRequest) (*emptypb.Empty, error) {
	studentsToUpdate := make([]*models.Student, len(req.Students))
	for i, grpcStudent := range req.Students {
		studentUUID, err := uuid.Parse(grpcStudent.Id)
		if err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "Invalid Student UUID format: %v", err)
		}
		branchUUID, err := uuid.Parse(grpcStudent.BranchId)
		if err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "Invalid Branch UUID format: %v", err)
		}

		var accID *string
		if grpcStudent.AccountId != "" {
			val := grpcStudent.AccountId
			accID = &val
		}

		studentsToUpdate[i] = &models.Student{
			ID:              studentUUID,
			AccountID:       accID,
			BranchID:        branchUUID,
			ParentName:      grpcStudent.ParentName,
			DiscountPercent: grpcStudent.DiscountPercent,
			FullName:        &grpcStudent.FullName,
			GroupName:       &grpcStudent.GroupName,
			Phone:           &grpcStudent.Phone,
			ContractNumber:  &grpcStudent.ContractNumber,
			Status:          grpcStudent.Status,
		}
	}

	err := s.managementService.UpdateStudentsBatch(ctx, studentsToUpdate)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Failed to update students in batch: %v", err)
	}

	return &emptypb.Empty{}, nil
}

func (s *grpcServer) DeleteStudentsBatch(ctx context.Context, req *payment.DeleteStudentsBatchRequest) (*emptypb.Empty, error) {
	if len(req.AccountIds) == 0 {
		return &emptypb.Empty{}, nil
	}

	err := s.managementService.DeleteStudentsBatch(ctx, req.AccountIds)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Failed to delete students in batch: %v", err)
	}

	return &emptypb.Empty{}, nil
}