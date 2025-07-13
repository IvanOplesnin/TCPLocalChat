import asyncio
import json
from enum import Enum
from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field, TypeAdapter

END_MARKER = b"<END>\n"

class TypeMessage(str, Enum):
    token = "token"
    message = "message"
    update = "update"
    init = "init"


class BaseMessage(BaseModel):
    type_: TypeMessage = Field(..., alias="type")
    content: str

    model_config = {
        "populate_by_name": True,
        "extra": "ignore"
    }

    def _to_bytes(self) -> bytes:
        return json.dumps(self.model_dump()).encode() + END_MARKER

    async def send_message(self, writer: "asyncio.StreamWriter"):
        writer.write(self._to_bytes())
        await writer.drain()


class TokenMessage(BaseMessage):
    type_: Literal[TypeMessage.token] = Field(TypeMessage.token, alias="type")

class Message(BaseMessage):
    type_: Literal[TypeMessage.message] = Field(TypeMessage.message, alias="type")
    from_: int
    from_username: str
    room_id: int
    time_: str


class UpdateMessage(BaseMessage):
    type_: Literal[TypeMessage.update] = Field(TypeMessage.update, alias="type")


class InitMessage(BaseMessage):
    type_: Literal[TypeMessage.init] = Field(TypeMessage.init, alias="type")


AnyMessage = Annotated[
    Union[Message, UpdateMessage, InitMessage],
    Field(discriminator="type_")
]

message_adapter = TypeAdapter(AnyMessage)

# # Пример данных
# data = {
#     "type": "message",
#     "content": "Привет!",
#     "from_": 1,
#     "room_id": 2
# }
#
# parsed: BaseMessage = message_adapter.validate_python(data)
# print(parsed.to_bytes())
# print(type(parsed))


