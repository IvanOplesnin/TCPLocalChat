import asyncio
import json
import threading
from concurrent.futures.thread import ThreadPoolExecutor
from queue import Queue

from action.schemas_message import Message, UpdateMessage, InitMessage, TokenMessage, END_MARKER, message_adapter, \
    BaseMessage
from server.server import Action
from gui_client.client_logger import get_logger

SERVER_HOST = "192.168.3.38"
SERVER_PORT = 8888


class AsyncConnector:
    def __init__(self, out_q: Queue, in_q: Queue, loop: asyncio.AbstractEventLoop):
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.out_q: Queue = out_q
        self.in_q: Queue = in_q
        self.loop = loop
        self.log = get_logger(self.__class__.__name__, to_file=True)
        self._executor = ThreadPoolExecutor(max_workers=1)

    def start(self):
        asyncio.run_coroutine_threadsafe(
            self._start(),
            self.loop
        )

    async def _start(self):
        self.reader, self.writer = await asyncio.open_connection(SERVER_HOST, SERVER_PORT)
        self._send_task = self.loop.create_task(self._sender())
        self._receiver_task = self.loop.create_task(self._receiver())
        self.log.info(f"Подключен к серверу по адресу: {SERVER_HOST}:{SERVER_PORT}")

    async def _sender(self):
        while True:
            action: Action | None = await self.loop.run_in_executor(
                self._executor,
                self.out_q.get
            )
            if action is None:
                break
            self.log.info(f"Отправка {action}")
            await action.send_action(writer=self.writer)

    async def _receiver(self):
        try:
            while True:
                msg = await self.reader.readuntil(END_MARKER)
                self.log.info(f"Пришло сообщение: {msg}")
                data = msg.removesuffix(END_MARKER)
                message: BaseMessage = message_adapter.validate_python(json.loads(data.decode()))
                self.in_q.put(message)
        except (asyncio.CancelledError, ConnectionError) as e:
            self.log.info(f"{str(e)}")

    def shutdown(self):
        self.out_q.put(None)
        self._receiver_task.cancel()
        self._executor.shutdown(wait=False)
        self._send_task.cancel()


class LoopThread(threading.Thread):

    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self._loop = loop
        self.daemon = True

    def run(self):
        self._loop.run_forever()


