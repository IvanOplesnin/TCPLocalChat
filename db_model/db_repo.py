import hashlib
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute, joinedload

from db_model.models import User, ChatRoom, Membership, Message, PrivateRoom
from action.schemas import RegisterAction, AuthorizeAction, JoinUserAction, SendAction
from action.auth_token import decode_token


class DbRepo:

    def __init__(self, db_url: str):
        self.async_engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(
            bind=self.async_engine, expire_on_commit=False, class_=AsyncSession
        )

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


    async def new_room(self, action: JoinUserAction):
        async with self.async_session() as session:
            payload = decode_token(action.token)
            user_1_id, user_2_id = sorted([payload['id'], action.user_id])
            username = payload['username']
            stmt = select(User).where(User.id == action.user_id)
            user_2 = await session.execute(stmt)
            user_2 = user_2.scalars().first()
            if user_2 is None:
                raise Exception(f"User with ID {action.user_id} not found")

            stmt = select(PrivateRoom).where(
                PrivateRoom.user1_id == user_1_id,
                PrivateRoom.user2_id == user_2_id
            )
            existing_private_room = await session.execute(stmt)
            existing_private_room = existing_private_room.scalars().first()
            if existing_private_room:
                chat_room = await session.get(ChatRoom, existing_private_room.room_id)
                return chat_room

            new_chat_room = ChatRoom(
                name=f'Chat: {username} <-> {user_2.username}',
            )
            session.add(new_chat_room)
            await session.commit()
            await session.refresh(new_chat_room)
            new_membership_list = [
                Membership(id_user=u_id, id_room=new_chat_room.id) for u_id in [user_1_id, user_2.id]
            ]
            session.add_all(new_membership_list)
            await session.commit()
            session.add(PrivateRoom(user1_id=user_1_id, user2_id=user_2_id, room_id=new_chat_room.id))
            await session.commit()
            print(f"Создана новая комната {new_chat_room.id} между {user_1_id} и {user_2.id}")
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



