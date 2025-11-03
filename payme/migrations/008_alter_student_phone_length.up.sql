-- payme/migrations/008_alter_student_phone_length.up.sql
ALTER TABLE students
ALTER COLUMN phone TYPE VARCHAR(255);