"""Migracao aditiva leve.

O projeto nao usa Alembic (escopo do TCC, banco SQLite descartavel), mas
bancos ja criados por versoes anteriores existem na maquina de quem esta
desenvolvendo. `Base.metadata.create_all` cria tabelas novas mas NAO adiciona
colunas novas em tabelas existentes — este modulo cobre exatamente esse caso.

Regras: so adiciona colunas (nunca remove nem altera tipo), sempre nullable
(SQLite recusa ADD COLUMN NOT NULL sem default constante) e com backfill
explicito quando o modelo espera valor.
"""

import logging

from sqlalchemy import inspect, text

from app.database import engine

logger = logging.getLogger(__name__)

# (tabela, coluna, DDL do tipo, SQL de backfill opcional)
_ADDED_COLUMNS: list[tuple[str, str, str, str | None]] = [
    ("users", "diagnostic_completed_at", "DATETIME", None),
    ("questions", "subject_id", "INTEGER", None),
    ("questions", "module_id", "INTEGER", None),
    ("questions", "statement_hash", "VARCHAR(64)", None),
    ("questions", "created_at", "DATETIME", "UPDATE questions SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"),
    ("questions", "active", "BOOLEAN", "UPDATE questions SET active = 1 WHERE active IS NULL"),
    ("attempts", "quiz_id", "INTEGER", None),
    ("attempts", "feedback_text", "TEXT", None),
]


def run_additive_migrations() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, column, ddl_type, backfill in _ADDED_COLUMNS:
            if table not in existing_tables:
                continue
            columns = {c["name"] for c in inspector.get_columns(table)}
            if column in columns:
                continue
            logger.info("Migracao aditiva: %s.%s", table, column)
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
            if backfill:
                conn.execute(text(backfill))
