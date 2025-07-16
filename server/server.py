import asyncio
import json
from argparse import Action
from typing import Protocol

from action.auth_token import decode_token
from action.schemas_message import END_MARKER, BaseMessage
from config import Config
from db_model.db_repo import DbRepo
from action.schemas import (
    adapter
)
from utils.logger import get_logger

class Action(Protocol):

    async def run(self, server: 'Server', reader: 'asyncio.StreamReader', writer: 'asyncio.StreamWriter'):
        pass

    async def send_action(self, writer: 'asyncio.StreamWriter'):
        pass

class Server:

    def __init__(self, db: 'DbRepo'):
        self.chats: dict[int, set[int]] = {}
        self.users: dict[int, asyncio.StreamWriter] = {}
        self.db = db
        self.log = get_logger(self.__class__.__name__, to_file=True)
        self.log.info("Создание экзкмепляра Сервера")

    async def start(self):
        server = await asyncio.start_server(self.handle_client, '0.0.0.0', 8888)
        addr = server.sockets[0].getsockname()
        self.log.info(f"Сервер запущен на {addr}")
        chats = await self.db.get_rooms()
        for chat in chats:
            self.chats[chat.id] = set()

        await server.serve_forever()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        self.log.info(f"Подключение от {addr}")
        try:
            while True:
                data = await reader.readuntil(END_MARKER)
                self.log.info(f"Получено сообщение от {addr}")
                self.log.info(f"Данные: {data}")
                if data:
                    data = data.removesuffix(END_MARKER)
                    action: Action = adapter.validate_python(json.loads(data))
                    if token := getattr(action, 'token', None):
                        self.log.info(f"Есть токен: {token}")
                        payload = decode_token(token)
                        user_id, username = payload['id'], payload['username']
                        if user_id not in self.users:
                            user = await self.db.get_user_by_id(user_id)
                            if not user:
                                raise Exception("Невалидынй токен")
                            self.users[user_id] = writer
                    self.log.info(f"Сообщение прошло валидицию: {action}")
                    await action.run(self, reader, writer)
                elif not data:
                    break
            self.log.info(f'Пользователь {addr} отключился')
        except Exception as e:
            self.log.error(e, exc_info=True)
        finally:
            self.log.info(f"Удаляем пользователя {addr}")

    async def all_broadcast(self, message: BaseMessage):
        self.log.info(f"Оповещаем всех {message}")
        for user_id in self.users:
            writer = self.users[user_id]
            await message.send_message(writer)

    async def send_in_chats(self, message: BaseMessage, room_id: int):
        self.log.info(f"Оповещаем в комнате {room_id} {message}")
        for user_id in self.chats[room_id]:
            if writer := self.users.get(user_id):
                await message.send_message(writer)

async def main():
    db_repo = DbRepo(db_url=Config.SQLALCHEMY_DATABASE_URI)
    my_server = Server(db_repo)
    await my_server.start()
