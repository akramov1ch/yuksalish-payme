package utils

import (
	"encoding/json"
)

type RPCRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params"`
	ID      interface{}     `json:"id"`
}

type RPCResponse struct {
	JSONRPC string      `json:"jsonrpc"`
	Result  interface{} `json:"result"`
	ID      interface{} `json:"id"`
}

type RPCErrorResponse struct {
	JSONRPC string   `json:"jsonrpc"`
	Error   RPCError `json:"error"`
	ID      interface{} `json:"id"`
}

func NewRPCSuccessResponse(id interface{}, result interface{}) RPCResponse {
	return RPCResponse{
		JSONRPC: "2.0",
		ID:      id,
		Result:  result,
	}
}

func NewRPCErrorResponse(id interface{}, err RPCError) RPCErrorResponse {
	return RPCErrorResponse{
		JSONRPC: "2.0",
		ID:      id,
		Error:   err,
	}
}