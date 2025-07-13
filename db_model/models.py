import datetime
from typing import List

from sqlalchemy import ForeignKey, UniqueConstraint, engine
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str] = mapped_column()

    rooms: Mapped[List['Membership']] = relationship(
        back_populates='user'
    )
    messages: Mapped[List['Message']] = relationship(
        back_populates='user'
    )


class ChatRoom(Base):
    __tablename__ = 'chat_rooms'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    users: Mapped[List['Membership']] = relationship(
        back_populates='room'
    )
    messages: Mapped[List['Message']] = relationship(
        back_populates='room'
    )

class PrivateRoom(Base):
    __tablename__ = 'private_rooms'

    user1_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    user2_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey('chat_rooms.id'), unique=True)

    __table_args__ = (
        UniqueConstraint('user1_id', 'user2_id'),
    )

    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])
    room = relationship("ChatRoom")




class Membership(Base):
    __tablename__ = 'memberships'

    id_user: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    id_room: Mapped[int] = mapped_column(ForeignKey('chat_rooms.id'), primary_key=True)

    __table_args__ = (
        UniqueConstraint('id_room', 'id_user'),
    )

    user: Mapped[User] = relationship(back_populates='rooms')
    room: Mapped[ChatRoom] = relationship(back_populates='users')


class Message(Base):
    __tablename__ = 'messages'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    room_id: Mapped[int] = mapped_column(ForeignKey('chat_rooms.id'))
    message: Mapped[str]
    timestamp: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)

    user: Mapped[User] = relationship(
        back_populates='messages'
    )
    room: Mapped[ChatRoom] = relationship(
        back_populates='messages'
    )
