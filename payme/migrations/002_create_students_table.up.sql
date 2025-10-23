CREATE TABLE IF NOT EXISTS students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(20) UNIQUE,
    branch_id UUID NOT NULL,
    parent_name VARCHAR(255),
    discount_percent NUMERIC(5, 2) DEFAULT 0.00,
    balance BIGINT DEFAULT 0,
    full_name VARCHAR(255),
    group_name VARCHAR(255),
    phone VARCHAR(20),
    jshshir VARCHAR(14) UNIQUE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_branch
        FOREIGN KEY(branch_id) 
        REFERENCES branches(id) 
        ON DELETE CASCADE
);