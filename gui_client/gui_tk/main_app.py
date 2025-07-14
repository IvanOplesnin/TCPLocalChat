import asyncio
import json
import os
import tkinter as tk
from pathlib import Path
from queue import Queue, Empty
from tkinter import ttk

from action.auth_token import decode_token
from action.schemas_message import BaseMessage, TokenMessage, InitMessage
from gui_client.async_connector import AsyncConnector
from gui_client.client_logger import get_logger
from server.server import Action
from action.schemas import RegisterAction, JoinServerAction, Command

CFG_PATH = Path(os.getenv("ONLINECHAT_CFG", Path.home()/".onlinechat/config.json"))

logger = get_logger('Интерфейс')

class AppConfig:
    def __init__(self):
        self.data: dict = {}
        if CFG_PATH.exists():
            self.data = json.loads(CFG_PATH.read_text())
    def save(self):
        CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CFG_PATH.write_text(json.dumps(self.data, indent=2))
    # помощники
    def get(self, k, d=None): return self.data.get(k, d)
    def set(self, k, v): self.data[k] = v


class MainFrame(ttk.Frame):

    def __init__(self, parent, loop: asyncio.AbstractEventLoop, in_q: Queue, out_q: Queue, controller: 'App', **kwargs):
        super().__init__(parent, **kwargs)

        self.in_q: Queue = in_q
        self.out_q: Queue = out_q
        self.loop = loop
        self.controller = controller

        self.label = tk.Label(self, text="OnlineChat-mainFrame")
        self.label.pack(side="top", fill="x")

        self.side_bar = ttk.Frame(self, borderwidth=2, relief="ridge")
        self.side_bar.pack(side="left", fill="x")

        self.main_frame = ttk.Frame(self, borderwidth=2, relief="ridge")
        self.main_frame.pack(side="left", fill="x", padx=10)

        self.msg_entry = ttk.Entry(self.main_frame)
        self.msg_entry.pack(side="bottom", fill="x")

        self.chats = []
        self.users = []


    def init_process(self, msg: InitMessage):
        online_id = [u.id for u in msg.online_users]
        for user in msg.all_users:
            text = user.username + '-online' if user.id in online_id else user.username
            label = tk.Label(self.side_bar, text=text)
            label.pack(side="top", fill="x")




class RegisterFrame(ttk.Frame):

    def __init__(self, parent, loop: asyncio.AbstractEventLoop, in_q: Queue, out_q: Queue, controller: 'App', **kwargs):
        super().__init__(parent, **kwargs)
        self.in_q: Queue = in_q
        self.out_q: Queue = out_q
        self.loop = loop
        self.controller = controller

        self.label = tk.Label(self, text="OnlineChat-RegisterFrame")
        self.label.pack(side="top", fill="x")


        self.name_label = tk.Label(self, text="username")
        self.name_label.pack(side="top", fill="x")
        self.name_entry = ttk.Entry(self, width=40)
        self.name_entry.pack(side="top", fill="x", padx=10, pady=10)
        self.name_entry.focus_force()

        self.name_label = tk.Label(self, text="password")
        self.name_label.pack(side="top", fill="x")
        self.password_entry = ttk.Entry(self, width=40)
        self.password_entry.pack(side="top", fill="x", padx=10, pady=10)


        self.button = ttk.Button(self, command=self.click, text="Зарегистрироваться")
        self.button.pack(side="top", fill="x", padx=10, pady=10)

    def click(self):
        self.controller.send_action(
            RegisterAction(
                username=self.name_entry.get(),
                password=self.password_entry.get(),
                command=Command.REGISTER
            )
        )


class LoginFrame(ttk.Frame):
    def __init__(self, parent, loop: asyncio.AbstractEventLoop, in_q: Queue, out_q: Queue, controller: 'App', **kwargs):
        super().__init__(parent, **kwargs)
        self.in_q: Queue = in_q
        self.out_q: Queue = out_q
        self.loop = loop
        self.controller = controller

        self.label = tk.Label(self, text="OnlineChat-LoginFrame")
        self.label.pack(side="top", fill="x")


class App(tk.Tk):

    def __init__(self, loop: asyncio.AbstractEventLoop, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("OnlineChat")
        self.geometry("800x600")

        self.in_q: Queue = Queue()
        self.out_q: Queue = Queue()
        self.loop = loop

        async_connector = AsyncConnector(loop=self.loop, in_q=self.in_q, out_q=self.out_q)
        async_connector.start()
        self.after(20, self.poll_in)

        self.frames: dict[str, ttk.Frame] = {}
        self.container = ttk.Frame(self);
        self.container.pack(fill="both", expand=True)
        for F in (MainFrame, RegisterFrame, LoginFrame):
            page = F(self.container, loop=self.loop, in_q=self.in_q, out_q=self.out_q, controller=self)
            self.frames[F.__name__] = page
            page.grid(row=0, column=0, sticky="nsew")

        self.cfg = AppConfig()
        if token:=self.cfg.get('token'):
            self.send_action(
                JoinServerAction(command=Command.JOIN_SERVER, token=token)
            )
        else:
            self.show_page('RegisterFrame')


    def send_action(self, action: Action):
        self.out_q.put(action)


    def poll_in(self):
        try:
            while True:
                msg: BaseMessage = self.in_q.get_nowait()
                logger.info(f"Прочитано сообщение интерфейсом: {msg}")
                self.process_msg(msg)
        except Empty:
            pass
        self.after(20, self.poll_in)


    def show_page(self, name):
        page = self.frames[name]
        page.tkraise()


    def process_msg(self, msg: BaseMessage):
        match msg:
            case TokenMessage():
                self.proc_token_msg(msg)
            case InitMessage():
                self.proc_init_msg(msg)

    def proc_token_msg(self, msg: TokenMessage):
        token = msg.content
        payload = decode_token(token)
        username = payload.get("username")
        user_id = payload.get("user_id")
        self.cfg.set('token', token)
        self.cfg.set('username', username)
        self.cfg.set('user_id', user_id)
        self.cfg.save()


    def proc_init_msg(self, msg: InitMessage):
        self.show_page('MainFrame')
        main_frame: MainFrame = self.frames['MainFrame']
        main_frame.init_process(msg)









