import tkinter as tk
import os


PLAYER_FILE = "player_live.txt"

UPDATE_MS = 100


class PlayerLiveWindow:

    def __init__(self, root):

        self.root = root

        self.root.title("PLAYER LIVE")
        self.root.geometry("500x400")

        self.text = tk.Text(
            root,
            font=("Consolas", 12),
            bg="#111111",
            fg="#00FF66",
            insertbackground="white"
        )

        self.text.pack(
            fill="both",
            expand=True
        )

        self.last_content = ""

        self.update_loop()

    def update_loop(self):

        try:

            if os.path.exists(PLAYER_FILE):

                with open(
                    PLAYER_FILE,
                    "r",
                    encoding="utf-8"
                ) as f:

                    content = f.read()

                if content != self.last_content:

                    self.text.delete(
                        "1.0",
                        tk.END
                    )

                    self.text.insert(
                        tk.END,
                        content
                    )

                    self.last_content = content

        except Exception as e:

            self.text.delete(
                "1.0",
                tk.END
            )

            self.text.insert(
                tk.END,
                f"ERROR:\n\n{e}"
            )

        self.root.after(
            UPDATE_MS,
            self.update_loop
        )


root = tk.Tk()

app = PlayerLiveWindow(root)

root.mainloop()