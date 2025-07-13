import asyncio
import json
from typing import Protocol

from config import Config
from db_model.db_repo import DbRepo
from action.schemas import (
    adapter
)


class Action(Protocol):

    async def run(self, server: 'Server', reader: 'asyncio.StreamReader', writer: 'asyncio.StreamWriter'):
        pass


class Server:

    def __init__(self, db: 'DbRepo'):
        self.chats: dict[int, set[int]] = {}
        self.users: dict[int, asyncio.StreamWriter] = {}
        self.db = db

    async def start(self):
        server = await asyncio.start_server(self.handle_client, '127.0.0.1', 8888)
        addr = server.sockets[0].getsockname()
        print(f"Сервер запущен на {addr}")
        await server.serve_forever()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        print(f"Подключение от {addr}")

        while True:
            data = await reader.readline()
            if data.replace(b'\n', b''):
                print(data)
                action: Action = adapter.validate_python(json.loads(data))
                print(action)
                await action.run(self, reader, writer)


async def main():
    db_repo = DbRepo(db_url=Config.SQLALCHEMY_DATABASE_URI)
    my_server = Server(db_repo)
    await my_server.start()
