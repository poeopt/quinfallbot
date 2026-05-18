import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import importlib.util
import shutil
from datetime import datetime

PACKET_FILE = "live_packets.jsonl"
PARSER_FILE = "live_parser.py"


class PacketToolkit:

    def __init__(self, root):

        self.root = root

        self.root.title("Live Packet Toolkit")

        self.root.geometry("1400x900")

        self.packets = []

        self.file_offset = 0

        self.parser_module = None

        self.last_live_result = "No parser data yet"

        # =========================================
        # TOP BAR
        # =========================================

        top = tk.Frame(root)

        top.pack(fill="x")

        tk.Button(
            top,
            text="APPLY",
            command=self.reload_parser,
            bg="#2d8fdd",
            fg="white"
        ).pack(side="left", padx=5, pady=5)

        tk.Button(
            top,
            text="CLEAR",
            command=self.clear_logs,
            bg="#cc4444",
            fg="white"
        ).pack(side="left", padx=5, pady=5)

        tk.Button(
            top,
            text="EXPORT TEST",
            command=self.export_test,
            bg="#44aa44",
            fg="white"
        ).pack(side="left", padx=5, pady=5)

        # =========================================
        # MAIN
        # =========================================

        main = tk.PanedWindow(
            root,
            orient=tk.HORIZONTAL,
            sashrelief=tk.RAISED
        )

        main.pack(fill="both", expand=True)

        # =========================================
        # LEFT PANEL
        # =========================================

        left_frame = tk.Frame(main)

        main.add(left_frame, width=320)

        tk.Label(
            left_frame,
            text="Packets (newest first)"
        ).pack(anchor="w")

        self.packet_list = tk.Listbox(
            left_frame
        )

        self.packet_list.pack(
            fill="both",
            expand=True
        )

        self.packet_list.bind(
            "<<ListboxSelect>>",
            self.on_packet_select
        )

        # =========================================
        # CENTER PANEL
        # =========================================

        center_frame = tk.Frame(main)

        main.add(center_frame)

        tk.Label(
            center_frame,
            text="HEX / RESULT"
        ).pack(anchor="w")

        self.result_text = tk.Text(
            center_frame,
            wrap="word"
        )

        self.result_text.pack(
            fill="both",
            expand=True
        )

        # =========================================
        # RIGHT PANEL
        # =========================================

        right_frame = tk.Frame(main)

        main.add(right_frame)

        tk.Label(
            right_frame,
            text="Live Parser"
        ).pack(anchor="w")

        self.parser_text = tk.Text(
            right_frame,
            wrap="none",
            undo=True
        )

        self.parser_text.pack(
            fill="both",
            expand=True
        )

        # =========================================
        # LOAD PARSER
        # =========================================

        self.load_parser_text()

        self.reload_parser(silent=True)

        # =========================================
        # LOOP
        # =========================================

        self.root.after(
            200,
            self.update_packets
        )

    # =============================================
    # LOAD PARSER FILE
    # =============================================

    def load_parser_text(self):

        if not os.path.exists(PARSER_FILE):

            with open(
                PARSER_FILE,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
'''def handle(payload: bytes):

    return {
        "size": len(payload)
    }
'''
                )

        with open(
            PARSER_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            code = f.read()

        self.parser_text.delete(
            "1.0",
            "end"
        )

        self.parser_text.insert(
            "1.0",
            code
        )

    # =============================================
    # RELOAD PARSER
    # =============================================

    def reload_parser(self, silent=False):

        try:

            code = self.parser_text.get(
                "1.0",
                "end"
            )

            with open(
                PARSER_FILE,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(code)

            spec = importlib.util.spec_from_file_location(
                "live_parser",
                PARSER_FILE
            )

            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            self.parser_module = module

            self.last_live_result = "Parser loaded successfully"

            if not silent:

                messagebox.showinfo(
                    "OK",
                    "Parser loaded"
                )

        except Exception as e:

            self.last_live_result = (
                f"PARSER LOAD ERROR:\n{str(e)}"
            )

            messagebox.showerror(
                "Parser Error",
                str(e)
            )

    # =============================================
    # CLEAR
    # =============================================

    def clear_logs(self):

        try:

            if os.path.exists(PACKET_FILE):
                os.remove(PACKET_FILE)

            if os.path.exists("player_live.txt"):
                os.remove("player_live.txt")

        except:
            pass

        self.packet_list.delete(
            0,
            "end"
        )

        self.result_text.delete(
            "1.0",
            "end"
        )

        self.packets.clear()

        self.file_offset = 0

        self.last_live_result = "Logs cleared"

    # =============================================
    # EXPORT
    # =============================================

    def export_test(self):

        if not os.path.exists(PACKET_FILE):

            messagebox.showerror(
                "Error",
                "No packet log"
            )

            return

        filename = datetime.now().strftime(
            "test_%Y%m%d_%H%M%S.jsonl"
        )

        save_path = filedialog.asksaveasfilename(
            defaultextension=".jsonl",
            initialfile=filename,
            filetypes=[
                ("JSONL", "*.jsonl")
            ]
        )

        if not save_path:
            return

        shutil.copyfile(
            PACKET_FILE,
            save_path
        )

        messagebox.showinfo(
            "Export",
            "Done"
        )

    # =============================================
    # UPDATE PACKETS
    # =============================================

    def update_packets(self):

        try:

            if os.path.exists(PACKET_FILE):

                with open(
                    PACKET_FILE,
                    "r",
                    encoding="utf-8"
                ) as f:

                    f.seek(self.file_offset)

                    lines = f.readlines()

                    self.file_offset = f.tell()

                for line in lines:

                    try:

                        packet = json.loads(line)

                        self.packets.insert(
                            0,
                            packet
                        )

                        # =====================================
                        # REALTIME PARSER
                        # =====================================

                        if self.parser_module:

                            try:

                                hex_data = packet.get(
                                    "hex",
                                    ""
                                )

                                if hex_data:

                                    payload = bytes.fromhex(
                                        hex_data
                                    )

                                    result = self.parser_module.handle(
                                        payload
                                    )

                                    # =====================================
                                    # SAVE LIVE RESULT
                                    # =====================================

                                    self.last_live_result = json.dumps(
                                        result,
                                        indent=2
                                    )

                            except Exception as e:

                                self.last_live_result = (
                                    f"LIVE PARSER ERROR:\n{str(e)}"
                                )

                        size = packet.get(
                            "size",
                            0
                        )

                        ts = packet.get(
                            "timestamp",
                            0
                        )

                        self.packet_list.insert(
                            0,
                            f"{size} bytes | {ts}"
                        )

                        self.packet_list.yview(0)

                        if len(self.packets) > 10000:

                            self.packets.pop()

                            self.packet_list.delete(
                                "end"
                            )

                    except Exception as e:

                        self.last_live_result = (
                            f"PACKET ERROR:\n{str(e)}"
                        )

        except Exception as e:

            self.last_live_result = (
                f"READ ERROR:\n{str(e)}"
            )

        self.root.after(
            200,
            self.update_packets
        )

    # =============================================
    # PACKET CLICK
    # =============================================

    def on_packet_select(self, event):

        if not self.packet_list.curselection():
            return

        index = self.packet_list.curselection()[0]

        if index >= len(self.packets):
            return

        packet = self.packets[index]

        self.result_text.delete(
            "1.0",
            "end"
        )

        hex_data = packet.get(
            "hex",
            ""
        )

        self.result_text.insert(
            "end",
            "HEX:\n\n"
        )

        self.result_text.insert(
            "end",
            hex_data
        )

        self.result_text.insert(
            "end",
            "\n\n========================================\n"
        )

        self.result_text.insert(
            "end",
            "LIVE PARSER RESULT:\n\n"
        )

        self.result_text.insert(
            "end",
            self.last_live_result
        )


# =============================================
# START
# =============================================

root = tk.Tk()

app = PacketToolkit(root)

root.mainloop()