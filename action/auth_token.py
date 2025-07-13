from typing import Any
import jwt

from db_model.models import User
from config import Config

def create_token(user: User) -> str:
    return jwt.encode(
        payload={
            "id": user.id,
            "username": user.username,
        },
        key=Config.SECRET_KEY,
        algorithm="HS256",
    )

def decode_token(token: str) -> Any:
    try:
        decode = jwt.decode(
            token,
            Config.SECRET_KEY,
            algorithms="HS256",
        )
        return decode
    except jwt.exceptions.InvalidSignatureError:
        raise jwt.exceptions.InvalidSignatureError("Invalid key")
    except jwt.exceptions.ExpiredSignatureError:
        raise jwt.exceptions.ExpiredSignatureError("Expired token")
    except jwt.exceptions.InvalidTokenError:
        raise jwt.exceptions.InvalidTokenError("Invalid token")
