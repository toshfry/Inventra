import customtkinter as ctk
from config.themes import COLORS
from ui.nav_sidebar import NavSidebar
from core.services.auth_service import is_admin, logout


def confirm_and_exit(root):
    """Ask the user to confirm before quitting the running app, then save a
    backup on the way out. Wired to the main window's close (X) button so the
    app can't be closed by an accidental click while working."""
    import tkinter.messagebox as mb
    from utils.backup import create_backup
    if mb.askyesno(
        "Exit Inventra",
        "Are you sure you want to exit Inventra?",
        icon="question",
        parent=root,
    ):
        create_backup()
        root.destroy()


class AppWindow(ctk.CTkFrame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], corner_radius=0, **kwargs)
        self._parent  = parent
        self._screens = {}
        self._active  = None
        self._active_key = None
        self._build()

    def _build(self):
        self.sidebar = NavSidebar(self,
                                   on_navigate=self.navigate,
                                   on_logout=self._logout,
                                   on_collapse=self._hide_nav)
        self.sidebar.pack(side="left", fill="y")

        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        # Slim edge handle to reopen the sidebar after it's hidden (shown only then).
        self._nav_handle = ctk.CTkButton(
            self, text="›", width=20, height=72,
            fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
            text_color="#FFFFFF", font=("Helvetica", 18, "bold"),
            corner_radius=0, command=self._show_nav)

        self.navigate("dashboard")

    def _hide_nav(self):
        """Fully hide the sidebar; show a small edge handle to bring it back."""
        self.sidebar.pack_forget()
        self._nav_handle.place(relx=0.0, rely=0.5, anchor="w")
        self._nav_handle.lift()

    def _show_nav(self):
        self._nav_handle.place_forget()
        self.sidebar.pack(side="left", fill="y", before=self.content)

    def navigate(self, key: str):
        if key == "settings" and not is_admin():
            return
        if key == self._active_key:
            return

        if self._active:
            self._active.pack_forget()

        if key not in self._screens:
            self._screens[key] = self._create_screen(key)

        screen = self._screens[key]
        screen.pack(fill="both", expand=True)
        if hasattr(screen, "refresh"):
            screen.refresh()
        self._active = screen
        self._active_key = key
        self.sidebar.navigate_to(key)
        self.content.update_idletasks()

    def show_low_stock_parts(self):
        """Open the Parts Library with the low-stock filter already applied
        (used by the Dashboard's low-stock 'View all' links)."""
        self.navigate("parts")
        screen = self._screens.get("parts")
        if screen is not None and hasattr(screen, "set_low_stock_filter"):
            screen.set_low_stock_filter(True)

    def _create_screen(self, key: str):
        from ui.screens.dashboard     import DashboardScreen
        from ui.screens.parts_library import PartsLibraryScreen
        from ui.screens.stock_in      import StockInScreen
        from ui.screens.stock_out     import StockOutScreen
        from ui.screens.pos           import PosScreen
        from ui.screens.suppliers     import SuppliersScreen
        from ui.screens.reports       import ReportsScreen
        from ui.screens.settings      import SettingsScreen
        from ui.screens.returns       import ReturnsScreen

        map_ = {
            "dashboard":  DashboardScreen,
            "parts":      PartsLibraryScreen,
            "stock_in":   StockInScreen,
            "stock_out":  StockOutScreen,
            "pos":        PosScreen,
            "suppliers":  SuppliersScreen,
            "reports":    ReportsScreen,
            "settings":   SettingsScreen,
            "returns":    ReturnsScreen,
        }
        cls = map_.get(key)
        if cls:
            return cls(self.content, app=self)
        raise ValueError(f"Unknown screen: {key}")

    def _logout(self):
        import tkinter.messagebox as mb
        if mb.askyesno("Sign Out", "Are you sure you want to sign out?",
                       parent=self):
            logout()
            # Destroy this window and relaunch login
            self._parent.destroy()
            _relaunch()


def _relaunch():
    import customtkinter as ctk
    from database.engine import init_db
    from config.settings import APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT, MIN_WIDTH, MIN_HEIGHT

    init_db()
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title(f"{APP_NAME}  v{APP_VERSION}")
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    root.minsize(MIN_WIDTH, MIN_HEIGHT)
    root.withdraw()

    from ui.login import LoginWindow
    def on_success():
        root.deiconify()
        app = AppWindow(root)
        app.pack(fill="both", expand=True)
        root.protocol("WM_DELETE_WINDOW", lambda: confirm_and_exit(root))

    LoginWindow(root, on_success=on_success)
    root.mainloop()
