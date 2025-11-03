package handler

import (
	"api-gateway/internal/config"
	"api-gateway/internal/grpc_client"
	"encoding/base64"
	"encoding/json"
	"api-gateway/genproto/payment"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"sync"

	"github.com/gin-gonic/gin"
	"google.golang.org/grpc/status"
)

var (
	currentPassword string
	passwordMutex   sync.RWMutex
)

type RPCHandler struct {
	grpcClient *grpc_client.GrpcClient
	config     *config.Config
}

type RPCRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params"`
	ID      interface{}     `json:"id"`
}

type MultilingualMessage struct {
	EN string `json:"en"`
	RU string `json:"ru"`
	UZ string `json:"uz"`
}

type RPCError struct {
	Code    int               `json:"code"`
	Message MultilingualMessage `json:"message"`
	Data    interface{}       `json:"data,omitempty"`
}

type RPCResponse struct {
	JSONRPC string      `json:"jsonrpc"`
	Result  interface{} `json:"result,omitempty"`
	Error   *RPCError   `json:"error,omitempty"`
	ID      interface{} `json:"id"`
}

type CheckTransactionResult struct {
	CreateTime  int64  `json:"create_time"`
	PerformTime int64  `json:"perform_time"`
	CancelTime  int64  `json:"cancel_time"`
	Transaction string `json:"transaction"`
	State       int32  `json:"state"`
	Reason      *int32 `json:"reason"`
}

type StatementAccount struct {
	ID string `json:"id"`
}

type StatementReceiver struct {
	ID     string `json:"id"`
	Amount int64  `json:"amount"`
}

type StatementTransactionResult struct {
	ID          string               `json:"id"`
	Time        int64                `json:"time"`
	Amount      int64                `json:"amount"`
	Account     StatementAccount     `json:"account"`
	CreateTime  int64                `json:"create_time"`
	PerformTime int64                `json:"perform_time"`
	CancelTime  int64                `json:"cancel_time"` 
	Transaction string               `json:"transaction"`
	State       int32                `json:"state"`
	Reason      *int32               `json:"reason"` 
	Receivers   []StatementReceiver  `json:"receivers"`
}

type GetStatementResult struct {
	Transactions []StatementTransactionResult `json:"transactions"`
}


func NewRPCHandler(grpcClient *grpc_client.GrpcClient, cfg *config.Config) *RPCHandler {
	passwordMutex.Lock()
	currentPassword = cfg.PaymePassword
	passwordMutex.Unlock()

	return &RPCHandler{grpcClient: grpcClient, config: cfg}
}

func getAccountIDFromParams(params json.RawMessage) (string, bool) {
	var data map[string]interface{}
	if err := json.Unmarshal(params, &data); err != nil {
		return "", false
	}
	accountMap, ok := data["account"].(map[string]interface{})
	if !ok {
		return "", false
	}
	if accountID, ok := accountMap["id"].(string); ok {
		return accountID, true
	}
	if accountID, ok := accountMap["user_id"].(string); ok {
		return accountID, true
	}
	return "", false
}

func (h *RPCHandler) HandleRequest(c *gin.Context) {
	log.Println("------------------- YANGI SO'ROV KELDI -------------------")

	bodyBytes, err := io.ReadAll(c.Request.Body)
	if err != nil {
		log.Println("[XATOLIK] So'rov tanasini o'qib bo'lmadi:", err)
		h.sendJsonRpcError(c, nil, -32700, "Parse error", nil)
		return
	}
	log.Printf("[INFO] Kiruvchi so'rov tanasi: %s", string(bodyBytes))

	var tempReq RPCRequest
	if err := json.Unmarshal(bodyBytes, &tempReq); err != nil {
		log.Println("[XATOLIK] So'rov ID'sini o'qishda xatolik:", err)
		h.sendJsonRpcError(c, nil, -32700, "Parse error", nil)
		return
	}
	reqID := tempReq.ID
	log.Printf("[INFO] So'rov ID: %v, Metod: %s", reqID, tempReq.Method)

	authHeader := c.GetHeader("Authorization")
	if !strings.HasPrefix(authHeader, "Basic ") {
		log.Println("[XATOLIK] Avtorizatsiya sarlavhasi yo'q yoki noto'g'ri formatda.")
		h.sendJsonRpcError(c, reqID, -32504, "Invalid authorization", nil)
		return
	}
	payload, err := base64.StdEncoding.DecodeString(authHeader[6:])
	if err != nil {
		log.Println("[XATOLIK] Avtorizatsiya ma'lumotlarini dekodlashda xatolik:", err)
		h.sendJsonRpcError(c, reqID, -32504, "Invalid authorization", nil)
		return
	}
	pair := strings.SplitN(string(payload), ":", 2)

	passwordMutex.RLock()
	isPasswordCorrect := len(pair) == 2 && pair[0] == h.config.PaymeLogin && pair[1] == currentPassword
	passwordMutex.RUnlock()

	if !isPasswordCorrect {
		log.Printf("[XATOLIK] Noto'g'ri login yoki parol. Kelgan login: %s", pair[0])
		h.sendJsonRpcError(c, reqID, -32504, "Invalid authorization", nil)
		return
	}
	log.Println("[INFO] Avtorizatsiya muvaffaqiyatli o'tdi.")

	var params map[string]interface{}
	if err := json.Unmarshal(tempReq.Params, &params); err != nil {
		log.Println("[XATOLIK] So'rov parametrlarini (params) o'qishda xatolik:", err)
		h.sendJsonRpcError(c, reqID, -32602, "Invalid params", nil)
		return
	}

	var result interface{}
	var rpcErr error

	switch tempReq.Method {
	case "CheckPerformTransaction":
		log.Println("[INFO] CheckPerformTransaction metodi chaqirildi.")
		amount, _ := params["amount"].(float64)
		accountID, ok := getAccountIDFromParams(tempReq.Params)
		if !ok {
			h.sendJsonRpcError(c, reqID, -32602, "Invalid params", "account.id or account.user_id is missing")
			return
		}
		grpcReq := &payment.CheckPerformTransactionRequest{Amount: int64(amount), Account: &payment.Account{Id: accountID}}
		result, rpcErr = h.grpcClient.PaymentServiceClient.CheckPerformTransaction(c.Request.Context(), grpcReq)

	case "CreateTransaction":
		log.Println("[INFO] CreateTransaction metodi chaqirildi.")
		amount, _ := params["amount"].(float64)
		accountID, _ := getAccountIDFromParams(tempReq.Params)
		id, _ := params["id"].(string)
		timeVal, _ := params["time"].(float64)
		grpcReq := &payment.CreateTransactionRequest{Id: id, Time: int64(timeVal), Amount: int64(amount), Account: &payment.Account{Id: accountID}}
		result, rpcErr = h.grpcClient.PaymentServiceClient.CreateTransaction(c.Request.Context(), grpcReq)

	case "PerformTransaction":
		log.Println("[INFO] PerformTransaction metodi chaqirildi.")
		id, _ := params["id"].(string)
		grpcReq := &payment.TransactionRequest{Id: id}
		result, rpcErr = h.grpcClient.PaymentServiceClient.PerformTransaction(c.Request.Context(), grpcReq)

	case "CheckTransaction":
		log.Println("[INFO] CheckTransaction metodi chaqirildi.")
		id, _ := params["id"].(string)
		grpcReq := &payment.TransactionRequest{Id: id}
		var grpcResult *payment.CheckTransactionResponse
		grpcResult, rpcErr = h.grpcClient.PaymentServiceClient.CheckTransaction(c.Request.Context(), grpcReq)
		if rpcErr == nil {
			result = CheckTransactionResult{
				CreateTime:  grpcResult.CreateTime,
				PerformTime: grpcResult.PerformTime,
				CancelTime:  grpcResult.CancelTime,
				Transaction: grpcResult.Transaction,
				State:       grpcResult.State,
				Reason:      grpcResult.Reason,
			}
		}

	case "CancelTransaction":
		log.Println("[INFO] CancelTransaction metodi chaqirildi.")
		id, _ := params["id"].(string)
		reason, _ := params["reason"].(float64)
		grpcReq := &payment.CancelTransactionRequest{Id: id, Reason: int32(reason)}
		result, rpcErr = h.grpcClient.PaymentServiceClient.CancelTransaction(c.Request.Context(), grpcReq)

	case "GetStatement":
		log.Println("[INFO] GetStatement metodi chaqirildi.")
		from, _ := params["from"].(float64)
		to, _ := params["to"].(float64)
		grpcReq := &payment.GetStatementRequest{From: int64(from), To: int64(to)}
		
		var grpcResult *payment.GetStatementResponse
		grpcResult, rpcErr = h.grpcClient.PaymentServiceClient.GetStatement(c.Request.Context(), grpcReq)

		if rpcErr == nil {
			statementTransactions := make([]StatementTransactionResult, 0, len(grpcResult.Transactions))
			for _, grpcTx := range grpcResult.Transactions {
				receivers := make([]StatementReceiver, 0, len(grpcTx.Receivers))
				for _, r := range grpcTx.Receivers {
					receivers = append(receivers, StatementReceiver{
						ID:     r.Id,
						Amount: r.Amount,
					})
				}

				tx := StatementTransactionResult{
					ID:          grpcTx.Id,
					Time:        grpcTx.Time,
					Amount:      grpcTx.Amount,
					Account:     StatementAccount{ID: grpcTx.Account.Id},
					CreateTime:  grpcTx.CreateTime,
					PerformTime: grpcTx.PerformTime,
					CancelTime:  grpcTx.CancelTime,
					Transaction: grpcTx.Transaction,
					State:       grpcTx.State,
					Reason:      grpcTx.Reason,
					Receivers:   receivers,
				}
				statementTransactions = append(statementTransactions, tx)
			}
			result = GetStatementResult{Transactions: statementTransactions}
		}

	case "ChangePassword":
		log.Println("[INFO] ChangePassword metodi chaqirildi.")
		newPassword, ok := params["password"].(string)
		if !ok {
			h.sendJsonRpcError(c, reqID, -32602, "Invalid params", "password field is missing or not a string")
			return
		}
		
		passwordMutex.Lock()
		currentPassword = newPassword
		passwordMutex.Unlock()

		log.Printf("[DIQQAT] Parol xotirada muvaffaqiyatli o'zgartirildi. Yangi parol: %s", newPassword)
		log.Println("[DIQQAT] Testdan o'tgach, .env faylidagi PAYME_PASSWORD o'zgaruvchisini yangilang va servisni qayta ishga tushiring!")

		result = map[string]bool{"success": true}
		rpcErr = nil

	default:
		log.Printf("[XATOLIK] Noma'lum metod so'raldi: %s", tempReq.Method)
		h.sendJsonRpcError(c, reqID, -32601, "Method not found", nil)
		return
	}

	if rpcErr != nil {
		log.Printf("[XATOLIK] gRPC chaqiruvida xatolik: %v", rpcErr)
		h.handleGrpcError(c, reqID, rpcErr)
		return
	}

	log.Printf("[INFO] Muvaffaqiyatli javob yuborilmoqda. Result: %+v", result)
	c.JSON(http.StatusOK, RPCResponse{JSONRPC: "2.0", ID: reqID, Result: result})
}

func (h *RPCHandler) handleGrpcError(c *gin.Context, id interface{}, err error) {
	st, ok := status.FromError(err)
	if !ok {
		log.Println("[FATAL] gRPC xatoligini status'ga o'girib bo'lmadi:", err)
		h.sendJsonRpcError(c, id, -32603, "Internal server error", nil)
		return
	}

	grpcMessage := st.Message()
	log.Printf("[INFO] gRPC xatolik xabari qabul qilindi: %s", grpcMessage)

	parts := strings.SplitN(grpcMessage, ":", 2)
	if len(parts) == 2 {
		code, err := strconv.Atoi(parts[0])
		if err == nil {
			switch code {
			case -31001:
				h.sendJsonRpcError(c, id, code, "Invalid amount", nil)
				return
			case -31003:
				h.sendJsonRpcError(c, id, code, "Transaction not found", nil)
				return
			case -31007:
				h.sendJsonRpcError(c, id, code, "Could not cancel transaction", nil)
				return
			case -31008:
				h.sendJsonRpcError(c, id, code, "Could not perform operation", nil)
				return
			case -31050:
				h.sendJsonRpcError(c, id, code, "User not found", "account")
				return
			}
		}
	}

	log.Printf("[XATOLIK] gRPC'dan noma'lum xatolik formati yoki umumiy xatolik: %s", grpcMessage)
	h.sendJsonRpcError(c, id, -32603, "Internal server error", grpcMessage)
}

func (h *RPCHandler) sendJsonRpcError(c *gin.Context, id interface{}, code int, messageKey string, data interface{}) {
	msg := MultilingualMessage{}
	switch messageKey {
	case "Invalid authorization":
		msg = MultilingualMessage{EN: "Invalid authorization", RU: "Неверная авторизация", UZ: "Noto'g'ri avtorizatsiya"}
	case "User not found":
		msg = MultilingualMessage{EN: "User not found", RU: "Пользователь не найден", UZ: "Foydalanuvchi topilmadi"}
	case "Invalid amount":
		msg = MultilingualMessage{EN: "Invalid amount", RU: "Неверная сумма", UZ: "Summa noto'g'ri"}
	case "Transaction not found":
		msg = MultilingualMessage{EN: "Transaction not found", RU: "Транзакция не найдена", UZ: "Tranzaksiya topilmadi"}
	case "Could not cancel transaction":
		msg = MultilingualMessage{EN: "The transaction cannot be cancelled", RU: "Заказ выполнен. Невозможно отменить транзакцию.", UZ: "Tranzaksiyani bekor qilib bo'lmaydi"}
	case "Could not perform operation":
		msg = MultilingualMessage{EN: "Could not perform this operation", RU: "Невозможно выполнить операцию", UZ: "Ushbu operatsiyani bajarib bo'lmadi"}
	case "Method not found":
		msg = MultilingualMessage{EN: "Method not found", RU: "Метод не найден", UZ: "Metod topilmadi"}
	case "Invalid params":
		msg = MultilingualMessage{EN: "Invalid params", RU: "Неверные параметры", UZ: "Parametrlar noto'g'ri"}
	case "Internal server error":
		msg = MultilingualMessage{EN: "Internal server error", RU: "Внутренняя ошибка сервера", UZ: "Ichki server xatosi"}
	default:
		msg = MultilingualMessage{EN: messageKey, RU: messageKey, UZ: messageKey}
	}
	log.Printf("[JAVOB] Xatolik yuborilmoqda: Code %d, Message: %s", code, messageKey)
	c.JSON(http.StatusOK, RPCResponse{JSONRPC: "2.0", ID: id, Error: &RPCError{Code: code, Message: msg, Data: data}})
}