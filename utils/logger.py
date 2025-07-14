import logging


def get_logger(name: str = "OnlineChat", to_file: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    fmt = (
        "%(name)-15s | %(asctime)s | "
        "%(module)-15s | line:%(lineno)4d | %(levelname)-8s | "
        "%(message)s"
    )
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        if to_file:
            file_handler = logging.FileHandler(filename="online_chat.log", mode="a")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger