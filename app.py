import customtkinter as ctk
from database.engine import init_db
from utils.backup import create_backup
from utils.app_icon import set_window_icon
from config.settings import APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT, MIN_WIDTH, MIN_HEIGHT


def main():
    init_db()
    create_backup()

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    set_window_icon(root)
    root.title(f"{APP_NAME}  v{APP_VERSION}")
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    root.minsize(MIN_WIDTH, MIN_HEIGHT)

    # Centre on screen
    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(
        f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{(sw-WINDOW_WIDTH)//2}+{(sh-WINDOW_HEIGHT)//2}")

    # Hide main window until login succeeds
    root.withdraw()

    from core.licensing.license_manager import is_activated
    from ui.activation import ActivationWindow
    from ui.login import LoginWindow
    from ui.app_window import AppWindow, confirm_and_exit

    def on_login_success():
        root.deiconify()
        app = AppWindow(root)
        app.pack(fill="both", expand=True)
        root.protocol("WM_DELETE_WINDOW", lambda: confirm_and_exit(root))

    def show_login():
        LoginWindow(root, on_success=on_login_success)

    # First-time activation comes before the normal login window.
    if is_activated():
        show_login()
    else:
        ActivationWindow(root, on_success=show_login)

    root.mainloop()


if __name__ == "__main__":
    main()
