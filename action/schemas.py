import asyncio
import datetime
import json
from enum import Enum
from typing import Optional, Literal, Annotated, Union, TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field, TypeAdapter

from db_model.models import User, ChatRoom
from action.auth_token import create_token, decode_token
from action.schemas_message import (
    Message,
    InitMessage,
    UpdateMessage,
    TokenMessage,
    TypeMessage, UserBrief, UpdateKind, END_MARKER
)
from utils.logger import get_logger

if TYPE_CHECKING:
    from server.server import Server


class Command(str, Enum):
    JOIN_CHAT = 'JOIN_CHAT'
    JOIN_GROUP = 'JOIN_GROUP'
    JOIN_USER = 'JOIN_USER'
    SEND = 'SEND'
    LEAVE = 'LEAVE'
    JOIN_SERVER = 'JOIN_SERVER'
    REGISTER = 'REGISTER'
    AUTHORIZE = 'AUTHORIZE'


class BaseAction(BaseModel):
    token: str
    command: Command

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self.model_dump()}>'

    def _to_bytes(self) -> bytes:
        return json.dumps(self.model_dump()).encode() + END_MARKER

    async def send_action(self, writer: 'asyncio.StreamWriter'):
        writer.write(self._to_bytes())
        await writer.drain()
        self.log.info(f"Отправлена информация {json.dumps(self.model_dump())}")


class RegisterAction(BaseAction):
    command: Literal[Command.REGISTER]
    username: str
    password: str
    token: Optional[str] = None

    async def run(self, server: "Server", _: 'asyncio.StreamReader', writer: 'asyncio.StreamWriter'):
        try:
            new_user: User = await server.db.new_user(self)
            all_users = await server.db.get_all_users()
            users = [UserBrief(id=u.id, username=u.username) for u in all_users]
            server.users[new_user.id] = writer
            auth_token = create_token(new_user)
            token_message = TokenMessage(content=auth_token, type=TypeMessage.token)
            init_message = InitMessage(
                self_user={"id": new_user.id, "username": new_user.username},
                type=TypeMessage.init,
                rooms=[],
                all_users=users,
                online_users=[u for u in users if u.id in server.users],
            )
            update_message = UpdateMessage(
                kind=UpdateKind.user_online,
                payload={"id": new_user.id, "username": new_user.username},
                type=TypeMessage.update,
            )
            await token_message.send_message(writer)
            await init_message.send_message(writer)
            await update_message.send_message(writer)
            server.log.info(f"Отправлено {token_message}")
            server.log.info(f"Отправлено {init_message}")
            server.log.info(f"Отправлено {update_message}")
            return new_user
        except Exception as e:
            self.log.info(f'{str(e)}')
            writer.write(str(e).encode())


class AuthorizeAction(BaseAction):
    command: Literal[Command.AUTHORIZE]
    username: str
    password: str
    token: Optional[str] = None

    async def run(self, server: "Server", _: 'asyncio.StreamReader', writer: 'asyncio.StreamWriter'):
        try:
            user: User = await server.db.get_user(self)
            server.users[user.id] = writer
            auth_token = create_token(user)
            token_message = TokenMessage(content=auth_token)
            await token_message.send_message(writer)
        except Exception as e:
            writer.write(e.args[1].encode())


class JoinServerAction(BaseAction):
    command: Literal[Command.JOIN_SERVER]

    async def run(self, server: "Server", _: 'asyncio.StreamReader', writer: 'asyncio.StreamWriter'):
        try:
            payload = decode_token(self.token)
            user_id, username = payload['id'], payload['username']
            user = await server.db.get_user_by_id(user_id)
            if user and user.username == username:
                server.users[user_id.id] = writer
            else:
                raise Exception(f'User not found, maybe old token')
        except Exception as e:

            writer.write(e.args[1].encode())


class JoinChatAction(BaseAction):
    command: Literal[Command.JOIN_CHAT]
    room: int
    message: Optional[str] = None


class JoinGroupAction(BaseAction):
    command: Literal[Command.JOIN_GROUP]
    room: int
    message: Optional[str] = None


class JoinUserAction(BaseAction):
    command: Literal[Command.JOIN_USER]
    user_id: int
    message: Optional[str] = None

    async def run(self, server: "Server", _: 'asyncio.StreamReader', writer: 'asyncio.StreamWriter'):
        try:
            new_room: ChatRoom = await server.db.new_room(self)
            payload = decode_token(self.token)
            user_id, username = payload['id'], payload['username']
            server.chats[new_room.id] = {self.user_id, user_id}
            mes = f'{username} хочет с вами поболтать\n'
            if self.message:
                mes += f'{self.message}\n'
            new_message = Message(
                content=mes,
                from_=user_id,
                from_username=username,
                room_id=new_room.id,
                time_=datetime.datetime.now().strftime("%H:%M:%S"),
                type=TypeMessage.message
            )

            for user in server.chats[new_room.id]:
                user_writer = server.users.get(user)
                if user_writer:
                    await new_message.send_message(user_writer)

            await server.db.send_message(user_id, new_room.id, mes)
        except Exception as e:
            writer.write(e.args[1].encode())


class SendAction(BaseAction):
    command: Literal[Command.SEND]
    room: int
    message: str

    async def run(self, server: "Server", _: 'asyncio.StreamReader', writer: 'asyncio.StreamWriter'):
        try:
            room: ChatRoom = await server.db.get_room(self)
            payload = decode_token(self.token)
            user_id, username = payload['id'], payload['username']
            mes = f'{self.message}'
            new_message = Message(
                content=mes,
                from_=user_id,
                from_username=username,
                room_id=room.id,
                time_=datetime.datetime.now().strftime("%H:%M:%S"),
                type=TypeMessage.message
            )
            for user in server.chats[room.id]:
                user_writer = server.users.get(user)
                if user_writer:
                    await new_message.send_message(user_writer)

            saved_message = await server.db.send_message(user_id, self.room, mes)
        except Exception as e:
            writer.write(e.args[1].encode())


class LeaveAction(BaseAction):
    command: Literal[Command.LEAVE]
    room: int
    message: Optional[str] = None


ActionUnion = Annotated[
    Union[
        JoinChatAction,
        JoinGroupAction,
        JoinUserAction,
        JoinServerAction,
        SendAction,
        LeaveAction,
        RegisterAction,
        AuthorizeAction
    ],
    Field(discriminator='command')
]
adapter = TypeAdapter(ActionUnion)

if __name__ == '__main__':
    data = {
        'command': 'JOIN',
        'room': 1,
    }
    # action = adapter.validate_python(data)
    # print(action.command)
    # print(action.room)
    # print(type(action))

    import json

    data = json.dumps(data, indent=4).encode()
    print(type(data))

    new_data = (json.loads(data.decode()))
    print(type(new_data))
    print(new_data)
