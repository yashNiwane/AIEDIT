import tkinter as tk
from src.app_ui.main_window import VideoEditorAppUI

if __name__ == '__main__':
    root = tk.Tk()
    app = VideoEditorAppUI(root)
    # Set the protocol for window closing to call app.on_closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
