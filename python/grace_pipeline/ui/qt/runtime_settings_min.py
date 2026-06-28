"""Small settings dialog patch."""
from grace_pipeline.ui.qt.runtime_theme_simple import THEME_ITEMS


def install():
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QMessageBox, QVBoxLayout
    from grace_pipeline.ui.qt import controller as c
    from grace_pipeline.ui.qt.preferences import UIPreferences
    def open_settings(self):
        d = QDialog(self.window)
        d.setWindowTitle(self.window.translate_text("Settings"))
        d.resize(460, 230)
        lay = QVBoxLayout(d)
        form = QFormLayout(); lay.addLayout(form)
        theme_box = QComboBox(); lang_box = QComboBox()
        for label, value in THEME_ITEMS:
            theme_box.addItem(self.window.translate_text(label), value)
        lang_box.addItem(self.window.translate_text("English"), "en")
        lang_box.addItem(self.window.translate_text("Chinese"), "zh")
        theme_box.setCurrentIndex(max(0, theme_box.findData(self.window.ui_preferences.theme)))
        lang_box.setCurrentIndex(max(0, lang_box.findData(self.window.ui_preferences.language)))
        form.addRow(QLabel(self.window.translate_text("Theme")), theme_box)
        form.addRow(QLabel(self.window.translate_text("Language")), lang_box)
        note = QLabel(self.window.translate_text("Choose between English and Simplified Chinese for the interface.")); note.setWordWrap(True); lay.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply); lay.addWidget(buttons)
        buttons.button(QDialogButtonBox.Ok).setText(self.window.translate_text("OK"))
        buttons.button(QDialogButtonBox.Cancel).setText(self.window.translate_text("Cancel"))
        buttons.button(QDialogButtonBox.Apply).setText(self.window.translate_text("Apply"))
        def run(close=False):
            buttons.setEnabled(False)
            pref = UIPreferences(str(theme_box.currentData()), str(lang_box.currentData()))
            def apply_now():
                try:
                    self.window.apply_ui_preferences(pref, persist=True)
                    d.accept() if close else buttons.setEnabled(True)
                except Exception as exc:
                    buttons.setEnabled(True); QMessageBox.warning(d, self.window.translate_text("Settings"), str(exc))
            QTimer.singleShot(0, apply_now)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(lambda: run(False))
        buttons.button(QDialogButtonBox.Ok).clicked.connect(lambda: run(True))
        buttons.button(QDialogButtonBox.Cancel).clicked.connect(d.reject)
        d.exec()
    c.MainWindowController.on_open_settings = open_settings
