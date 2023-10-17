-- Connect to the newly created database
\c aisheAI;

-- Enable the vector extension
CREATE EXTENSION vector;

-- -- Create the items table with a vector column
-- CREATE TABLE items (id bigserial PRIMARY KEY, embedding vector(3));
