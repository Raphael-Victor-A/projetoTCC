from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

database_url = settings.database_url
# Provedores como Render/Neon/Heroku entregam "postgres://", que o
# SQLAlchemy 2 nao aceita mais.
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
# pool_pre_ping + pool_recycle: o Neon suspende o compute ocioso (scale to zero)
# e derruba conexoes paradas; testa/renova antes de usar. Em producao use a URL
# "-pooler" do Neon (PgBouncer), que aguenta muitas conexoes.
engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
