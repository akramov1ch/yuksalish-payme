FROM python:3.10-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN pip install \
    --no-cache-dir \
    --default-timeout=300 \
    -r requirements.txt


FROM python:3.10-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

COPY . .

COPY sheetsbot-476708-5b08cf89eabf.json .

RUN mkdir -p generated
RUN python -m grpc_tools.protoc \
    -I=protos \
    --python_out=generated \
    --grpc_python_out=generated \
    protos/payment.proto protos/bot_admin.proto

RUN touch generated/__init__.py
RUN sed -i 's/^import \(.*_pb2\)/from . import \1/' generated/*_pb2_grpc.py

EXPOSE 50051

CMD ["python", "main.py"]