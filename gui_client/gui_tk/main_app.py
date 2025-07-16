import asyncio
from datetime import datetime
import json
import os
import tkinter as tk
from pathlib import Path
from queue import Queue, Empty
from tkinter import ttk

from action.auth_token import decode_token
from action.schemas_message import BaseMessage, TokenMessage, InitMessage, JoinChatMessage, UpdateMessage
from gui_client.async_connector import AsyncConnector
from gui_client.client_logger import get_logger
from server.server import Action
from action.schemas import RegisterAction, JoinServerAction, Command, JoinUserAction, JoinChatAction, SendAction

CFG_PATH = Path(os.getenv("ONLINECHAT_CFG", Path.home() / ".onlinechat/config.json"))
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

        self.side_bar_2 = ttk.Frame(self, borderwidth=2, relief="ridge")
        self.side_bar_2.pack(side="left", fill="x")

        self.main_frame = ttk.Frame(self, borderwidth=2, relief="ridge")
        self.main_frame.pack(side="left", fill="x", padx=10)

        self.msg_entry = ttk.Entry(self)
        self.msg_entry.pack(side="bottom", fill="x")
        self.msg_entry.bind(
            "<Return>",
            self.send_message
        )
        # ── создаём Canvas и Scrollbar ──
        self.canvas = tk.Canvas(self.main_frame, borderwidth=0, highlightthickness=0)
        self.vsb = tk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # ── внутренний фрейм для сообщений ──
        self.msg_container = ttk.Frame(self.canvas)
        self.container_id = self.canvas.create_window(
            (0, 0), window=self.msg_container, anchor="nw"
        )

        # ── обновление scrollregion при изменении содержимого ──
        def on_frame_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        self.msg_container.bind("<Configure>", on_frame_configure)

        # ── флаг текущей комнаты ──

        self.chats = []
        self.users: list[ttk.Label] = []

    def init_process(self, msg: InitMessage):
        online_id = [u.id for u in msg.online_users]
        for child in self.side_bar.winfo_children():
            child.destroy()
        for child in self.side_bar_2.winfo_children():
            child.destroy()

        for user in msg.all_users:
            text = user.username + '-online' if user.id in online_id else user.username
            label = ttk.Label(self.side_bar, text=text)
            label.pack(side="top", fill="x")
            label.bind(
                "<Button-1>",
                lambda e, u_id=user.id: self.controller.send_action(self.create_join_user_action(u_id))
            )
            label.user_id = user.id
            self.users.append(label)

        for chat in msg.rooms:
            text = f"{chat.title}\nУчастников: {len(chat.users)}"
            label = ttk.Label(self.side_bar_2, text=text)
            label.pack(side="top", fill="x", padx=5)
            label.bind(
                "<Button-1>",
                lambda e, chat_id=chat.room_id: self.create_join_chat_action(chat_id)
            )
            label.chat_id = chat.room_id
            self.chats.append(label)

    def create_join_chat_action(self, room_id):
        if self.controller.room_id == room_id:
            return
        else:
            self.controller.send_action(
                JoinChatAction(
                    command=Command.JOIN_CHAT,
                    room=room_id,
                    token=self.controller.token,
                )
            )

    def open_chat(self, msg: JoinChatMessage):
        self.controller.room_id = msg.messages[0].room_id
        messages = sorted(msg.messages, key=lambda m: m.time_)
        for child in self.msg_container.winfo_children():
            child.destroy()
        for m in messages:
            bubble = ttk.Frame(self.msg_container)
            bubble.pack(fill="x", pady=2, padx=5)

            text = f"{m.content}\n[{datetime.fromtimestamp(m.time_).strftime('%H:%M:%S')}]"
            lbl = ttk.Label(bubble, text=text, wraplength=300, justify="left",
                            background="#e1ffc7" if m.from_ == self.controller.user_id else "#ffffff",
                            relief="ridge", padding=5)

            if m.from_ == self.controller.user_id:
                # свои сообщения справа
                lbl.pack(side="right", anchor="e", padx=(50, 0))
            else:
                # чужие слева
                lbl.pack(side="left", anchor="w", padx=(0, 50))

            # прокрутить вниз
            self.canvas.yview_moveto(1.0)

    def create_join_user_action(self, user_id):
        return JoinUserAction(
            user_id=user_id,
            command=Command.JOIN_USER,
            token=self.controller.token
        )

    def proc_update_msg(self, msg: UpdateMessage):
        match msg.kind:
            case "user_online":
                for user_label in self.users:
                    if user_label.user_id == msg.payload['id']:
                        user_label.config(text=f"{msg.payload['username']}-online")

            case "user_offline":
                for user_label in self.users:
                    if user_label.user_id == msg.payload['id']:
                        user_label.config(text=f"{msg.payload['username']}")

            case "new_room":
                if self.controller.user_id in msg.payload['users']:
                    title = msg.payload['title']
                    room_id = msg.payload['id']
                    users = msg.payload['users']
                    text = f"{title}\nУчастников: {len(users)}"
                    label = ttk.Label(self.side_bar_2, text=text)
                    label.pack(side="top", fill="x", padx=5)
                    label.bind(
                        "<Button-1>",
                        lambda e, chat_id=room_id: self.create_join_chat_action(chat_id)
                    )
                    label.chat_id = room_id
                    self.chats.append(label)

            case 'update_room':
                pass

    def send_message(self, e: tk.Event):
        widget: ttk.Entry = e.widget
        if widget.get():
            send_action = SendAction(
                command=Command.SEND,
                room=self.controller.room_id,
                token=self.controller.token,
                message=widget.get()
            )
            self.controller.send_action(send_action)






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


        self.async_connector = AsyncConnector(loop=self.loop, in_q=self.in_q, out_q=self.out_q)
        self.async_connector.start()
        self.after(50, self.poll_in)

        self.frames: dict[str, ttk.Frame] = {}
        self.container = ttk.Frame(self);
        self.container.pack(fill="both", expand=True)
        for F in (MainFrame, RegisterFrame, LoginFrame):
            page = F(self.container, loop=self.loop, in_q=self.in_q, out_q=self.out_q, controller=self)
            self.frames[F.__name__] = page
            page.grid(row=0, column=0, sticky="nsew")


        self.username = None
        self.user_id = None
        self.cfg = AppConfig()
        if token := self.cfg.get('token'):
            logger.info(f"Есть {token}")
            self.token = token
            self.send_action(
                JoinServerAction(command=Command.JOIN_SERVER, token=token)
            )
        else:
            self.show_page('RegisterFrame')


        self.room_id: int | None = None

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
            case UpdateMessage():
                self.proc_update_msg(msg)
            case JoinChatMessage():
                self.join_chat(msg)

    def proc_token_msg(self, msg: TokenMessage):
        self.token = msg.content
        payload = decode_token(self.token)
        self.username = payload.get("username")
        self.user_id = payload.get("id")
        self.cfg.set('token', self.token)
        self.cfg.set('username', self.username)
        self.cfg.set('id', self.user_id)
        self.cfg.save()

    def proc_init_msg(self, msg: InitMessage):
        self.show_page('MainFrame')
        self.username = msg.self_user["username"]
        self.user_id = msg.self_user["id"]
        main_frame: MainFrame = self.frames['MainFrame']
        main_frame.init_process(msg)


    def proc_update_msg(self, msg: UpdateMessage):
        main_frame: MainFrame = self.frames['MainFrame']
        main_frame.proc_update_msg(msg)

    def join_chat(self, msg: JoinChatMessage):
        main_frame: MainFrame = self.frames['MainFrame']
        main_frame.open_chat(msg)


    def destroy(self):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.async_connector.shutdown)
            self.loop.call_soon_threadsafe(self.loop.stop)
        super().destroy()
