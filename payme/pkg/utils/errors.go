package utils

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

func (e RPCError) Error() string {
	return e.Message.RU
}

var (
	ErrInvalidAmount = RPCError{Code: -31001, Message: MultilingualMessage{
		EN: "Invalid amount",
		RU: "Неверная сумма",
		UZ: "Summa noto'g'ri"},
	}

	ErrTransactionNotFound = RPCError{Code: -31003, Message: MultilingualMessage{
		EN: "Transaction not found",
		RU: "Транзакция не найдена",
		UZ: "Tranzaksiya topilmadi"},
	}

	ErrCouldNotCancel = RPCError{Code: -31007, Message: MultilingualMessage{
		EN: "The transaction cannot be cancelled",
		RU: "Заказ выполнен. Невозможно отменить транзакцию.",
		UZ: "Tranzaksiyani bekor qilib bo'lmaydi"},
	}

	ErrCouldNotPerform = RPCError{Code: -31008, Message: MultilingualMessage{
		EN: "Could not perform this operation",
		RU: "Невозможно выполнить операцию",
		UZ: "Ushbu operatsiyani bajarib bo'lmadi"},
	}

	ErrUserNotFound = RPCError{Code: -31050, Message: MultilingualMessage{
		EN: "User not found",
		RU: "Пользователь не найден",
		UZ: "Foydalanuvchi topilmadi"},
		Data: "account",
	}

	ErrInvalidParams = RPCError{Code: -32602, Message: MultilingualMessage{
		EN: "Invalid params",
		RU: "Неверные параметры",
		UZ: "Parametrlar noto'g'ri"},
	}

	ErrInternalServer = RPCError{Code: -32603, Message: MultilingualMessage{
		EN: "Internal server error",
		RU: "Внутренняя ошибка сервера",
		UZ: "Ichki server xatosi"},
	}
)