class Debouncer:
    """Delay a callback until the user pauses rapid input."""

    def __init__(self, widget, delay_ms=180):
        self.widget = widget
        self.delay_ms = delay_ms
        self._after_id = None

    def call(self, fn, *args, **kwargs):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.widget.after(
            self.delay_ms, lambda: self._run(fn, *args, **kwargs))

    def _run(self, fn, *args, **kwargs):
        self._after_id = None
        fn(*args, **kwargs)
