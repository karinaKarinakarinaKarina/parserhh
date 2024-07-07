-- init.sql
-- CREATE DATABASE vacancies_db;

\c vacancies_db;

CREATE TABLE IF NOT EXISTS vacancies (
    id SERIAL PRIMARY KEY,
    vacancy_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    professional_roles VARCHAR(255),
    employer VARCHAR(255) NOT NULL,
    salary_from INTEGER,
    salary_to INTEGER,
    currency VARCHAR(255) NOT NULL,
    experience VARCHAR(255) NOT NULL,
    employment VARCHAR(255) NOT NULL,
    area VARCHAR(255),
    metro_stations VARCHAR(255),
    url VARCHAR(255) NOT NULL,
    responsibility TEXT
);