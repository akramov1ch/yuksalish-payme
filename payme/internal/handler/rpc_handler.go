package handler

import (
	"encoding/json"
	"io"
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/go-playground/validator/v10"
	"payme/internal/service"
	"payme/pkg/utils"
)

type RPCHandler struct {
	paymentService service.PaymentService
	validate       *validator.Validate
}

func NewRPCHandler(paymentService service.PaymentService) *RPCHandler {
	return &RPCHandler{
		paymentService: paymentService,
		validate:       validator.New(),
	}
}

func (h *RPCHandler) RegisterRoutes(router *gin.Engine) {
	router.POST("/rpc", h.handleRequest)
}

func (h *RPCHandler) handleRequest(c *gin.Context) {
	body, err := io.ReadAll(c.Request.Body)
	if err != nil {
		c.JSON(http.StatusOK, utils.NewRPCErrorResponse(nil, utils.ErrInvalidParams))
		return
	}

	var rpcRequest utils.RPCRequest
	if err := json.Unmarshal(body, &rpcRequest); err != nil {
		c.JSON(http.StatusOK, utils.NewRPCErrorResponse(nil, utils.ErrInvalidParams))
		return
	}

	switch rpcRequest.Method {
	case "CheckPerformTransaction":
		h.handleCheckPerformTransaction(c, rpcRequest)
	case "CreateTransaction":
		h.handleCreateTransaction(c, rpcRequest)
	case "PerformTransaction":
		h.handlePerformTransaction(c, rpcRequest)
	case "CancelTransaction":
		h.handleCancelTransaction(c, rpcRequest)
	case "CheckTransaction":
		h.handleCheckTransaction(c, rpcRequest)
	case "GetStatement":
		h.handleGetStatement(c, rpcRequest)
	default:
		h.sendResponse(c, rpcRequest.ID, nil, utils.ErrInternalServer)
	}
}

func (h *RPCHandler) handleCheckPerformTransaction(c *gin.Context, req utils.RPCRequest) {
	var params service.CheckPerformTransactionParams
	if h.decodeAndValidate(req.Params, &params) != nil {
		h.sendResponse(c, req.ID, nil, utils.ErrInvalidParams)
		return
	}
	result, err := h.paymentService.CheckPerformTransaction(c.Request.Context(), params)
	h.sendResponse(c, req.ID, result, err)
}

func (h *RPCHandler) handleCreateTransaction(c *gin.Context, req utils.RPCRequest) {
	var params service.CreateTransactionParams
	if h.decodeAndValidate(req.Params, &params) != nil {
		h.sendResponse(c, req.ID, nil, utils.ErrInvalidParams)
		return
	}
	result, err := h.paymentService.CreateTransaction(c.Request.Context(), params)
	h.sendResponse(c, req.ID, result, err)
}

func (h *RPCHandler) handlePerformTransaction(c *gin.Context, req utils.RPCRequest) {
	var params service.TransactionParams
	if h.decodeAndValidate(req.Params, &params) != nil {
		h.sendResponse(c, req.ID, nil, utils.ErrInvalidParams)
		return
	}
	result, err := h.paymentService.PerformTransaction(c.Request.Context(), params)
	h.sendResponse(c, req.ID, result, err)
}

func (h *RPCHandler) handleCancelTransaction(c *gin.Context, req utils.RPCRequest) {
	var params service.TransactionParams
	if h.decodeAndValidate(req.Params, &params) != nil {
		h.sendResponse(c, req.ID, nil, utils.ErrInvalidParams)
		return
	}
	result, err := h.paymentService.CancelTransaction(c.Request.Context(), params)
	h.sendResponse(c, req.ID, result, err)
}

func (h *RPCHandler) handleCheckTransaction(c *gin.Context, req utils.RPCRequest) {
	var params service.TransactionParams
	if h.decodeAndValidate(req.Params, &params) != nil {
		h.sendResponse(c, req.ID, nil, utils.ErrInvalidParams)
		return
	}
	result, err := h.paymentService.CheckTransaction(c.Request.Context(), params)
	h.sendResponse(c, req.ID, result, err)
}

func (h *RPCHandler) handleGetStatement(c *gin.Context, req utils.RPCRequest) {
	var params service.GetStatementParams
	if h.decodeAndValidate(req.Params, &params) != nil {
		h.sendResponse(c, req.ID, nil, utils.ErrInvalidParams)
		return
	}
	result, err := h.paymentService.GetStatement(c.Request.Context(), params)
	h.sendResponse(c, req.ID, result, err)
}

func (h *RPCHandler) decodeAndValidate(params json.RawMessage, target interface{}) error {
	if len(params) == 0 || json.Unmarshal(params, target) != nil || h.validate.Struct(target) != nil {
		return utils.ErrInvalidParams
	}
	return nil
}

func (h *RPCHandler) sendResponse(c *gin.Context, id interface{}, result interface{}, err error) {
	if err != nil {
		if rpcErr, ok := err.(utils.RPCError); ok {
			c.JSON(http.StatusOK, utils.NewRPCErrorResponse(id, rpcErr))
		} else {
			log.Printf("ERROR: Unhandled internal error: %v", err)
			c.JSON(http.StatusOK, utils.NewRPCErrorResponse(id, utils.ErrInternalServer))
		}
		return
	}
	c.JSON(http.StatusOK, utils.NewRPCSuccessResponse(id, result))
}