import asyncio
import json

from action.schemas_message import END_MARKER, InitMessage, TokenMessage, UpdateMessage
from action.schemas import RegisterAction, AuthorizeAction, JoinServerAction, Command


async def send_messages(writer):
    while True:
        msg = await asyncio.to_thread(input, "> ")  # не блокирует event loop
        if msg.lower() in ("exit", "quit"):
            writer.write(b"Client disconnected.\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            break
        register = RegisterAction(
            username='i_vanya0956',
            password='ivashka',
            command=Command.REGISTER
        )
        msg = json.dumps(register.model_dump()).encode() + END_MARKER
        writer.write(msg)
        await writer.drain()

async def receive_messages(reader):
    while True:
        data = await reader.readuntil(END_MARKER)
        if not data:
            print("Сервер отключился.")
            break
        print(f"\n{data.decode().strip()}")

async def main():
    reader, writer = await asyncio.open_connection("127.0.0.1", 8888)

    print("Подключено к серверу. Пиши 'exit' для выхода.")

    # Параллельный запуск чтения и записи
    await asyncio.gather(
        send_messages(writer),
        receive_messages(reader)
    )

asyncio.run(main())
