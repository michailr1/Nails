\getenv app_user APP_DB_USER
\getenv app_password APP_DB_PASSWORD

SELECT format(
  'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
  :'app_user',
  :'app_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user')
\gexec

SELECT format('ALTER DATABASE %I OWNER TO %I', current_database(), :'app_user')
\gexec

SELECT format('ALTER SCHEMA public OWNER TO %I', :'app_user')
\gexec

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'app_user')
\gexec
