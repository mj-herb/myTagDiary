from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON, UniqueConstraint, ForeignKey
from typing import Optional
from datetime import datetime, date, time

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)


class Diary(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # user_id: int = Field(foreign_key="user.id", index=True)
    user_id: int = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    )
    diary_date: date = Field(index=True)
    country_iso2: str = Field(index=True)
    country_name: str
    city: str = Field(index=True)
    weather: dict | None = Field(default=None, sa_column=Column(JSON))
    memo: dict | None = Field(default=None, sa_column=Column(JSON))
    photos: list | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    entries: list["DiaryEntry"] = Relationship(back_populates="diary") 



class DiaryEntryTagLink(SQLModel, table=True):
    diary_entry_id: int = Field(
        sa_column=Column(ForeignKey("diaryentry.id", ondelete="CASCADE"), primary_key=True)
    )
    tag_id: int = Field(
        sa_column=Column(ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True)
    )
    user_id: int = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    )


# diary에 생성되는 table 속 <tr> -> 시간: memo : tag 
class DiaryEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    diary_id: int = Field(
        sa_column=Column(ForeignKey("diary.id", ondelete="CASCADE"))
    )
    time_recorded: time = Field(index=True)
    memo: str | None = None

    diary: "Diary" = Relationship(back_populates="entries")
    tags: list["Tag"] = Relationship(back_populates="entries", link_model=DiaryEntryTagLink)


# 링크에는 여러 사용자가 있으니 ... user_id를 추가
class DotTagLink(SQLModel, table=True):
    dot_id: int = Field(foreign_key="dot.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)
    # user_id: int = Field(foreign_key="user.id", primary_key=True)
    user_id: int = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    )

class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    # user_id: int = Field(foreign_key="user.id")
    user_id: int = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    )
    # entries: list["DiaryEntry"] = Relationship(back_populates="tags", link_model=DiaryEntryTagLink)
    entries: list["DiaryEntry"] = Relationship(
        back_populates="tags",
        link_model=DiaryEntryTagLink,
        sa_relationship_kwargs={"cascade": "all, delete"}
    )
    dots: list["Dot"] = Relationship(
        back_populates="tags",
        link_model=DotTagLink,
        sa_relationship_kwargs={"cascade": "all, delete"}
    )
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='unique_user_tag_name'),)

# class DotReplyLink(SQLModel, table=True):
#     dot_id: int = Field(foreign_key="dot.id", primary_key=True)
#     reply_id: int = Field(foreign_key="replytodot.id", primary_key=True)
#     user_id: int = Field(foreign_key="user.id", primary_key=True)
    
class Dot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    # name: unique니까 만약 원래 있는 이름의 dot을 만들려고 하면 이미 있는 dot 입니다. 라고 나와야함
    describe: str | None = None
    tags: list["Tag"] = Relationship(
        back_populates="dots",
        link_model=DotTagLink,
        # sa_relationship_kwargs={"cascade": "delete, delete-orphan"} delete-orphan 은 many to many에서는 사용할수 없는 옵션이다.
    )
    replies: list["ReplyToDot"] = Relationship(
        back_populates="dot",
        # link_model=DotReplyLink,
    )


class ReplyToDot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"))
    )
    reply: str | None = None
    dot_id: int = Field(foreign_key="dot.id")
    dot: Dot = Relationship(back_populates="replies")
    parent_reply_id: int | None = Field(default=None, foreign_key="replytodot.id")
    parent_reply: "ReplyToDot" = Relationship(
        back_populates="child_replies",
        sa_relationship_kwargs={"remote_side": "ReplyToDot.id"}
    )
    child_replies: list["ReplyToDot"] = Relationship(back_populates="parent_reply")


# weather는 현재 사용 안함
class Weather(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    country_iso2: str = Field(index=True)
    country_name: str
    city: str = Field(index=True)
    weather_date: date = Field(index=True)
    data: dict = Field(sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('country_iso2', 'city', 'weather_date', name='uix_country_city_date'),
    )
    
    class Config:
        arbitrary_types_allowed = True

