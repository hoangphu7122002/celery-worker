# Flyway Migrations

SQL-based migrations with Flyway instead of Alembic. Reference: `.cursor/rules/flyway-migrations.mdc`.

## Folder layout

```
db/
  migration/
    V1__create_tables.sql
    V2__add_column.sql
```

Naming: `V<version>__<description>.sql` (double underscore).

## CLI usage

```bash
# Flyway expects JDBC URL for PostgreSQL
flyway -url=jdbc:postgresql://host:5432/dbname -user=user -password=secret -locations=filesystem:db/migration migrate
```

Convert `postgresql://user:pass@host:5432/db` to `jdbc:postgresql://host:5432/db` and pass `-user`, `-password` separately, or use `-url` with embedded credentials in JDBC format.

## Docker

```bash
docker run --rm -v $(pwd)/db/migration:/flyway/sql \
  -e FLYWAY_URL=jdbc:postgresql://host:5432/db \
  -e FLYWAY_USER=user -e FLYWAY_PASSWORD=secret \
  flyway/flyway migrate
```

## Azure migration job

Use `flyway/flyway` image; mount migrations or bake into image. Command:

```
flyway -url=$DATABASE_URL -locations=filesystem:/flyway/sql migrate
```

Ensure `DATABASE_URL` is converted to JDBC format if Flyway expects it. Run job before deploy; see [azure-deploy-full](.cursor/rules/azure-deploy-full.mdc) for build→migrate→deploy flow.
