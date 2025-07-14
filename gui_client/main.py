import asyncio

from gui_client.gui_tk.main_app import App
from gui_client.async_connector import LoopThread



loop = asyncio.new_event_loop()
asyncio_thread = LoopThread(loop)
asyncio_thread.start()

app = App(loop=loop)
app.mainloop()