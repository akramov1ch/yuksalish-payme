CREATE TABLE IF NOT EXISTS students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(20) UNIQUE,
    branch_id UUID NOT NULL REFERENCES branches(id),
    parent_name VARCHAR(255) NOT NULL,
    discount_percent NUMERIC(5, 2) DEFAULT 0.0,
    balance BIGINT DEFAULT 0,
    full_name VARCHAR(255),
    group_name VARCHAR(100),
    phone VARCHAR(255), -- O'ZGARTIRILDI: VARCHAR(20) dan VARCHAR(255) ga
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);