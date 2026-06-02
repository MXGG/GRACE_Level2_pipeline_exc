from pathlib import Path
import re


def rewrite_pages() -> None:
    pages_path = Path(r"python/grace_pipeline/ui/qt/pages.py")
    text = pages_path.read_text(encoding="utf-8")
    new_class = """class LeakagePage(ScrollPage):
    def __init__(self):
        super().__init__("leakage")
        self.add_header("\\u6cc4\\u6f0f\\u6821\\u6b63")

        self.chk_leakage_enable = QCheckBox("\\u542f\\u7528\\u6cc4\\u6f0f\\u8bef\\u5dee\\u6821\\u6b63")
        self.chk_leakage_enable.setChecked(True)
        self.rb_method_fm = QRadioButton("FM")
        self.rb_method_sf = QRadioButton("SF")
        self.rb_method_sf.setChecked(True)
        self.rb_method_fm.hide()
        self.rb_method_sf.hide()

        self.btn_run_leakage = QPushButton("\\u8fd0\\u884c\\u6821\\u6b63")
        self.btn_run_leakage.setObjectName("PrimaryButton")
        self.btn_pause_leakage = QPushButton("\\u6682\\u505c")
        self.btn_pause_leakage.setObjectName("GhostButton")
        self.btn_stop_leakage = QPushButton("\\u505c\\u6b62")
        self.btn_stop_leakage.setObjectName("GhostButton")

        self.card_enable = CardFrame("\\u6a21\\u5757\\u72b6\\u6001")
        self.badge_product = build_badge("\\u4ea7\\u54c1\\u5f85\\u8bc6\\u522b", "primary")
        self.badge_operator = build_badge("\\u6ee4\\u6ce2\\u5f85\\u8bc6\\u522b", "primary")
        self.badge_scene = build_badge("\\u573a\\u666f\\u5f85\\u8bc6\\u522b", "primary")
        self.badge_strategy = build_badge("\\u7b56\\u7565\\u5f85\\u63a8\\u8350", "primary")
        top_row = QWidget()
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(10)
        top_row_layout.addWidget(self.chk_leakage_enable)
        top_row_layout.addStretch(1)
        top_row_layout.addWidget(self.badge_product)
        top_row_layout.addWidget(self.badge_operator)
        top_row_layout.addWidget(self.badge_scene)
        top_row_layout.addWidget(self.badge_strategy)
        self.card_enable.body.addWidget(top_row)
        self.lbl_scientific_note = QLabel(
            "\\u9ed8\\u8ba4\\u89c4\\u5219\\uff1a\\u533a\\u57df\\u95ee\\u9898\\u4f18\\u5148\\u533a\\u57df\\u5c3a\\u5ea6\\u56e0\\u5b50\\u6216\\u533a\\u57df FM\\uff1bGaussian \\u5168\\u7403\\u6d77\\u5cb8\\u7ebf\\u53ef\\u8d70\\u6d77\\u5cb8\\u7ebf\\u7b97\\u6cd5\\uff1bDDK\\u3001FAN\\u3001P4M6 \\u7b49\\u975e Gaussian \\u5168\\u7403\\u683c\\u7f51\\u9ed8\\u8ba4\\u63a8\\u8350\\u5168\\u7403\\u6b63\\u5219\\u5316\\u6062\\u590d\\u3002"
        )
        self.lbl_scientific_note.setWordWrap(True)
        self.card_enable.body.addWidget(self.lbl_scientific_note)

        self.card_input = CardFrame("\\u6570\\u636e\\u4e0e\\u8f93\\u51fa")
        self.edit_lrc_input = _make_line_edit("", "\\u8f93\\u5165\\u5f85\\u6821\\u6b63\\u6808\\uff0c\\u652f\\u6301 MAT / NC / HDF / TXT")
        self.btn_lrc_input_browse = QPushButton("\\u6d4f\\u89c8")
        self.btn_lrc_input_browse.setObjectName("GhostButton")
        self.edit_reference_input = _make_line_edit("", "\\u53c2\\u8003\\u6570\\u636e\\u6216\\u5b98\\u65b9 scaling/gain \\u6587\\u4ef6\\uff0c\\u53ef\\u9009")
        self.btn_reference_input_browse = QPushButton("\\u6d4f\\u89c8")
        self.btn_reference_input_browse.setObjectName("GhostButton")
        self.edit_regional_boundary = _make_line_edit("", "\\u533a\\u57df\\u6a21\\u5f0f\\u4e0b\\u4f7f\\u7528\\uff0c\\u652f\\u6301 shp / txt / bln")
        self.btn_regional_boundary_browse = QPushButton("\\u6d4f\\u89c8")
        self.btn_regional_boundary_browse.setObjectName("GhostButton")
        self.edit_lrc_output = _make_line_edit("", "\\u8f93\\u51fa\\u6587\\u4ef6\\u6216\\u76ee\\u5f55\\uff0c\\u7559\\u7a7a\\u65f6\\u81ea\\u52a8\\u751f\\u6210")
        self.btn_lrc_output_browse = QPushButton("\\u6d4f\\u89c8")
        self.btn_lrc_output_browse.setObjectName("GhostButton")
        self.lbl_leakage_info = QLabel("\\u5c1a\\u672a\\u8bfb\\u53d6\\u8f93\\u5165")
        self.lbl_dataset_shape_value = QLabel("-")
        self.lbl_product_type_value = QLabel("-")
        self.btn_load_leakage_info = QPushButton("\\u8bfb\\u53d6\\u8f93\\u5165\\u4fe1\\u606f")
        self.btn_load_leakage_info.setObjectName("GhostButton")
        self.btn_use_preview_stack = QPushButton("\\u4f7f\\u7528\\u9884\\u89c8\\u9875\\u6570\\u636e")
        self.btn_use_preview_stack.setObjectName("GhostButton")
        self.btn_use_basin_stack = QPushButton("\\u4f7f\\u7528\\u6d41\\u57df\\u9875\\u6570\\u636e")
        self.btn_use_basin_stack.setObjectName("GhostButton")
        self.lbl_linkage_status = QLabel("\\u5efa\\u8bae\\u5148\\u8bfb\\u53d6\\u8f93\\u5165\\u4fe1\\u606f\\uff0c\\u518d\\u786e\\u8ba4\\u63a8\\u8350\\u5de5\\u4f5c\\u6d41\\u3002")
        self.lbl_linkage_status.setWordWrap(True)
        self.card_input.body.addWidget(_make_field_row("\\u8f93\\u5165\\u6808", _make_edit_browse_widget(self.edit_lrc_input, self.btn_lrc_input_browse)))
        self.card_input.body.addWidget(_make_field_row("\\u53c2\\u8003\\u6570\\u636e", _make_edit_browse_widget(self.edit_reference_input, self.btn_reference_input_browse)))
        self.card_input.body.addWidget(_make_field_row("\\u533a\\u57df\\u8fb9\\u754c", _make_edit_browse_widget(self.edit_regional_boundary, self.btn_regional_boundary_browse)))
        self.card_input.body.addWidget(_make_field_row("\\u8f93\\u51fa\\u4f4d\\u7f6e", _make_edit_browse_widget(self.edit_lrc_output, self.btn_lrc_output_browse)))
        self.card_input.body.addWidget(
            _make_compact_field_grid(
                [("\\u8f93\\u5165\\u72b6\\u6001", self.lbl_leakage_info), ("\\u7f51\\u683c\\u5f62\\u72b6", self.lbl_dataset_shape_value), ("\\u4ea7\\u54c1\\u7c7b\\u578b", self.lbl_product_type_value)],
                columns=3,
            )
        )
        input_actions = QWidget()
        input_actions_layout = QHBoxLayout(input_actions)
        input_actions_layout.setContentsMargins(0, 0, 0, 0)
        input_actions_layout.setSpacing(8)
        input_actions_layout.addWidget(self.btn_load_leakage_info)
        input_actions_layout.addWidget(self.btn_use_preview_stack)
        input_actions_layout.addWidget(self.btn_use_basin_stack)
        input_actions_layout.addStretch(1)
        self.card_input.body.addWidget(input_actions)
        self.card_input.body.addWidget(self.lbl_linkage_status)

        self.card_strategy = CardFrame("\\u63a8\\u8350\\u4e0e\\u7b56\\u7565")
        self.cmb_scope = _make_choice_combo([("\\u533a\\u57df", "regional"), ("\\u5168\\u7403", "global")], "global")
        self.cmb_scope.hide()
        self.cmb_strategy_family = _make_choice_combo(
            [("\\u533a\\u57df\\u6a21\\u5f0f", "regional"), ("\\u5168\\u7403\\u6d77\\u5cb8\\u7ebf", "global_coastal"), ("\\u5168\\u7403\\u6062\\u590d", "global_regularized"), ("\\u5b98\\u65b9/\\u539f\\u751f", "official")],
            "regional",
        )
        self.cmb_correction_strategy = _make_choice_combo(
            [
                ("\\u81ea\\u52a8\\u63a8\\u8350", "auto"),
                ("\\u533a\\u57df\\u5c3a\\u5ea6\\u56e0\\u5b50", "basin_scale_factor"),
                ("\\u533a\\u57df\\u6b63\\u6f14\\u5efa\\u6a21", "forward_modeling"),
                ("\\u5168\\u7403\\u6d77\\u5cb8\\u7ebf Gaussian", "global_coastal_gaussian"),
                ("\\u5168\\u7403\\u6b63\\u5219\\u5316\\u6062\\u590d", "global_regularized"),
                ("\\u5b98\\u65b9\\u9646\\u5730 scaling", "official_land_scaling"),
                ("\\u5b98\\u65b9\\u6d77\\u6d0b\\u539f\\u751f", "official_ocean_native"),
                ("Mascon \\u539f\\u751f\\u900f\\u4f20", "official_mascon_native"),
                ("\\u683c\\u70b9\\u589e\\u76ca\\u56e0\\u5b50", "gridded_gain_factor"),
                ("\\u6a21\\u578b\\u52a0\\u6027\\u6821\\u6b63", "model_based_additive"),
            ],
            "auto",
        )
        self.cmb_scene_override = _make_choice_combo(
            [("\\u81ea\\u52a8\\u8bc6\\u522b", "auto"), ("\\u5185\\u9646\\u6d41\\u57df", "inland_basin"), ("\\u6e56\\u6cca/\\u6c34\\u5e93", "lake_reservoir"), ("\\u6d77\\u5cb8\\u5e26", "coastal"), ("\\u51b0\\u51bb\\u5708", "cryosphere")],
            "auto",
        )
        self.cmb_reference_mode = _make_choice_combo([("\\u8d8b\\u52bf\\u573a", "trend"), ("\\u5747\\u503c\\u573a", "mean"), ("\\u4e2d\\u4f4d\\u573a", "median"), ("\\u9996\\u65f6\\u6b21", "first")], "trend")
        self.cmb_official_mode = _make_choice_combo([("\\u81ea\\u52a8\\u8bc6\\u522b", "auto"), ("\\u9646\\u5730 scaling", "land_scaling"), ("\\u6d77\\u6d0b\\u539f\\u751f", "ocean_native"), ("Mascon \\u539f\\u751f", "mascon_native")], "auto")
        self.lbl_operator_value = QLabel("-")
        self.lbl_scene_value = QLabel("-")
        self.lbl_recommendation_value = QLabel("-")
        self.lbl_boundary_status = QLabel("-")
        self.card_strategy.body.addWidget(
            _make_compact_field_grid(
                [("\\u6ee4\\u6ce2\\u8bc6\\u522b", self.lbl_operator_value), ("\\u573a\\u666f\\u8bc6\\u522b", self.lbl_scene_value), ("\\u63a8\\u8350\\u7b56\\u7565", self.lbl_recommendation_value), ("\\u8fb9\\u754c\\u72b6\\u6001", self.lbl_boundary_status)],
                columns=2,
            )
        )
        self.card_strategy.body.addWidget(
            _make_compact_field_grid(
                [("\\u5de5\\u4f5c\\u6d41", self.cmb_strategy_family), ("\\u5177\\u4f53\\u7b56\\u7565", self.cmb_correction_strategy), ("\\u53c2\\u8003\\u6784\\u9020", self.cmb_reference_mode), ("\\u573a\\u666f\\u8986\\u76d6", self.cmb_scene_override), ("\\u5b98\\u65b9\\u6a21\\u5f0f", self.cmb_official_mode)],
                columns=3,
            )
        )
        self.lbl_method_hint = QLabel("\\u5148\\u8bfb\\u53d6\\u8f93\\u5165\\u4fe1\\u606f\\uff0c\\u7cfb\\u7edf\\u4f1a\\u6309\\u6ee4\\u6ce2\\u7c7b\\u578b\\u4e0e\\u5de5\\u4f5c\\u8303\\u56f4\\u63a8\\u8350\\u66f4\\u5408\\u9002\\u7684\\u6821\\u6b63\\u8def\\u5f84\\u3002")
        self.lbl_method_hint.setWordWrap(True)
        self.card_strategy.body.addWidget(self.lbl_method_hint)

        self.card_params = CardFrame("\\u53c2\\u6570")
        self.edit_lrc_sf_factor = _make_line_edit("1.0")
        self.edit_operator_autodetect = _make_line_edit("\\u81ea\\u52a8")
        self.edit_lrc_gaussian_km = _make_line_edit("300")
        self.edit_ddk_type = _make_line_edit("DDK4")
        self.cmb_lrc_format = _make_choice_combo([("MAT \\u6587\\u4ef6", "mat"), ("TXT \\u6587\\u4ef6", "txt")], "mat")
        self.edit_coastal_buffer_cells = _make_line_edit("3")
        self.edit_coastal_attenuation_gain = _make_line_edit("1.0")
        self.edit_regularized_lambda = _make_line_edit("0.08")
        self.edit_regularized_step_size = _make_line_edit("1.05")
        self.edit_regularized_sigma = _make_line_edit("0.9")
        self.edit_regularized_iter = _make_line_edit("20")
        self.params_common_panel = _make_compact_field_grid(
            [("\\u7b97\\u5b50\\u8bc6\\u522b", self.edit_operator_autodetect), ("Gaussian \\u534a\\u5f84 / km", self.edit_lrc_gaussian_km), ("\\u8f93\\u51fa\\u683c\\u5f0f", self.cmb_lrc_format)],
            columns=3,
        )
        self.params_regional_panel = _make_compact_field_grid(
            [("\\u5c3a\\u5ea6\\u56e0\\u5b50", self.edit_lrc_sf_factor), ("DDK \\u7c7b\\u578b", self.edit_ddk_type)],
            columns=2,
        )
        self.params_coastal_panel = _make_compact_field_grid(
            [("\\u6d77\\u5cb8\\u7f13\\u51b2\\u683c\\u70b9", self.edit_coastal_buffer_cells), ("\\u8870\\u51cf\\u589e\\u76ca", self.edit_coastal_attenuation_gain)],
            columns=2,
        )
        self.params_regularized_panel = _make_compact_field_grid(
            [("\\u6b63\\u5219\\u5f3a\\u5ea6 \\u03bb", self.edit_regularized_lambda), ("\\u6b65\\u957f", self.edit_regularized_step_size), ("\\u5e73\\u6ed1 \\u03c3", self.edit_regularized_sigma), ("\\u8fed\\u4ee3\\u6b21\\u6570", self.edit_regularized_iter)],
            columns=2,
        )
        self.card_params.body.addWidget(self.params_common_panel)
        self.card_params.body.addWidget(self.params_regional_panel)
        self.card_params.body.addWidget(self.params_coastal_panel)
        self.card_params.body.addWidget(self.params_regularized_panel)

        self.advanced_section = CollapsibleSection("\\u9ad8\\u7ea7\\u53c2\\u6570", expanded=False)
        self.edit_fm_iteration_count = _make_line_edit("40")
        self.edit_fm_convergence_threshold = _make_line_edit("0.01")
        self.edit_fm_acceleration = _make_line_edit("1.1")
        self.edit_fm_patience = _make_line_edit("8")
        self.edit_fm_min_improve = _make_line_edit("0.0001")
        self.edit_lrc_edge_buffer = _make_line_edit("2.0")
        self.advanced_section.body.addWidget(
            _make_compact_field_grid(
                [("FM \\u6700\\u5927\\u8fed\\u4ee3", self.edit_fm_iteration_count), ("FM \\u6536\\u655b\\u9608\\u503c", self.edit_fm_convergence_threshold), ("FM \\u52a0\\u901f\\u56e0\\u5b50", self.edit_fm_acceleration), ("FM \\u5bb9\\u5fcd\\u8f6e\\u6570", self.edit_fm_patience), ("\\u6700\\u5c0f\\u6539\\u5584\\u91cf", self.edit_fm_min_improve), ("\\u8fb9\\u754c\\u7f13\\u51b2 / \\u683c", self.edit_lrc_edge_buffer)],
                columns=3,
            )
        )
        self.card_params.body.addWidget(self.advanced_section)

        self.card_result = CardFrame("\\u7ed3\\u679c\\u5165\\u53e3")
        self.card_preview = self.card_result
        self.cmb_preview_layer = _make_choice_combo([("\\u6821\\u6b63\\u540e\\u6808", "corrected"), ("\\u5dee\\u503c\\u6808", "difference"), ("\\u539f\\u59cb\\u6808", "raw")], "corrected")
        self.cmb_preview_figure = _make_choice_combo([("\\u5168\\u7403\\u56fe", "representative_map"), ("\\u533a\\u57df\\u653e\\u5927\\u56fe", "representative_map_roi"), ("\\u65f6\\u95f4\\u5e8f\\u5217", "regional_series"), ("FM \\u8bca\\u65ad\\u56fe", "fm_rate_diagnostics")], "representative_map")
        self.cmb_preview_region = _make_choice_combo([("\\u4e3b\\u533a\\u57df", "main")], "main")
        self.cmb_preview_time = _make_choice_combo([("\\u5168\\u90e8\\u65f6\\u6b21", "all")], "all")
        self.btn_open_preview_asset = QPushButton("\\u6253\\u5f00\\u5f53\\u524d\\u7ed3\\u679c")
        self.btn_open_preview_asset.setObjectName("GhostButton")
        self.btn_open_preview_corrected = QPushButton("\\u5728\\u9884\\u89c8\\u9875\\u67e5\\u770b\\u6821\\u6b63\\u6808")
        self.btn_open_preview_corrected.setObjectName("GhostButton")
        self.lbl_preview_status = QLabel("\\u672c\\u9875\\u4e0d\\u518d\\u5185\\u5d4c\\u5730\\u56fe\\u9884\\u89c8\\u3002\\u8fd0\\u884c\\u5b8c\\u6210\\u540e\\u53ef\\u76f4\\u63a5\\u8df3\\u8f6c\\u5230 Preview \\u9875\\u67e5\\u770b\\u5168\\u7403\\u6216\\u533a\\u57df\\u7ed3\\u679c\\u3002")
        self.lbl_preview_status.setWordWrap(True)
        self.preview_image = QLabel("")
        self.preview_image.hide()
        self.card_result.body.addWidget(
            _make_compact_field_grid(
                [("\\u56fe\\u5c42", self.cmb_preview_layer), ("\\u56fe\\u4ef6", self.cmb_preview_figure), ("\\u533a\\u57df/\\u6d41\\u57df", self.cmb_preview_region), ("\\u65f6\\u6b21", self.cmb_preview_time)],
                columns=4,
            )
        )
        result_actions = QWidget()
        result_actions_layout = QHBoxLayout(result_actions)
        result_actions_layout.setContentsMargins(0, 0, 0, 0)
        result_actions_layout.setSpacing(8)
        result_actions_layout.addWidget(self.btn_open_preview_asset)
        result_actions_layout.addWidget(self.btn_open_preview_corrected)
        result_actions_layout.addStretch(1)
        self.card_result.body.addWidget(result_actions)
        self.card_result.body.addWidget(self.lbl_preview_status)

        self.card_note = CardFrame("\\u8bca\\u65ad\\u8bf4\\u660e")
        self.txt_leakage_notes = QTextEdit()
        self.txt_leakage_notes.setReadOnly(True)
        self.txt_leakage_notes.setMinimumHeight(170)
        self.txt_leakage_notes.setPlaceholderText("\\u8bfb\\u53d6\\u8f93\\u5165\\u4fe1\\u606f\\u540e\\uff0c\\u8fd9\\u91cc\\u4f1a\\u663e\\u793a\\u4ea7\\u54c1\\u8bc6\\u522b\\u3001\\u573a\\u666f\\u5224\\u65ad\\u3001\\u63a8\\u8350\\u8def\\u5f84\\u548c\\u9002\\u7528\\u6761\\u4ef6\\u3002")
        self.card_note.body.addWidget(self.txt_leakage_notes)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_pause_leakage)
        action_row.addWidget(self.btn_stop_leakage)
        action_row.addWidget(self.btn_run_leakage)

        middle_grid = QGridLayout()
        middle_grid.setHorizontalSpacing(18)
        middle_grid.setVerticalSpacing(18)
        middle_grid.addWidget(self.card_strategy, 0, 0)
        middle_grid.addWidget(self.card_params, 0, 1)
        middle_grid.setColumnStretch(0, 1)
        middle_grid.setColumnStretch(1, 1)

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(18)
        wrapper_layout.addLayout(action_row)
        wrapper_layout.addWidget(self.card_enable)
        wrapper_layout.addWidget(self.card_input)
        wrapper_layout.addLayout(middle_grid)
        wrapper_layout.addWidget(self.card_result)
        wrapper_layout.addWidget(self.card_note)
        self.body.addWidget(wrapper)
        self.body.addStretch(1)
"""
    start = text.index("class LeakagePage(ScrollPage):")
    end = text.index("\nclass BasinPage(ScrollPage):", start)
    text = text[:start] + new_class + "\n\nclass BasinPage(ScrollPage):" + text[end + len("\nclass BasinPage(ScrollPage):"):]
    pages_path.write_text(text, encoding="utf-8")


def rewrite_controller() -> None:
    path = Path(r"python/grace_pipeline/ui/qt/controller.py")
    text = path.read_text(encoding="utf-8")
    old = "from grace_pipeline.domain.leakage import classify_leakage_scene, infer_operator_spec, recommend_correction_method"
    new = "from grace_pipeline.domain.leakage import classify_leakage_scene, infer_operator_spec, recommend_correction_method, resolve_strategy_request"
    if old in text and new not in text:
        text = text.replace(old, new)

    start = text.index("    @staticmethod\n    def _leakage_label(value: str) -> str:\n")
    end = text.index("\n\n\n    def _sync_processing_hsaf_controls", start)
    text = text[:start] + """    @staticmethod
    def _leakage_label(value: str) -> str:
        mapping = {
            "grid_stack": "\\u7f51\\u683c\\u6808",
            "official_land_grid": "\\u5b98\\u65b9\\u9646\\u5730\\u683c\\u7f51",
            "official_scaling_grid": "\\u5b98\\u65b9\\u7f29\\u653e\\u683c\\u7f51",
            "mascon_native": "Mascon \\u539f\\u751f\\u4ea7\\u54c1",
            "FORWARD_MODELING": "\\u533a\\u57df\\u6b63\\u6f14\\u5efa\\u6a21",
            "BASIN_SCALE_FACTOR": "\\u533a\\u57df\\u5c3a\\u5ea6\\u56e0\\u5b50",
            "GRIDDED_GAIN_FACTOR": "\\u683c\\u70b9\\u589e\\u76ca\\u56e0\\u5b50",
            "OFFICIAL_SCALING": "\\u5b98\\u65b9\\u7f29\\u653e/\\u589e\\u76ca",
            "OFFICIAL_LAND_SCALING": "\\u5b98\\u65b9\\u9646\\u5730 scaling",
            "OFFICIAL_OCEAN_NATIVE": "\\u5b98\\u65b9\\u6d77\\u6d0b\\u539f\\u751f",
            "OFFICIAL_MASCON_NATIVE": "Mascon \\u539f\\u751f\\u900f\\u4f20",
            "GLOBAL_COASTAL_GAUSSIAN": "\\u5168\\u7403\\u6d77\\u5cb8\\u7ebf Gaussian",
            "GLOBAL_REGULARIZED": "\\u5168\\u7403\\u6b63\\u5219\\u5316\\u6062\\u590d",
            "MODEL_BASED_ADDITIVE": "\\u6a21\\u578b\\u52a0\\u6027\\u6821\\u6b63",
            "inland_basin": "\\u5185\\u9646\\u6d41\\u57df",
            "lake_reservoir": "\\u6e56\\u6cca/\\u6c34\\u5e93",
            "coastal": "\\u6d77\\u5cb8\\u5e26",
            "cryosphere": "\\u51b0\\u51bb\\u5708",
            "GAUSSIAN": "Gaussian",
            "FAN": "FAN",
            "P4M6": "P4M6",
            "DDK4": "DDK4",
            "HSAF": "HSAF",
            "NONE": "\\u672a\\u8bc6\\u522b",
            "regional": "\\u533a\\u57df\\u6a21\\u5f0f",
            "global": "\\u5168\\u7403\\u6a21\\u5f0f",
            "official": "\\u5b98\\u65b9/\\u539f\\u751f",
            "global_coastal": "\\u5168\\u7403\\u6d77\\u5cb8\\u7ebf",
            "global_regularized": "\\u5168\\u7403\\u6062\\u590d",
            "auto": "\\u81ea\\u52a8\\u63a8\\u8350",
            "none": "\\u65e0",
            "mean": "\\u5747\\u503c\\u573a",
            "median": "\\u4e2d\\u4f4d\\u573a",
            "trend": "\\u8d8b\\u52bf\\u573a",
            "first": "\\u9996\\u65f6\\u6b21",
            "direct": "\\u76f4\\u63a5\\u5e94\\u7528",
            "land_scaling": "\\u9646\\u5730 scaling",
            "ocean_native": "\\u6d77\\u6d0b\\u539f\\u751f",
        }
        return mapping.get(str(value), str(value))
""" + text[end:]

    # Additional leakage blocks were already made structurally correct in previous steps.
    # Only normalize visible strings here.
    replacements = {
        "输入信息已更新，可直接按推荐策略运行。": "\\u8f93\\u5165\\u4fe1\\u606f\\u5df2\\u66f4\\u65b0\\uff0c\\u53ef\\u76f4\\u63a5\\u6309\\u63a8\\u8350\\u7b56\\u7565\\u8fd0\\u884c\\u3002",
        "输入读取失败，请检查路径和数据结构。": "\\u8f93\\u5165\\u8bfb\\u53d6\\u5931\\u8d25\\uff0c\\u8bf7\\u68c0\\u67e5\\u8def\\u5f84\\u548c\\u6570\\u636e\\u7ed3\\u6784\\u3002",
        "尚未生成结果。运行完成后可在 Preview 页查看完整地图和时序结果。": "\\u5c1a\\u672a\\u751f\\u6210\\u7ed3\\u679c\\u3002\\u8fd0\\u884c\\u5b8c\\u6210\\u540e\\u53ef\\u5728 Preview \\u9875\\u67e5\\u770b\\u5b8c\\u6574\\u5730\\u56fe\\u548c\\u65f6\\u5e8f\\u7ed3\\u679c\\u3002",
        "结果索引已更新，但目标文件尚不可用。": "\\u7ed3\\u679c\\u7d22\\u5f15\\u5df2\\u66f4\\u65b0\\uff0c\\u4f46\\u76ee\\u6807\\u6587\\u4ef6\\u5c1a\\u4e0d\\u53ef\\u7528\\u3002",
        "尚未生成结果。本页仅保留结果入口，地图渲染请转到 Preview 页。": "\\u5c1a\\u672a\\u751f\\u6210\\u7ed3\\u679c\\u3002\\u672c\\u9875\\u4ec5\\u4fdd\\u7559\\u7ed3\\u679c\\u5165\\u53e3\\uff0c\\u5730\\u56fe\\u6e32\\u67d3\\u8bf7\\u8f6c\\u5230 Preview \\u9875\\u3002",
        "区域模式适用于流域、湖泊和局部海岸区。默认推荐区域尺度因子；需要幅值恢复时再使用区域 FM。": "\\u533a\\u57df\\u6a21\\u5f0f\\u9002\\u7528\\u4e8e\\u6d41\\u57df\\u3001\\u6e56\\u6cca\\u548c\\u5c40\\u90e8\\u6d77\\u5cb8\\u533a\\u3002\\u9ed8\\u8ba4\\u63a8\\u8350\\u533a\\u57df\\u5c3a\\u5ea6\\u56e0\\u5b50\\uff1b\\u9700\\u8981\\u5e45\\u503c\\u6062\\u590d\\u65f6\\u518d\\u4f7f\\u7528\\u533a\\u57df FM\\u3002",
        "全球海岸线模式仅适用于标准 Gaussian 路线。运行时会优先使用海陆分离的海岸线校正。": "\\u5168\\u7403\\u6d77\\u5cb8\\u7ebf\\u6a21\\u5f0f\\u4ec5\\u9002\\u7528\\u4e8e\\u6807\\u51c6 Gaussian \\u8def\\u7ebf\\u3002\\u8fd0\\u884c\\u65f6\\u4f1a\\u4f18\\u5148\\u4f7f\\u7528\\u6d77\\u9646\\u5206\\u79bb\\u7684\\u6d77\\u5cb8\\u7ebf\\u6821\\u6b63\\u3002",
        "当前滤波不是 Gaussian 路线。按文献定义不适用全球海岸线 Gaussian 算法，运行时会自动转为全球正则化恢复。": "\\u5f53\\u524d\\u6ee4\\u6ce2\\u4e0d\\u662f Gaussian \\u8def\\u7ebf\\u3002\\u6309\\u6587\\u732e\\u5b9a\\u4e49\\u4e0d\\u9002\\u7528\\u5168\\u7403\\u6d77\\u5cb8\\u7ebf Gaussian \\u7b97\\u6cd5\\uff0c\\u8fd0\\u884c\\u65f6\\u4f1a\\u81ea\\u52a8\\u8f6c\\u4e3a\\u5168\\u7403\\u6b63\\u5219\\u5316\\u6062\\u590d\\u3002",
        "全球恢复模式适用于 DDK、FAN、P4M6 等非 Gaussian 全球格网，重点恢复空间分布而不是区域单值缩放。": "\\u5168\\u7403\\u6062\\u590d\\u6a21\\u5f0f\\u9002\\u7528\\u4e8e DDK\\u3001FAN\\u3001P4M6 \\u7b49\\u975e Gaussian \\u5168\\u7403\\u683c\\u7f51\\uff0c\\u91cd\\u70b9\\u6062\\u590d\\u7a7a\\u95f4\\u5206\\u5e03\\u800c\\u4e0d\\u662f\\u533a\\u57df\\u5355\\u503c\\u7f29\\u653e\\u3002",
        "官方/原生模式用于官方 scaling、官方海洋产品或 mascon 原生结果，不再重复做球谐泄漏校正。": "\\u5b98\\u65b9/\\u539f\\u751f\\u6a21\\u5f0f\\u7528\\u4e8e\\u5b98\\u65b9 scaling\\u3001\\u5b98\\u65b9\\u6d77\\u6d0b\\u4ea7\\u54c1\\u6216 mascon \\u539f\\u751f\\u7ed3\\u679c\\uff0c\\u4e0d\\u518d\\u91cd\\u590d\\u505a\\u7403\\u8c10\\u6cc4\\u6f0f\\u6821\\u6b63\\u3002",
    }
    for plain, escaped in replacements.items():
        text = text.replace(plain, escaped)
    path.write_text(text, encoding="utf-8")


def rewrite_mock_data() -> None:
    mock_path = Path(r"python/grace_pipeline/ui/qt/mock_data.py")
    mock = mock_path.read_text(encoding="utf-8")
    mock = mock.replace('("leakage", "Leakage Correction")', '("leakage", "\\u6cc4\\u6f0f\\u6821\\u6b63")')
    mock = mock.replace('"leakage": "Leakage Correction",', '"leakage": "\\u6cc4\\u6f0f\\u6821\\u6b63",')
    mock = mock.replace(
        '"leakage": "Choose correction method and inspect boundary-driven leakage inputs.",',
        '"leakage": "\\u9009\\u62e9\\u6821\\u6b63\\u5de5\\u4f5c\\u6d41\\uff0c\\u8bfb\\u53d6\\u8f93\\u5165\\u4fe1\\u606f\\uff0c\\u5e76\\u5c06\\u7ed3\\u679c\\u8f6c\\u4ea4 Preview \\u9875\\u67e5\\u770b\\u3002",',
    )
    mock_path.write_text(mock, encoding="utf-8")


if __name__ == "__main__":
    rewrite_pages()
    rewrite_controller()
    rewrite_mock_data()
    print("fixed leakage ui text")
