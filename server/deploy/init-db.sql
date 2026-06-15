-- Optional hardening: run as the Postgres superuser to create a least-privilege
-- application role that owns nothing it doesn't need. Point DATABASE_URL at this
-- role instead of the superuser created by the postgres image.
--
--   psql -U postgres -d giphery -f init-db.sql
--
-- Then set in .env:
--   POSTGRES_USER=giphery_app  (and the password below)
--
-- The role can CRUD application data but cannot create/drop databases or roles.
-- Run Alembic migrations with a higher-privileged role (it needs DDL), then have
-- the app connect as giphery_app.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'giphery_app') THEN
        CREATE ROLE giphery_app LOGIN PASSWORD 'change-me-app-password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE giphery TO giphery_app;
GRANT USAGE ON SCHEMA public TO giphery_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO giphery_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO giphery_app;

-- Apply automatically to tables/sequences created by future migrations.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO giphery_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO giphery_app;
