import grpc
from generated import payment_pb2, payment_pb2_grpc
from google.protobuf import empty_pb2
from config import settings
import logging

logger = logging.getLogger(__name__)

def get_management_stub():
    try:
        channel = grpc.insecure_channel(settings.grpc_go_server_address)
        return payment_pb2_grpc.ManagementServiceStub(channel)
    except Exception as e:
        logger.error(f"gRPC kanalini yaratishda xatolik: {e}")
        return None

def list_branches():
    stub = get_management_stub()
    if not stub:
        return None, "gRPC serveriga ulanib bo'lmadi."
    try:
        response = stub.ListBranches(empty_pb2.Empty())
        return response.branches, None
    except grpc.RpcError as e:
        logger.error(f"Filiallar ro'yxatini olishda gRPC xatoligi: {e.details()}")
        return None, f"gRPC xatoligi: {e.details()}"

def list_branches_with_student_counts():
    stub = get_management_stub()
    if not stub:
        return None, "gRPC serveriga ulanib bo'lmadi."
    try:
        branches_response = stub.ListBranches(empty_pb2.Empty())
        students_response = stub.ListStudents(payment_pb2.ListRequest())
        student_counts = {}
        for student in students_response.students:
            student_counts[student.branch_id] = student_counts.get(student.branch_id, 0) + 1
        result = []
        for branch in branches_response.branches:
            count = student_counts.get(branch.id, 0)
            result.append({"branch": branch, "student_count": count})
        return result, None
    except grpc.RpcError as e:
        logger.error(f"Filiallar ro'yxatini olishda gRPC xatoligi: {e.details()}")
        return None, f"gRPC xatoligi: {e.details()}"

def create_branch(data):
    stub = get_management_stub()
    if not stub:
        return None, "gRPC serveriga ulanib bo'lmadi."
    try:
        request = payment_pb2.CreateBranchRequest(
            name=data['name'],
            monthly_fee=int(data['monthly_fee']),
            mfo_code=data['mfo_code'],
            account_number=data['account_number'],
            merchant_id=data['merchant_id']
        )
        response = stub.CreateBranch(request)
        return response, None
    except grpc.RpcError as e:
        logger.error(f"Filial yaratishda gRPC xatoligi: {e.details()}")
        return None, f"gRPC xatoligi: {e.details()}"

def delete_branch(branch_id: str):
    stub = get_management_stub()
    if not stub:
        return False, "gRPC serveriga ulanib bo'lmadi."
    try:
        request = payment_pb2.ByIdRequest(id=branch_id)
        stub.DeleteBranch(request)
        return True, None
    except grpc.RpcError as e:
        logger.error(f"Filialni o'chirishda gRPC xatoligi: {e.details()}")
        if "foreign key constraint" in e.details():
            return False, "Bu filialga o'quvchilar biriktirilgan. Avval o'quvchilarni o'chiring yoki boshqa filialga o'tkazing."
        return False, f"gRPC xatoligi: {e.details()}"

def list_students():
    stub = get_management_stub()
    if not stub:
        return None, "gRPC serveriga ulanib bo'lmadi."
    try:
        response = stub.ListStudents(payment_pb2.ListRequest())
        return response.students, None
    except grpc.RpcError as e:
        logger.error(f"O'quvchilar ro'yxatini olishda gRPC xatoligi: {e.details()}")
        return None, f"gRPC xatoligi: {e.details()}"

def create_student(data):
    stub = get_management_stub()
    if not stub:
        return None, "gRPC serveriga ulanib bo'lmadi."
    try:
        request = payment_pb2.CreateStudentRequest(
            account_id=data.get('account_id', ""),
            branch_id=data['branch_id'],
            parent_name=data['parent_name'],
            full_name=data['full_name'],
            group_name=data['group_name'],
            phone=data['phone'],
            discount_percent=data['discount_percent'],
            contract_number=data.get('contract_number', "")
        )
        response = stub.CreateStudent(request)
        return response, None
    except grpc.RpcError as e:
        logger.error(f"O'quvchi yaratishda gRPC xatoligi: {e.details()}")
        return None, f"gRPC xatoligi: {e.details()}"

def delete_student_by_account_id(account_id: str):
    stub = get_management_stub()
    if not stub:
        return None, "gRPC serveriga ulanib bo'lmadi."
    try:
        request = payment_pb2.ByAccountIdRequest(account_id=account_id)
        stub.DeleteStudentByAccountId(request)
        return True, None
    except grpc.RpcError as e:
        logger.error(f"O'quvchini o'chirishda gRPC xatoligi: {e.details()}")
        if e.code() == grpc.StatusCode.NOT_FOUND or "no student found" in e.details():
            return None, f"'{account_id}' hisob raqamli o'quvchi topilmadi."
        return None, f"gRPC xatoligi: {e.details()}"

def get_student_by_account_id(account_id: str):
    stub = get_management_stub()
    if not stub:
        return None, "gRPC serveriga ulanib bo'lmadi."
    try:
        request = payment_pb2.ByAccountIdRequest(account_id=account_id)
        response = stub.GetStudentByAccountId(request)
        return response, None
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return None, f"'{account_id}' hisob raqamli o'quvchi topilmadi."
        logger.error(f"O'quvchini olishda gRPC xatoligi: {e.details()}")
        return None, f"gRPC xatoligi: {e.details()}"

def update_student(student_data):
    stub = get_management_stub()
    if not stub:
        return None, "gRPC serveriga ulanib bo'lmadi."
    try:
        request = payment_pb2.Student(**student_data)
        response = stub.UpdateStudent(request)
        return response, None
    except grpc.RpcError as e:
        logger.error(f"O'quvchini yangilashda gRPC xatoligi: {e.details()}")
        return None, f"gRPC xatoligi: {e.details()}"

def create_students_batch(students_data: list):
    stub = get_management_stub()
    if not stub:
        return None, "gRPC serveriga ulanib bo'lmadi."
    
    if not students_data:
        return [], None

    try:
        grpc_students = [
            payment_pb2.CreateStudentRequest(
                branch_id=s['branch_id'],
                parent_name=s['parent_name'],
                full_name=s['full_name'],
                group_name=s['group_name'],
                phone=s['phone'],
                discount_percent=s.get('discount_percent', 0.0),
                contract_number=s.get('contract_number', "")
            ) for s in students_data
        ]
        
        request = payment_pb2.CreateStudentsBatchRequest(students=grpc_students)
        response = stub.CreateStudentsBatch(request)
        return response.students, None
        
    except grpc.RpcError as e:
        logger.error(f"O'quvchilarni ommaviy yaratishda gRPC xatoligi: {e.details()}")
        return None, f"gRPC xatoligi: {e.details()}"
    except Exception as e:
        logger.error(f"O'quvchilarni ommaviy yaratishda kutilmagan xatolik: {e}", exc_info=True)
        return None, str(e)

# YANGI FUNKSIYA
def update_students_batch(students_data: list):
    stub = get_management_stub()
    if not stub:
        return False, "gRPC serveriga ulanib bo'lmadi."
    
    if not students_data:
        return True, None

    try:
        grpc_students = [payment_pb2.Student(**s) for s in students_data]
        request = payment_pb2.UpdateStudentsBatchRequest(students=grpc_students)
        stub.UpdateStudentsBatch(request)
        return True, None
    except grpc.RpcError as e:
        logger.error(f"O'quvchilarni ommaviy yangilashda gRPC xatoligi: {e.details()}")
        return False, f"gRPC xatoligi: {e.details()}"
    except Exception as e:
        logger.error(f"O'quvchilarni ommaviy yangilashda kutilmagan xatolik: {e}", exc_info=True)
        return False, str(e)

def delete_students_batch(account_ids: list):
    stub = get_management_stub()
    if not stub:
        return False, "gRPC serveriga ulanib bo'lmadi."
    
    try:
        request = payment_pb2.DeleteStudentsBatchRequest(account_ids=account_ids)
        stub.DeleteStudentsBatch(request)
        return True, None
    except grpc.RpcError as e:
        logger.error(f"O'quvchilarni ommaviy o'chirishda gRPC xatoligi: {e.details()}")
        return False, f"gRPC xatoligi: {e.details()}"
    except Exception as e:
        logger.error(f"O'quvchilarni ommaviy o'chirishda kutilmagan xatolik: {e}")
        return False, str(e)