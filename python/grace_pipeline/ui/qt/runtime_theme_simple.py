"""Additional theme modes for runtime settings."""
THEMES = {"system", "light", "dark", "blue", "green", "graphite", "sepia", "violet"}
THEME_ITEMS = [("System", "system"), ("Light", "light"), ("Dark", "dark"), ("Blue", "blue"), ("Green", "green"), ("Graphite", "graphite"), ("Sepia", "sepia"), ("Violet", "violet")]

def norm_theme(value):
    value = str(value or "system").strip().lower()
    return value if value in THEMES else "system"

def install_preferences():
    from grace_pipeline.ui.qt import preferences
    preferences.THEME_MODES = set(THEMES)
    preferences._normalize_theme = norm_theme
    def load(settings=None):
        s = settings or preferences.make_settings_store()
        return preferences.UIPreferences(norm_theme(s.value("ui/theme", "system", type=str)), preferences._normalize_language(s.value("ui/language", "zh", type=str)))
    def save(pref, settings=None):
        s = settings or preferences.make_settings_store()
        out = preferences.UIPreferences(norm_theme(getattr(pref, "theme", "system")), preferences._normalize_language(getattr(pref, "language", "zh")))
        s.setValue("ui/theme", out.theme); s.setValue("ui/language", out.language); s.sync(); return out
    preferences.load_ui_preferences = load
    preferences.save_ui_preferences = save

def install_palette():
    from grace_pipeline.ui.qt import theme
    system_theme = theme.resolve_system_theme
    def resolve(mode="system", app=None):
        mode = norm_theme(mode)
        return system_theme(app=app) if mode == "system" else ("dark" if mode in {"dark", "graphite"} else "light")
    def palette(mode="system", app=None):
        mode = norm_theme(mode)
        base = dict(theme.DARK_COLOR if resolve(mode, app) == "dark" else theme.LIGHT_COLOR)
        if mode == "blue": base.update({"background":"#f3f8ff","nav_surface":"#eaf3fc","primary":"#0068b7","primary_soft":"#d7eaff"})
        if mode == "green": base.update({"background":"#f4faf6","nav_surface":"#eaf5ee","primary":"#217a4a","primary_soft":"#d9f0e2"})
        if mode == "sepia": base.update({"background":"#faf6ef","nav_surface":"#f3eadf","primary":"#8a5a24","primary_soft":"#f1dfc4"})
        if mode == "violet": base.update({"background":"#f8f6ff","nav_surface":"#f0ebfb","primary":"#6d4db8","primary_soft":"#e5dcff"})
        return base
    def stylesheet(mode="system", app=None):
        theme.ensure_application_font(app=app); colors = palette(mode, app); theme.set_active_palette(colors); return theme.build_stylesheet(colors)
    theme.resolve_theme_mode = resolve; theme.palette_for_theme = palette; theme.app_stylesheet = stylesheet

def install():
    install_preferences(); install_palette()
