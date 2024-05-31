-- Create the 'postgres' role with all permissions for langfuse
CREATE ROLE postgres WITH LOGIN PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE postgres TO postgres;
-- Create the database
CREATE DATABASE aisheAI;