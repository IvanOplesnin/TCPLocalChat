import hashlib
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute, joinedload

from db_model.models import User, ChatRoom, Membership, Message, PrivateRoom
from action.schemas import RegisterAction, AuthorizeAction, JoinUserAction, SendAction
from action.auth_token import decode_token
from utils.logger import get_logger


class DbRepo:

    def __init__(self, db_url: str):
        self.async_engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(
            bind=self.async_engine, expire_on_commit=False, class_=AsyncSession
        )
        self.log = get_logger(self.__class__.__name__, to_file=True)

    async def new_user(self, action: RegisterAction):
        async with self.async_session() as session:
            hash_password = hashlib.sha256(action.password.encode()).hexdigest()
            new_user = User(
                username=action.username,
                password_hash=hash_password,
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            return new_user

    async def get_user(self, action: AuthorizeAction):
        async with self.async_session() as session:
            hash_password = hashlib.sha256(action.password.encode()).hexdigest()
            stmt = select(User).where(User.username == action.username)
            user = await session.execute(stmt)
            user = user.scalars().first()
            if user is None:
                raise Exception(f'User {action.username} not found')
            if user.password_hash != hash_password:
                raise Exception(f'Password mismatch')
            return user

    async def new_room_privat(self, action: JoinUserAction) -> ChatRoom | None:
        async with self.async_session() as session:
            payload = decode_token(action.token)
            username = payload['username']
            stmt = select(User).where(User.id == action.user_id)
            user_2 = await session.execute(stmt)
            user_2 = user_2.scalars().first()
            if user_2 is None:
                raise Exception(f"User with ID {action.user_id} not found")
            tup_user_1, tup_user_2 = sorted(
                [(payload['id'], payload['username']),
                 (user_2.id, user_2.username)],
                key=lambda p: p[0],
            )
            id_1, id_2 = tup_user_1[0], tup_user_2[0]
            stmt = select(PrivateRoom).where(
                PrivateRoom.user1_id == id_1,
                PrivateRoom.user2_id == id_2
            )
            existing_private_room = await session.execute(stmt)
            existing_private_room = existing_private_room.scalars().first()
            if existing_private_room:
                self.log.info(
                    f"Найдена существующая комната[{existing_private_room.room_id}] между {id_1}, {id_2}"
                )
                chat_room = await session.get(ChatRoom, existing_private_room.room_id)
                return chat_room

            new_chat_room = ChatRoom(
                name=f'Chat: {username} <-> {user_2.username}',
            )
            session.add(new_chat_room)
            await session.commit()

            new_membership_list = [
                Membership(id_user=u_id, id_room=new_chat_room.id) for u_id in [id_1, id_2]
            ]
            session.add_all(new_membership_list)
            await session.commit()
            session.add(PrivateRoom(user1_id=id_1, user2_id=id_2, room_id=new_chat_room.id))
            await session.commit()
            self.log.info(f"Создана новая комната {new_chat_room.id} между {id_1} и {id_2}")
            await session.refresh(new_chat_room)
            return new_chat_room

    async def send_message(self, user_id: int, room_id: int, message: str):
        async with self.async_session() as session:
            new_message = Message(
                room_id=room_id,
                user_id=user_id,
                message=message
            )
            session.add(new_message)
            await session.commit()
            await session.refresh(new_message)
            return new_message

    async def get_room(self, action: SendAction):
        async with self.async_session() as session:
            stmt = select(ChatRoom).where(ChatRoom.id == action.room)
            room = await session.execute(stmt)
            room = room.scalars().first()
            return room

    async def get_user_by_id(self, user_id: int):
        async with self.async_session() as session:
            stmt = select(User).where(User.id == user_id)
            user = await session.execute(stmt)
            user = user.scalars().first()
            return user

    async def get_all_users(self):
        async with self.async_session() as session:
            stmt = select(User)
            users = await session.execute(stmt)
            users = users.scalars().all()
            return users

    async def get_chats_user(self, user_id: int) -> Sequence[ChatRoom]:
        async with self.async_session() as session:
            stmt = (
                select(ChatRoom)
                .join(Membership, Membership.id_room == ChatRoom.id)
                .where(Membership.id_user == user_id)
                .options(
                    joinedload(ChatRoom.users)
                    .joinedload(Membership.user)
                )
            )

            result = await session.scalars(stmt)
            return result.all()


    async def get_messages(self, room_id: int) -> Sequence[Message]:
        async with self.async_session() as session:
            stmt = select(Message).where(Message.room_id == room_id)
            result = await session.execute(stmt)
            return result.scalars().all()


if __name__ == '__main__':
    from config import Config
    db_r = DbRepo(Config.SQLALCHEMY_DATABASE_URI)
