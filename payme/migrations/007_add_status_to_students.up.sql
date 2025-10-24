ALTER TABLE students
ADD COLUMN status BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN students.status IS 'Talabaning holati: TRUE - o''qimoqda, FALSE - o''qishni tugatgan/ketgan';