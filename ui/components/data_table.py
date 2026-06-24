import tkinter as tk
import tkinter.ttk as ttk
from config.themes import COLORS, FONTS


class DataTable(tk.Frame):
    """Styled ttk.Treeview with alternating rows and hover feel."""

    def __init__(self, parent, columns: list, on_select=None,
                 on_double_click=None, on_click=None, height: int = 20, **kwargs):
        super().__init__(parent, bg=COLORS["card"], **kwargs)
        self.on_select       = on_select
        self.on_double_click = on_double_click
        self.on_click        = on_click
        self._row_height     = 40
        self._setup_style()
        self._build(columns, height)

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Inventra.Treeview",
            background    = COLORS["card"],
            foreground    = COLORS["txt"],
            fieldbackground = COLORS["card"],
            rowheight     = self._row_height,
            font          = ("Helvetica", 12),
            borderwidth   = 0,
        )
        style.configure("Inventra.Treeview.Heading",
            background  = COLORS["navy"],
            foreground  = "#FFFFFF",
            font        = ("Helvetica", 10, "bold"),
            borderwidth = 0,
            relief      = "flat",
            padding     = (10, 8),
        )
        style.map("Inventra.Treeview",
            background = [("selected", COLORS["blue_bg"])],
            foreground = [("selected", COLORS["blue"])],
        )
        style.layout("Inventra.Treeview", [
            ("Treeview.treearea", {"sticky": "nswe"})
        ])

    def _build(self, columns: list, height: int):
        col_ids = [c["id"] for c in columns]

        self.tree = ttk.Treeview(
            self, columns=col_ids, show="headings",
            style="Inventra.Treeview", height=height,
            selectmode="browse",
        )

        for c in columns:
            self.tree.heading(c["id"], text=c["label"],
                              anchor=c.get("anchor", "w"))
            self.tree.column(c["id"], width=c.get("width", 120),
                             minwidth=c.get("minwidth", 60),
                             anchor=c.get("anchor", "w"),
                             stretch=c.get("stretch", True))

        vsb = ttk.Scrollbar(self, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<ButtonRelease-1>",  self._on_click)
        self.tree.bind("<Double-1>",         self._on_double)

        # Row tags for alternating color
        self.tree.tag_configure("odd",     background=COLORS["card"])
        self.tree.tag_configure("even",    background="#F8FAFC")
        self.tree.tag_configure("low",     foreground=COLORS["red"])
        self.tree.tag_configure("warn",    foreground=COLORS["amber"])

    def load(self, rows: list):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(rows):
            tag  = "even" if i % 2 == 0 else "odd"
            extra = row.get("_tag", "")
            tags  = (tag, extra) if extra else (tag,)
            self.tree.insert("", "end",
                             values=row["values"],
                             iid=str(row.get("id", i)),
                             tags=tags)

    def get_selected_iid(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def set_visible_rows(self, rows: int):
        self.tree.configure(height=max(3, int(rows)))

    def _on_select(self, _):
        iid = self.get_selected_iid()
        if iid and self.on_select:
            self.on_select(iid)

    def _on_click(self, event):
        if not self.on_click:
            return
        iid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if iid:
            self.on_click(iid, col)

    def _on_double(self, _):
        iid = self.get_selected_iid()
        if iid and self.on_double_click:
            self.on_double_click(iid)
