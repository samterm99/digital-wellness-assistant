"""Thai control window: status, countdowns, pause/resume, interval settings.

It is a normal small window (opened on request), not a notification overlay.
It talks to the tray app only through state.json (read) and window messages (commands).
"""
import ctypes
import time
import tkinter as tk
from tkinter import font as tkfont, ttk

from . import config, control

ORDER = ("eyes", "stand", "posture")
GREEN, ORANGE, RED = "#1b7f3b", "#b35a00", "#b00020"


def fmt(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%02d:%02d" % (m, s)


def _single_panel():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CreateMutexW(None, False, "Local\\DigitalWellnessPanel" + config.INSTANCE)
    return ctypes.get_last_error() != 183


class Panel:
    def __init__(self, root):
        self.root = root
        root.title("ผู้ช่วยสุขภาพดิจิทัล")
        root.resizable(False, False)
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):  # ~20% larger text
            f = tkfont.nametofont(name)
            f.configure(size=int(round(f.cget("size") * 1.2)))  # negative = pixels, also fine
        ttk.Style().configure("TButton", padding=(10, 6))
        frm = ttk.Frame(root, padding=20)
        frm.grid()

        self.status = tk.Label(frm, font=("Tahoma", 18, "bold"), anchor="w")
        self.status.grid(row=0, column=0, columnspan=4, sticky="w")
        self.substatus = tk.Label(frm, anchor="w", fg="#555555")
        self.substatus.grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 10))

        cfg = config.load()
        self.enabled, self.minutes, self.countdown = {}, {}, {}
        for i, key in enumerate(ORDER, start=2):
            self.enabled[key] = tk.BooleanVar(value=cfg[key]["enabled"])
            self.minutes[key] = tk.StringVar(value=str(cfg[key]["minutes"]))
            ttk.Checkbutton(frm, text=config.LABELS[key], variable=self.enabled[key]
                            ).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Label(frm, text="ทุก").grid(row=i, column=1, padx=(12, 2))
            ttk.Spinbox(frm, from_=1, to=480, width=5, textvariable=self.minutes[key]
                        ).grid(row=i, column=2)
            ttk.Label(frm, text="นาที").grid(row=i, column=3, padx=(2, 12), sticky="w")
            self.countdown[key] = ttk.Label(frm, text="-", width=22)
            self.countdown[key].grid(row=i, column=4, sticky="w")

        self.skip = tk.BooleanVar(value=cfg["skip_fullscreen"])
        ttk.Checkbutton(frm, text="ไม่แจ้งเตือนตอนใช้งานเต็มจอ (หนัง/เกม/นำเสนอ)",
                        variable=self.skip).grid(row=5, column=0, columnspan=5, sticky="w", pady=(8, 2))
        self.startup = tk.BooleanVar(value=cfg["show_panel_on_startup"])
        ttk.Checkbutton(frm, text="แสดงหน้าต่างควบคุมเมื่อเริ่ม Windows",
                        variable=self.startup).grid(row=6, column=0, columnspan=5, sticky="w", pady=2)
        self.sound = tk.BooleanVar(value=cfg["eye_break_sound"])
        ttk.Checkbutton(frm, text="เล่นเสียงเบา ๆ เมื่อครบเวลาพักสายตา 20 วินาที",
                        variable=self.sound).grid(row=7, column=0, columnspan=5, sticky="w", pady=2)
        ttk.Label(frm, foreground="#555555", wraplength=520, justify="left",
                  text="ระยะเวลาที่แจ้งเตือนค้างอยู่ Windows เป็นผู้กำหนด "
                       "(ตั้งค่า → การช่วยการเข้าถึง → ระยะเวลาแสดงการแจ้งเตือน)"
                  ).grid(row=8, column=0, columnspan=5, sticky="w", pady=(0, 2))

        btns = ttk.Frame(frm)  # 2x2 grid keeps the window narrow on small screens
        btns.grid(row=9, column=0, columnspan=5, sticky="w", pady=(10, 0))
        self.toggle = ttk.Button(btns, width=22, command=self.on_toggle)
        self.toggle.grid(row=0, column=0, padx=(0, 8), pady=3)
        self.btest = ttk.Button(btns, text="ทดสอบแจ้งเตือน", width=22,
                                command=lambda: self.cmd(control.ID_TEST))
        self.btest.grid(row=0, column=1, pady=3)
        self.b30 = ttk.Button(btns, text="หยุด 30 นาที", width=22,
                              command=lambda: self.cmd(control.ID_PAUSE30))
        self.b30.grid(row=1, column=0, padx=(0, 8), pady=3)
        self.b60 = ttk.Button(btns, text="หยุด 1 ชั่วโมง", width=22,
                              command=lambda: self.cmd(control.ID_PAUSE60))
        self.b60.grid(row=1, column=1, pady=3)
        ttk.Button(btns, text="เริ่มพักสายตา 20 วินาที", width=22, command=self.eye_break
                   ).grid(row=2, column=0, padx=(0, 8), pady=3)

        ttk.Button(frm, text="บันทึกการตั้งค่า", command=self.save
                   ).grid(row=10, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.msg = ttk.Label(frm, text="")
        self.msg.grid(row=10, column=2, columnspan=3, sticky="w", pady=(12, 0))

        self.refresh()
        self.center()

    def center(self):
        """Centre on screen; keep it inside small screens (becomes resizable if too big)."""
        r = self.root
        r.update_idletasks()
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        w, h = r.winfo_reqwidth(), r.winfo_reqheight()
        if w > sw - 40 or h > sh - 80:
            w, h = min(w, sw - 40), min(h, sh - 80)
            r.resizable(True, True)
        r.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2), max(0, (sh - h) // 3)))

    def cmd(self, cid):
        control.send_command(cid)
        self.root.after(400, self.refresh_once)

    def eye_break(self):
        # the timer process refuses to open a second window while one is running
        from .tray_app import spawn_module
        spawn_module("wellness", "--eyebreak")

    def on_toggle(self):
        st = config.read_state() or {}
        if not control.is_running():
            from .tray_app import spawn_module
            spawn_module("wellness")
            self.root.after(1500, self.refresh_once)
        else:
            self.cmd(control.ID_RESUME if st.get("paused") else control.ID_PAUSE)

    def save(self):
        new = {"skip_fullscreen": self.skip.get(),
               "show_panel_on_startup": self.startup.get(),
               "eye_break_sound": self.sound.get()}
        for key in ORDER:
            try:
                m = int(self.minutes[key].get())
                if not 1 <= m <= 480:
                    raise ValueError
            except ValueError:
                self.msg.config(text="ใส่จำนวนนาทีเป็นตัวเลข 1-480", foreground=RED)
                return
            new[key] = {"enabled": self.enabled[key].get(), "minutes": m}
        config.save(new)
        control.send_command(control.ID_RELOAD)
        self.msg.config(text="บันทึกแล้ว", foreground=GREEN)
        self.root.after(400, self.refresh_once)

    def refresh_once(self):
        running = control.is_running()
        st = config.read_state() if running else None
        now = time.time()
        if not running or not st:
            self.status.config(text="○ โปรแกรมเตือนไม่ได้ทำงาน", fg=RED)
            self.substatus.config(text="กดปุ่ม \"เปิดการเตือน\" เพื่อเริ่ม")
            self.toggle.config(text="เปิดการเตือน")
            for b in (self.b30, self.b60, self.btest):
                b.state(["disabled"])
            for lbl in self.countdown.values():
                lbl.config(text="-")
            return
        paused = st.get("paused")
        for b in (self.b30, self.b60):
            b.state(["disabled"] if paused else ["!disabled"])
        self.btest.state(["!disabled"])
        if paused:
            until = st.get("paused_until")
            self.status.config(text="⏸ หยุดชั่วคราว", fg=ORANGE)
            self.substatus.config(
                text=("จะเริ่มเองอีก " + fmt(until - now)) if until else "กดปุ่มเพื่อเริ่มการเตือนต่อ")
            self.toggle.config(text="เริ่มการเตือนต่อ")
        else:
            self.status.config(text="● กำลังทำงาน", fg=GREEN)
            if st.get("away"):
                self.substatus.config(text="หน้าจอล็อกอยู่ — เริ่มนับเวลาใหม่เมื่อกลับมา")
            elif st.get("busy") and self.skip.get():
                self.substatus.config(text="ตอนนี้ใช้งานเต็มจอ — เลื่อนการเตือนไว้ก่อน")
            else:
                self.substatus.config(text="")
            self.toggle.config(text="หยุดการเตือนชั่วคราว")
        for key in ORDER:
            r = st["reminders"].get(key, {})
            if not r.get("enabled") or r.get("next") is None:
                text = "ปิดอยู่"
            elif paused:
                text = "-"
            elif r["next"] - now <= 0:
                text = "กำลังจะเตือน"
            else:
                text = "เตือนอีก " + fmt(r["next"] - now)
            self.countdown[key].config(text=text)

    def refresh(self):
        try:
            self.refresh_once()
        finally:
            self.root.after(1000, self.refresh)


def main():
    if not _single_panel():
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # sharp text on high-DPI screens
    except Exception:
        pass
    root = tk.Tk()
    Panel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
