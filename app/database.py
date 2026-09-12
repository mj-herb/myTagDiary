from sqlmodel import create_engine, SQLModel, Session

DATABASE_URL = "postgresql://mj:0000@127.0.0.1/diary"
engine = create_engine(DATABASE_URL, echo=True)

def create_db_and_tables():
    from .models import User
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session