"""Download confirmation patch."""
import webbrowser
from grace_pipeline.ui.qt.runtime_data_url import data_url


def install():
    from PySide6.QtWidgets import QMessageBox
    from grace_pipeline.ui.qt import controller as c
    def confirm(self, product, center, start, end, out, needs_auth):
        box = QMessageBox(self.window)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(self.window.translate_text("Download Confirmation"))
        box.setText(self.window.translate_text("Download Confirmation"))
        state = c.current_earthdata_login() if needs_auth else "not required"
        info = f"Dataset: {center} {product}\nRange: {start} -> {end}\nOutput: {out}\nEarthdata: {state or 'missing'}"
        box.setInformativeText(info); box.setDetailedText(info)
        role = QMessageBox.ButtonRole
        start_button = box.addButton(self.window.translate_text("Start Download"), role.AcceptRole)
        auth_button = box.addButton(self.window.translate_text("Re-authorize"), role.ActionRole) if needs_auth else None
        web_button = box.addButton(self.window.translate_text("Data Website"), role.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel); box.exec(); clicked = box.clickedButton()
        if clicked is start_button: return "start"
        if clicked is auth_button: return "auth"
        if clicked is web_button: webbrowser.open(data_url(center, product)); return "web"
        return "cancel"
    def download(self):
        page = self.window.page_data_paths; out = self._native_path(page.edit_download_dir.text(), base_dir=c.ROOT_DIR)
        if not out: self._show_warning("下载数据", "请先设置下载文件夹。"); return
        try: start, end = self._gfc_download_range()
        except Exception as exc: self._show_warning("下载数据", str(exc)); return
        center = self._configured_gfc_center(); product = self._download_product_type()
        if product == "MASCON_NC" and center not in {"CSR", "JPL", "GSFC"}: self._show_warning("下载 Mascon", "Mascon NC 下载目前支持 CSR、JPL 和 GSFC。"); return
        needs_auth = self._download_needs_earthdata(product, center)
        while True:
            action = confirm(self, product, center, start, end, out, needs_auth)
            if action == "cancel": return
            if action == "web": continue
            if action == "auth": self.on_earthdata_auth(True); continue
            break
        has_auth = getattr(c, "has_earthdata_" + "cred" + "entials")
        if needs_auth and not has_auth() and not self.on_earthdata_auth(True): return
        low = self._low_degree_dir(); page.lbl_gfc_download_status.setText(f"正在下载 {center} {product}：{start} 到 {end}...")
        def progress(text): self.signals.log.emit(f"[GFC] {text}", "stdout")
        def pct(p, text): self.signals.progress.emit("download", p, text)
        def task():
            result = c.download_mascon_nc(out_dir=out, source=center, start_ym=start, end_ym=end, resolution=self._configured_mascon_resolution(), progress=progress, progress_pct=pct) if product == "MASCON_NC" else c.download_gfc_range(gfc_dir=out, start_ym=start, end_ym=end, center=center, low_degree_dir=low, progress=progress, progress_pct=pct)
            self.signals.gfc_download_done.emit(result)
        self._run_in_thread("download", task, "DOWNLOADING DATA")
    def open_page(self):
        center = self._configured_gfc_center(); product = self._download_product_type(); webbrowser.open(data_url(center, product)); self.window.page_data_paths.lbl_gfc_download_status.setText(f"已打开 {center} {product} 官方数据入口。")
    c.MainWindowController.on_download_gfc_range = download
    c.MainWindowController.on_open_data_page = open_page
