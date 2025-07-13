import os

import dotenv


dotenv.load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DB_URL")
    SECRET_KEY = os.environ.get("SECRET_KEY")

if __name__ == "__main__":
    print(Config.SQLALCHEMY_DATABASE_URI)