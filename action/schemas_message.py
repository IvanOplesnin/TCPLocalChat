import asyncio
import json
from enum import Enum
from typing import Literal, Annotated, Union, Optional
from pydantic import BaseModel, Field, TypeAdapter, ConfigDict

END_MARKER: bytes = b"<END>\n"


class TypeMessage(str, Enum):
    token = "token"
    message = "message"
    update = "update"
    init = "init"


class UpdateKind(str, Enum):
    user_online = "user_online"
    user_offline = "user_offline"
    new_room = "new_room"
    new_message = "new_message"


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

    def __repr__(self):
        return f"{self.__class__.__name__}: {json.dumps(self.model_dump(), indent=4)}"


class RoomBrief(BaseModel):
    room_id: int
    title: str
    last_message: str | None
    last_time: str | None
    unread: int


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
    kind: UpdateKind
    payload: dict
    content: Optional[str] = None


class UserBrief(BaseModel):
    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)

class InitMessage(BaseMessage):
    type_: Literal[TypeMessage.init] = Field(TypeMessage.init, alias="type")
    self_user: dict
    rooms: list[RoomBrief]
    all_users: list[UserBrief]
    online_users: list[UserBrief]
    content: Optional[str] = None


AnyMessage = Annotated[
    Union[Message, UpdateMessage, InitMessage, TokenMessage],
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
