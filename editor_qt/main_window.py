"""Main Qt editor window."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QSplitter,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from editor_qt.bridge.engine_facade import EditorEngineFacade
from editor_qt.panels.agent_panel import AgentPanel
from editor_qt.panels.animator_panel import AnimatorPanel
from editor_qt.panels.console_panel import ConsolePanel
from editor_qt.panels.flow_panel import FlowPanel
from editor_qt.panels.hierarchy_panel import HierarchyPanel
from editor_qt.panels.inspector_panel import InspectorPanel
from editor_qt.panels.project_panel import ProjectPanel
from editor_qt.panels.sprite_editor_dialog import open_sprite_editor
from editor_qt.panels.terminal_panel import TerminalPanel
from editor_qt.panels.viewport_panel import QtSceneViewportPanel
from editor_qt.theme import (
    DEFAULT_THEME,
    load_editor_icon,
    load_editor_pixmap,
    load_theme,
    normalize_theme_name,
)
from editor_qt.value_codec import parse_value


class MainWindow(QMainWindow):
    """Fixed editor shell shaped like the legacy editor, backed by EngineAPI."""

    def __init__(
        self,
        facade: EditorEngineFacade | None = None,
        initial_scene: str = "",
        initial_theme: str = "",
    ) -> None:
        super().__init__()
        self.setObjectName("AppRoot")
        self.facade = facade or EditorEngineFacade()
        self.initial_scene = initial_scene
        self._active_center_tab = "Scene"
        self._base_center_tab_count = 4
        self._loading_preferences = False
        self._scene_selector_loading = False
        self._editor_state = self.facade.get_editor_state()
        self._preferences = self._extract_preferences(self._editor_state)
        self._theme_name = self._resolve_initial_theme(initial_theme)
        app = QApplication.instance()
        if app is not None:
            load_theme(cast(QApplication, app), self._theme_name)

        self.setWindowTitle("MotorVideojuegosIA Editor")
        self.resize(1440, 860)

        self.hierarchy_panel = HierarchyPanel()
        self.inspector_panel = InspectorPanel()
        self.inspector_panel.set_component_descriptors(self.facade.list_component_descriptors())
        self.project_panel = ProjectPanel()
        self.console_panel = ConsolePanel()
        self.scene_viewport = QtSceneViewportPanel("Scene")
        self.game_viewport = QtSceneViewportPanel("Game")
        self.flow_panel = FlowPanel("Scene Flow")
        self.flow_tools_panel = FlowPanel("Flow Tools")
        self.animator_panel = AnimatorPanel()
        self.terminal_panel = TerminalPanel()
        self.agent_panel = AgentPanel()
        self._agent_session_id = ""
        self._dragging_asset: str = ""
        self._dragging_asset_type: str = ""

        self._build_actions()
        self._build_menu_bar()
        self._build_toolbar()
        self._build_shell()
        self._apply_saved_preferences()
        self._connect_signals()

        self.console_panel.log("Qt editor initialized.")
        self._refresh_project_panel()
        self._load_initial_scene()

    def _extract_preferences(self, state: dict[str, Any]) -> dict[str, Any]:
        preferences = state.get("preferences", {}) if isinstance(state, dict) else {}
        return dict(preferences) if isinstance(preferences, dict) else {}

    def _resolve_initial_theme(self, initial_theme: str) -> str:
        if initial_theme:
            return normalize_theme_name(initial_theme)
        saved = str(self._preferences.get("theme") or "")
        return normalize_theme_name(saved or DEFAULT_THEME)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_ui_preferences()
        if not self.facade.has_unsaved_changes():
            event.accept()
            return
        choice = self._confirm_close_with_unsaved_changes()
        if choice == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        if choice == QMessageBox.StandardButton.Save:
            result = self.facade.save_scene()
            self._log_action_result(result)
            if not result.get("success"):
                event.ignore()
                self._refresh_project_panel()
                return
        event.accept()

    def _confirm_close_with_unsaved_changes(self) -> QMessageBox.StandardButton:
        return QMessageBox.warning(
            self,
            "Unsaved Scene",
            "The active scene has unsaved changes.",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

    def _build_actions(self) -> None:
        self.new_scene_action = QAction("New", self)
        self.open_scene_action = QAction("Open", self)
        self.save_scene_action = QAction("Save", self)
        self.exit_action = QAction("Exit", self)

        self.undo_action = QAction("Undo", self)
        self.redo_action = QAction("Redo", self)
        self.refresh_action = QAction("Refresh", self)
        self.refresh_assets_action = QAction("Refresh Assets", self)
        self.project_action = QAction("Project", self)

        self.create_empty_action = QAction("Create Empty", self)
        self.create_canvas_action = QAction("Canvas", self)
        self.create_text_action = QAction("Text", self)
        self.create_button_action = QAction("Button", self)
        self.add_component_action = QAction("Add Component", self)
        self.add_component_action.setEnabled(False)

        self.select_tool_action = QAction("Select", self)
        self.move_tool_action = QAction("Move", self)
        self.rotate_tool_action = QAction("Rotate", self)
        self.scale_tool_action = QAction("Scale", self)
        for action in (
            self.select_tool_action,
            self.move_tool_action,
            self.rotate_tool_action,
            self.scale_tool_action,
        ):
            action.setCheckable(True)
        self.select_tool_action.setChecked(True)

        self.play_action = QAction("Play", self)
        self.pause_action = QAction("Pause", self)
        self.step_action = QAction("Step", self)
        for action in (self.play_action, self.pause_action, self.step_action):
            action.setEnabled(False)
            action.setToolTip("Runtime playback is not wired in the Qt editor yet.")
        self.build_action = QAction("Build", self)
        self.launch_action = QAction("Launch", self)
        for action in (self.build_action, self.launch_action):
            action.setEnabled(False)
            action.setToolTip("Build/launch is not wired in the Qt editor yet.")

        self.reset_camera_action = QAction("Reset Camera", self)
        self.frame_selected_action = QAction("Frame Selected", self)
        self.theme_action = QAction("Light Theme" if self._theme_name == "frost_dark" else "Dark Theme", self)

    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.new_scene_action)
        file_menu.addAction(self.open_scene_action)
        file_menu.addAction(self.save_scene_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = self.menuBar().addMenu("Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)

        assets_menu = self.menuBar().addMenu("Assets")
        assets_menu.addAction(self.refresh_assets_action)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.reset_camera_action)
        view_menu.addAction(self.frame_selected_action)
        view_menu.addSeparator()
        view_menu.addAction(self.theme_action)

        game_object_menu = self.menuBar().addMenu("GameObject")
        game_object_menu.addAction(self.create_empty_action)
        game_object_menu.addSeparator()
        game_object_menu.addAction(self.create_canvas_action)
        game_object_menu.addAction(self.create_text_action)
        game_object_menu.addAction(self.create_button_action)

        component_menu = self.menuBar().addMenu("Component")
        component_menu.addAction(self.add_component_action)

        window_menu = self.menuBar().addMenu("Window")
        for label in ("Scene", "Game", "Flow", "Animator"):
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, name=label: self._focus_center_tab(name))
            window_menu.addAction(action)
        window_menu.addSeparator()
        for label in ("Project", "Flow", "Console", "Terminal", "Agent"):
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, name=label: self._focus_bottom_tab(name))
            window_menu.addAction(action)

        help_menu = self.menuBar().addMenu("Help")
        about_action = QAction("About Qt Editor", self)
        about_action.triggered.connect(lambda _checked=False: self.console_panel.log("Qt editor shell: experimental/tooling."))
        help_menu.addAction(about_action)

    def _build_toolbar(self) -> None:
        self.top_bar = QFrame()
        self.top_bar.setObjectName("TopBar")
        layout = QHBoxLayout(self.top_bar)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        logo_group = self._create_topbar_group("TopBarLogoGroup")
        logo_layout = cast(QHBoxLayout, logo_group.layout())
        logo_pixmap = load_editor_pixmap("brand", "logo_frostline.png")
        if logo_pixmap is not None:
            logo_mark = QLabel()
            logo_mark.setObjectName("TopBarLogoImage")
            logo_mark.setPixmap(logo_pixmap.scaledToHeight(46, Qt.TransformationMode.SmoothTransformation))
            logo_layout.addWidget(logo_mark)
        else:
            logo_mark = QLabel("*")
            logo_mark.setObjectName("TopBarLogoMark")
            logo_wordmark = QLabel("FROSTLINE\nENGINE")
            logo_wordmark.setObjectName("TopBarLogo")
            logo_layout.addWidget(logo_mark)
            logo_layout.addWidget(logo_wordmark)
        layout.addWidget(logo_group)

        self.project_combo = QComboBox()
        self.project_combo.setObjectName("ProjectSelector")
        self.project_combo.setMinimumWidth(160)
        self.project_combo.setEnabled(False)
        self.project_combo.setToolTip("Active project")
        project_group = self._create_topbar_labeled_group("Project", self.project_combo)
        project_group.setObjectName("TopBarProjectGroup")
        layout.addWidget(project_group)

        self.scene_combo = QComboBox()
        self.scene_combo.setObjectName("SceneSelector")
        self.scene_combo.setMinimumWidth(180)
        self.scene_combo.setToolTip("Active scene")
        scene_group = self._create_topbar_labeled_group("Scene", self.scene_combo)
        scene_group.setObjectName("TopBarSceneGroup")
        layout.addWidget(scene_group)

        transform_group = self._create_topbar_group("TopBarTransformGroup")
        transform_layout = cast(QHBoxLayout, transform_group.layout())
        transform_layout.addWidget(self._make_action_button(self.select_tool_action, "Select", "icons/tool_select.png", "SP_ArrowUp"))
        transform_layout.addWidget(self._make_action_button(self.move_tool_action, "Move", "icons/tool_move.png", "SP_ArrowForward"))
        transform_layout.addWidget(self._make_action_button(self.rotate_tool_action, "Rotate", "icons/tool_rotate.png", "SP_BrowserReload"))
        transform_layout.addWidget(self._make_action_button(self.scale_tool_action, "Scale", "icons/tool_scale.png", "SP_TitleBarMaxButton"))
        layout.addWidget(transform_group)

        playback_group = self._create_topbar_group("TopBarPlaybackGroup")
        playback_layout = cast(QHBoxLayout, playback_group.layout())
        playback_layout.addWidget(self._make_action_button(self.play_action, "Play", "icons/tool_play.png", "SP_MediaPlay"))
        playback_layout.addWidget(self._make_action_button(self.pause_action, "Pause", "icons/tool_pause.png", "SP_MediaPause"))
        playback_layout.addWidget(self._make_action_button(self.step_action, "Stop", "icons/tool_stop.png", "SP_MediaStop"))
        layout.addWidget(playback_group)

        deploy_group = self._create_topbar_group("TopBarDeployGroup")
        deploy_layout = cast(QHBoxLayout, deploy_group.layout())
        deploy_layout.addWidget(self._make_action_button(self.build_action, "Build", "icons/tool_build.png", "SP_DialogSaveButton"))
        deploy_layout.addWidget(self._make_action_button(self.launch_action, "Launch", "icons/tool_launch.png", "SP_ArrowUp"))
        layout.addWidget(deploy_group)

        layout.addStretch(1)

        utility_group = self._create_topbar_group("TopBarUtilityGroup")
        utility_layout = cast(QHBoxLayout, utility_group.layout())
        utility_layout.addWidget(self._make_action_button(self.undo_action, "Undo", "icons/tool_undo.png", "SP_ArrowBack"))
        utility_layout.addWidget(self._make_action_button(self.redo_action, "Redo", "icons/tool_redo.png", "SP_ArrowForward"))
        utility_layout.addWidget(self._make_action_button(self.theme_action, "Theme", "icons/tool_theme.png", "SP_FileDialogDetailedView"))
        layout.addWidget(utility_group)

        account_group = self._create_topbar_group("TopBarAccountGroup")
        account_layout = cast(QHBoxLayout, account_group.layout())
        self.account_button = QToolButton()
        self.account_button.setObjectName("AccountButton")
        avatar_icon = load_editor_icon("brand", "avatar_a.png")
        if not avatar_icon.isNull():
            self.account_button.setIcon(avatar_icon)
            self.account_button.setIconSize(QSize(30, 30))
        else:
            self.account_button.setText("A")
        self.account_button.setToolTip("Account menu is not wired in the Qt editor yet.")
        self.account_button.setEnabled(False)
        self.account_button.setFixedSize(QSize(34, 34))
        self.account_menu_button = QToolButton()
        self.account_menu_button.setObjectName("AccountMenuButton")
        self.account_menu_button.setText("v")
        self.account_menu_button.setEnabled(False)
        self.account_menu_button.setToolTip("Account menu is not wired in the Qt editor yet.")
        account_layout.addWidget(self.account_button)
        account_layout.addWidget(self.account_menu_button)
        layout.addWidget(account_group)

        self.layers_combo = QComboBox()
        self.layers_combo.setObjectName("LayersCombo")
        self.layers_combo.addItems(["Layers", "Default"])
        self.layers_combo.setEnabled(False)
        self.layers_combo.setToolTip("Layer filtering is not wired in the Qt editor yet.")

        self.layout_combo = QComboBox()
        self.layout_combo.setObjectName("LayoutCombo")
        self.layout_combo.addItems(["Layout", "Default"])
        self.layout_combo.setEnabled(False)
        self.layout_combo.setToolTip("Layout presets are not wired in the Qt editor yet.")

    def _create_topbar_group(self, object_name: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName(object_name)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        return frame

    def _create_topbar_labeled_group(self, label_text: str, widget: QWidget) -> QFrame:
        frame = self._create_topbar_group("TopBarSelectGroup")
        layout = cast(QHBoxLayout, frame.layout())
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)
        label = QLabel(label_text)
        label.setObjectName("TopBarFieldLabel")
        column.addWidget(label)
        column.addWidget(widget)
        layout.addLayout(column)
        return frame

    def _make_action_button(self, action: QAction, label: str, asset_rel: str, icon_name: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName("TopBarActionButton")
        button.setDefaultAction(action)
        button.setText(label)
        button.setIcon(self._style_icon(asset_rel, icon_name))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setAutoRaise(False)
        button.setIconSize(QSize(18, 18))
        return button

    def _style_icon(self, asset_rel: str, icon_name: str) -> QIcon:
        if asset_rel:
            asset_parts = tuple(asset_rel.split("/"))
            icon = load_editor_icon(*asset_parts)
            if not icon.isNull():
                return icon
        style = self.style()
        if style is None:
            return QIcon()
        icon_enum = getattr(QStyle.StandardPixmap, icon_name, None)
        if icon_enum is None:
            return QIcon()
        return style.standardIcon(icon_enum)

    def _build_shell(self) -> None:
        self.center_tabs = QTabWidget()
        self.center_tabs.setObjectName("CenterTabs")
        self.center_tabs.addTab(self.scene_viewport, "Scene")
        self.center_tabs.addTab(self.game_viewport, "Game")
        self.center_tabs.addTab(self.flow_panel, "Flow")
        self.center_tabs.addTab(self.animator_panel, "Animator")

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setObjectName("BottomTabs")
        self.bottom_tabs.addTab(self.project_panel, "Project")
        self.bottom_tabs.addTab(self.flow_tools_panel, "Flow")
        self.bottom_tabs.addTab(self.console_panel, "Console")
        self.bottom_tabs.addTab(self.terminal_panel, "Terminal")
        self.bottom_tabs.addTab(self.agent_panel, "Agent")

        self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.top_splitter.setObjectName("MainHorizontalSplitter")
        self.top_splitter.addWidget(self.hierarchy_panel)
        self.top_splitter.addWidget(self.center_tabs)
        self.top_splitter.addWidget(self.inspector_panel)
        self.top_splitter.setStretchFactor(0, 0)
        self.top_splitter.setStretchFactor(1, 1)
        self.top_splitter.setStretchFactor(2, 0)
        self.top_splitter.setSizes([240, 900, 320])

        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setObjectName("MainVerticalSplitter")
        self.main_splitter.addWidget(self.top_splitter)
        self.main_splitter.addWidget(self.bottom_tabs)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([620, 240])

        root = QWidget()
        root.setObjectName("AppRoot")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(8, 8, 8, 8)
        shell.setSpacing(8)
        content = QWidget()
        content.setObjectName("AppShell")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        content_layout.addWidget(self.top_bar)
        content_layout.addWidget(self.main_splitter, stretch=1)
        shell.addWidget(self._build_left_rail())
        shell.addWidget(content, stretch=1)
        self.setCentralWidget(root)

    def _build_left_rail(self) -> QWidget:
        rail = QFrame()
        rail.setObjectName("SideRail")
        rail.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(6)
        self._rail_buttons: dict[str, QToolButton] = {}
        for label, target, asset_rel, icon_name in (
            ("Hierarchy", "Hierarchy", "icons/rail_hierarchy.png", "SP_FileDialogListView"),
            ("Scenes", "Scene", "icons/rail_scenes.png", "SP_FileDialogContentsView"),
            ("World", "Game", "icons/rail_world.png", "SP_ComputerIcon"),
            ("Lighting", "Console", "icons/rail_lighting.png", "SP_DialogYesButton"),
            ("Scripting", "Agent", "icons/rail_scripting.png", "SP_FileIcon"),
            ("Audio", "Project", "icons/rail_audio.png", "SP_MediaVolume"),
            ("Settings", "Settings", "icons/rail_settings.png", "SP_FileDialogDetailedView"),
        ):
            button = QToolButton()
            button.setObjectName("RailButton")
            button.setText(label)
            button.setIcon(self._style_icon(asset_rel, icon_name))
            button.setCheckable(True)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda _checked=False, value=target: self._focus_rail_target(value))
            self._rail_buttons[target] = button
            layout.addWidget(button)
        layout.addStretch()
        return rail

    def _apply_saved_preferences(self) -> None:
        self._loading_preferences = True
        try:
            main_sizes = self._preferences.get("main_splitter_sizes")
            if isinstance(main_sizes, list) and len(main_sizes) == 2:
                self.main_splitter.setSizes([int(value) for value in main_sizes])
            top_sizes = self._preferences.get("top_splitter_sizes")
            if isinstance(top_sizes, list) and len(top_sizes) == 3:
                self.top_splitter.setSizes([int(value) for value in top_sizes])
            self.project_panel.set_view_mode(str(self._preferences.get("project_view_mode") or "grid"))
            center_tab = str(self._preferences.get("center_tab") or "Scene")
            bottom_tab = str(self._preferences.get("bottom_tab") or "Project")
            self._focus_center_tab(center_tab)
            self._focus_bottom_tab(bottom_tab)
            self._set_rail_active(str(self._preferences.get("rail_active") or "Scene"))
        finally:
            self._loading_preferences = False

    def _save_ui_preferences(self, extra: dict[str, Any] | None = None) -> None:
        if self._loading_preferences:
            return
        preferences = {
            "theme": self._theme_name,
            "main_splitter_sizes": self.main_splitter.sizes() if hasattr(self, "main_splitter") else [],
            "top_splitter_sizes": self.top_splitter.sizes() if hasattr(self, "top_splitter") else [],
            "center_tab": self._active_center_tab,
            "bottom_tab": self.bottom_tabs.tabText(self.bottom_tabs.currentIndex()) if hasattr(self, "bottom_tabs") else "Project",
            "rail_active": self._current_rail_target(),
            "project_view_mode": self.project_panel.view_mode(),
        }
        if extra:
            preferences.update(extra)
        self._preferences.update(preferences)
        self.facade.save_editor_preferences(preferences)

    def _focus_rail_target(self, target: str) -> None:
        if target in {"Scene", "Game", "Flow", "Animator"}:
            self._focus_center_tab(target)
        elif target in {"Project", "Console", "Terminal", "Agent"}:
            self._focus_bottom_tab(target)
        elif target == "Settings":
            self.console_panel.log("Settings panel is not wired in the Qt editor yet.", "warning")
        self._set_rail_active(target)
        self._save_ui_preferences({"rail_active": target})

    def _set_rail_active(self, target: str) -> None:
        for label, button in getattr(self, "_rail_buttons", {}).items():
            button.setChecked(label == target)

    def _current_rail_target(self) -> str:
        for label, button in getattr(self, "_rail_buttons", {}).items():
            if button.isChecked():
                return label
        return "Scene"

    def _connect_signals(self) -> None:
        self.new_scene_action.triggered.connect(lambda _checked=False: self._request_new_scene())
        self.open_scene_action.triggered.connect(lambda _checked=False: self._focus_project_panel())
        self.save_scene_action.triggered.connect(lambda _checked=False: self._save_scene())
        self.exit_action.triggered.connect(lambda _checked=False: self.close())
        self.undo_action.triggered.connect(lambda _checked=False: self._undo())
        self.redo_action.triggered.connect(lambda _checked=False: self._redo())
        self.refresh_action.triggered.connect(lambda _checked=False: self._refresh_scene_panels())
        self.refresh_assets_action.triggered.connect(lambda _checked=False: self._refresh_assets())
        self.project_action.triggered.connect(lambda _checked=False: self._focus_project_panel())
        self.theme_action.triggered.connect(lambda _checked=False: self._toggle_theme())
        self.reset_camera_action.triggered.connect(lambda _checked=False: self._reset_active_viewport_camera())
        self.frame_selected_action.triggered.connect(lambda _checked=False: self._frame_selected_in_active_viewport())
        self.scene_combo.activated.connect(self._on_scene_selector_activated)

        self.create_empty_action.triggered.connect(lambda _checked=False: self._request_create_empty_entity())
        self.create_canvas_action.triggered.connect(lambda _checked=False: self._create_canvas())
        self.create_text_action.triggered.connect(lambda _checked=False: self._create_ui_text())
        self.create_button_action.triggered.connect(lambda _checked=False: self._create_ui_button())

        self.select_tool_action.triggered.connect(lambda _checked=False: self._select_tool(self.select_tool_action))
        self.move_tool_action.triggered.connect(lambda _checked=False: self._select_tool(self.move_tool_action))
        self.rotate_tool_action.triggered.connect(lambda _checked=False: self._select_tool(self.rotate_tool_action))
        self.scale_tool_action.triggered.connect(lambda _checked=False: self._select_tool(self.scale_tool_action))

        self.center_tabs.currentChanged.connect(self._on_center_tab_changed)
        self.bottom_tabs.currentChanged.connect(self._on_bottom_tab_changed)
        self.scene_viewport.entity_selected.connect(self._on_entity_selected)
        self.game_viewport.entity_selected.connect(self._on_entity_selected)
        self.scene_viewport.entity_moved.connect(self._on_gizmo_entity_moved)
        self.game_viewport.entity_moved.connect(self._on_gizmo_entity_moved)
        self.scene_viewport.entity_rotated.connect(self._on_gizmo_entity_rotated)
        self.game_viewport.entity_rotated.connect(self._on_gizmo_entity_rotated)
        self.scene_viewport.entity_scaled.connect(self._on_gizmo_entity_scaled)
        self.game_viewport.entity_scaled.connect(self._on_gizmo_entity_scaled)
        # Viewport drop support (accept drops from project panel)
        self.scene_viewport.asset_dropped.connect(self._on_viewport_asset_dropped)
        self.game_viewport.asset_dropped.connect(self._on_viewport_asset_dropped)
        self.flow_panel.connection_set_requested.connect(self._set_scene_connection)
        self.flow_tools_panel.connection_set_requested.connect(self._set_scene_connection)
        self.flow_panel.refresh_requested.connect(self._refresh_scene_panels)
        self.flow_tools_panel.refresh_requested.connect(self._refresh_scene_panels)
        self.animator_panel.ensure_requested.connect(self._ensure_animator)
        self.animator_panel.sprite_sheet_set_requested.connect(self._set_animator_sprite_sheet)
        self.animator_panel.speed_set_requested.connect(self._set_animator_speed)
        self.animator_panel.flip_set_requested.connect(self._set_animator_flip)
        self.animator_panel.state_upsert_requested.connect(self._upsert_animator_state)
        self.animator_panel.state_remove_requested.connect(self._remove_animator_state)
        self.animator_panel.sprite_editor_requested.connect(self._on_animator_open_sprite_editor)
        self.agent_panel.refresh_requested.connect(self._refresh_agent_panel)
        self.agent_panel.session_create_requested.connect(self._create_agent_session)
        self.agent_panel.message_send_requested.connect(self._send_agent_message)
        self.agent_panel.action_approval_requested.connect(self._approve_agent_action)
        self.hierarchy_panel.entity_selected.connect(self._on_entity_selected)
        self.hierarchy_panel.entity_create_requested.connect(self._create_entity)
        self.hierarchy_panel.entity_delete_requested.connect(self._delete_entity)
        self.hierarchy_panel.entity_active_set_requested.connect(self._set_entity_active)
        self.inspector_panel.property_edit_requested.connect(self._update_component_property)
        self.project_panel.scene_requested.connect(self._on_scene_requested)
        # Project panel new signals
        self.project_panel.asset_drag_started.connect(self._on_asset_drag_started)
        self.project_panel.sprite_editor_requested.connect(self._on_project_sprite_editor)
        self.project_panel.scene_open_requested.connect(self._on_scene_requested)
        self.project_panel.scene_create_requested.connect(self._request_new_scene)
        self.project_panel.view_mode_changed.connect(lambda mode: self._save_ui_preferences({"project_view_mode": mode}))
        self.console_panel.command_submitted.connect(self._on_console_command_submitted)
        # Animator panel new signal
        self.animator_panel.slice_names_requested.connect(self._on_animator_slice_names_requested)
        # New Inspector signals (foldouts + add/remove component)
        self.inspector_panel.component_add_requested.connect(self._add_component_to_entity)
        self.inspector_panel.component_remove_requested.connect(self._remove_component_from_entity)
        # New Hierarchy signals (drag-reparent + context menu)
        self.hierarchy_panel.entity_create_child_requested.connect(self._create_child_entity)
        self.hierarchy_panel.entity_duplicate_requested.connect(self._duplicate_entity)
        self.hierarchy_panel.entity_reparent_requested.connect(self._reparent_entity)
        self.main_splitter.splitterMoved.connect(lambda _pos, _index: self._save_ui_preferences())
        self.top_splitter.splitterMoved.connect(lambda _pos, _index: self._save_ui_preferences())

    def _on_entity_selected(self, entity_name: str) -> None:
        entity = self.facade.select_entity(entity_name)
        self.inspector_panel.set_entity(entity, self.facade)
        self.scene_viewport.set_selected_entity(entity_name)
        self.game_viewport.set_selected_entity(entity_name)
        self.animator_panel.set_entity(
            entity,
            self.facade.get_animator_info(entity_name),
            self.facade.list_animator_states(entity_name),
        )
        self.console_panel.log(f"Selected entity: {entity_name}")
        self.add_component_action.setEnabled(True)

    def _load_initial_scene(self) -> None:
        result = self.facade.load_scene(self.initial_scene) if self.initial_scene else self.facade.load_default_scene()
        self._log_action_result(result)
        self._refresh_scene_panels()

    def _on_scene_requested(self, scene_ref: str) -> None:
        result = self.facade.load_scene(scene_ref)
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()
            self._focus_center_tab("Scene")

    def _request_new_scene(self) -> None:
        name, ok = QInputDialog.getText(self, "New Scene", "Scene name:")
        if ok and name.strip():
            self._create_scene(name.strip())

    def _create_scene(self, scene_name: str) -> None:
        result = self.facade.create_scene(scene_name)
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _request_create_empty_entity(self) -> None:
        name, ok = QInputDialog.getText(self, "Create Empty", "Entity name:")
        if ok and name.strip():
            self._create_entity(name.strip())

    def _create_entity(self, entity_name: str) -> None:
        result = self.facade.create_entity(entity_name)
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()
            entity = self.facade.select_entity(entity_name)
            self.inspector_panel.set_entity(entity, self.facade)
            self._refresh_project_panel()

    def _create_canvas(self) -> None:
        result = self.facade.create_canvas("Canvas")
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _create_ui_text(self) -> None:
        result = self.facade.create_ui_text(parent="Canvas")
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _create_ui_button(self) -> None:
        result = self.facade.create_ui_button(parent="Canvas")
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _delete_entity(self, entity_name: str) -> None:
        result = self.facade.delete_entity(entity_name)
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _update_component_property(
        self,
        entity_name: str,
        component_name: str,
        property_name: str,
        value_text: str,
        original_value: Any,
    ) -> None:
        try:
            value = parse_value(value_text, original_value)
        except ValueError as exc:
            self.console_panel.log(f"Invalid value for {component_name}.{property_name}: {exc}")
            self.inspector_panel.set_entity(self.facade.get_entity(entity_name), self.facade)
            return
        result = self.facade.update_component_property(entity_name, component_name, property_name, value)
        self._log_action_result(result)
        if result.get("success"):
            self.inspector_panel.set_entity(self.facade.get_entity(entity_name), self.facade)
            self._refresh_project_panel()

    def _save_scene(self) -> None:
        result = self.facade.save_scene()
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_project_panel()

    def _undo(self) -> None:
        result = self.facade.undo()
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _redo(self) -> None:
        result = self.facade.redo()
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _refresh_assets(self) -> None:
        result = self.facade.refresh_assets()
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_project_panel()

    def _set_scene_connection(self, key: str, target: str) -> None:
        result = self.facade.set_scene_connection(key, target)
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _ensure_animator(self, entity_name: str) -> None:
        result = self.facade.ensure_animator(entity_name)
        self._log_action_result(result)
        if result.get("success"):
            self._on_entity_selected(entity_name)
            self._refresh_project_panel()

    def _set_animator_sprite_sheet(self, entity_name: str, asset_path: str) -> None:
        result = self.facade.set_animator_sprite_sheet(entity_name, asset_path)
        self._log_action_result(result)
        if result.get("success"):
            self._on_entity_selected(entity_name)

    def _set_animator_speed(self, entity_name: str, speed: float) -> None:
        result = self.facade.set_animator_speed(entity_name, speed)
        self._log_action_result(result)
        if result.get("success"):
            self._on_entity_selected(entity_name)

    def _set_animator_flip(self, entity_name: str, flip_x: bool, flip_y: bool) -> None:
        result = self.facade.set_animator_flip(entity_name, flip_x, flip_y)
        self._log_action_result(result)
        if result.get("success"):
            self._on_entity_selected(entity_name)

    def _upsert_animator_state(
        self,
        entity_name: str,
        state_name: str,
        slice_names: list[str],
        fps: float,
        loop: bool,
        on_complete: object,
        set_default: bool,
    ) -> None:
        result = self.facade.upsert_animator_state(
            entity_name,
            state_name,
            slice_names,
            fps,
            loop,
            str(on_complete) if on_complete else None,
            set_default,
        )
        self._log_action_result(result)
        if result.get("success"):
            self._on_entity_selected(entity_name)

    def _remove_animator_state(self, entity_name: str, state_name: str) -> None:
        result = self.facade.remove_animator_state(entity_name, state_name)
        self._log_action_result(result)
        if result.get("success"):
            self._on_entity_selected(entity_name)

    def _on_animator_open_sprite_editor(self, entity_name: str) -> None:
        """Open sprite editor for the entity's animator sprite sheet."""
        info = self.facade.get_animator_info(entity_name)
        sheet_path = str(info.get("sprite_sheet") or "")
        if not sheet_path:
            self.console_panel.log("No sprite sheet set. Enter a path first.")
            return
        accepted, image_path, slices = open_sprite_editor(sheet_path, self)
        if accepted and slices:
            self.console_panel.log(f"Sprite editor: {len(slices)} slices saved for {image_path}")
            self._on_entity_selected(entity_name)

    def _refresh_agent_panel(self) -> None:
        self.agent_panel.set_agent_data(self.facade.list_agent_providers(), self.facade.list_agent_tools())

    def _sync_top_bar(
        self,
        project: dict[str, Any],
        active_scene: dict[str, Any],
        scenes: list[dict[str, Any]],
    ) -> None:
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem(str(project.get("name") or "No project"))
        self.project_combo.blockSignals(False)

        active_path = str(active_scene.get("path") or "")
        self._scene_selector_loading = True
        try:
            self.scene_combo.clear()
            for scene in scenes:
                label = str(scene.get("name") or scene.get("path") or "Scene")
                path = str(scene.get("path") or "")
                self.scene_combo.addItem(label, path)
                if path and path == active_path:
                    self.scene_combo.setCurrentIndex(self.scene_combo.count() - 1)
            if self.scene_combo.count() == 0:
                self.scene_combo.addItem("No scene", "")
                self.scene_combo.setEnabled(False)
            else:
                self.scene_combo.setEnabled(True)
        finally:
            self._scene_selector_loading = False

    def _create_agent_session(self) -> None:
        result = self.facade.create_agent_session()
        self._log_action_result(result)
        data = result.get("data")
        if result.get("success") and isinstance(data, dict):
            self._agent_session_id = str(data.get("session_id") or "")
            self.agent_panel.set_session(data)

    def _send_agent_message(self, message: str) -> None:
        if not self._agent_session_id:
            self._create_agent_session()
        if not self._agent_session_id:
            return
        result = self.facade.send_agent_message(self._agent_session_id, message)
        self._log_action_result(result)
        self.agent_panel.append_result(result)

    def _approve_agent_action(self, action_id: str, approved: bool) -> None:
        if not self._agent_session_id:
            return
        result = self.facade.approve_agent_action(self._agent_session_id, action_id, approved)
        self._log_action_result(result)
        self.agent_panel.append_result(result)

    def _refresh_project_panel(self) -> None:
        project = self.facade.get_project_manifest()
        active_scene = self.facade.get_active_scene_info()
        entities = self.facade.list_entities()
        scenes = self.facade.list_project_scenes()
        flow_connections = self.facade.get_scene_connections()
        self._sync_top_bar(project, active_scene, scenes)
        self.project_panel.set_project_data(
            project=project,
            active_scene=active_scene,
            scenes=scenes,
            assets=self.facade.list_project_assets(),
            scripts=self.facade.list_project_scripts(),
            prefabs=self.facade.list_project_prefabs(),
        )
        self.hierarchy_panel.set_entities(entities)
        self.scene_viewport.set_snapshot(scene_info=active_scene, entities=entities, project_root=self.facade.project_root)
        self.game_viewport.set_snapshot(scene_info=active_scene, entities=entities, project_root=self.facade.project_root)
        self.scene_viewport.set_theme_name(self._theme_name)
        self.game_viewport.set_theme_name(self._theme_name)
        self.flow_panel.set_flow_data(flow_connections, scenes)
        self.flow_tools_panel.set_flow_data(flow_connections, scenes)
        self.terminal_panel.set_project_root(self.facade.project_root)
        self._refresh_agent_panel()
        self._refresh_open_scene_tabs(active_scene)
        self._update_status_bar(project, active_scene)

    def _refresh_scene_panels(self) -> None:
        self._refresh_project_panel()
        self.inspector_panel.set_entity(None, self.facade)

    def _refresh_open_scene_tabs(self, active_scene: dict[str, Any]) -> None:
        while self.center_tabs.count() > self._base_center_tab_count:
            self.center_tabs.removeTab(self.center_tabs.count() - 1)

        open_scenes = self.facade.list_open_scenes()
        if not open_scenes and active_scene.get("has_scene"):
            open_scenes = [active_scene]

        for scene in open_scenes:
            name = str(scene.get("name") or scene.get("path") or "Scene")
            label = f"{name} *" if scene.get("dirty") else name
            widget = QtSceneViewportPanel("Scene")
            widget.set_theme_name(self._theme_name)
            widget.set_snapshot(scene_info=scene, entities=self.facade.list_entities(), project_root=self.facade.project_root)
            widget.entity_selected.connect(self._on_entity_selected)
            widget.entity_moved.connect(self._on_gizmo_entity_moved)
            widget.entity_rotated.connect(self._on_gizmo_entity_rotated)
            widget.entity_scaled.connect(self._on_gizmo_entity_scaled)
            widget.setProperty("scene_key", str(scene.get("key") or scene.get("path") or ""))
            self.center_tabs.addTab(widget, label)

    def _log_action_result(self, result: dict[str, object]) -> None:
        message = str(result.get("message") or "")
        if result.get("success"):
            data = result.get("data")
            if isinstance(data, dict) and data.get("path"):
                message = f"{message}: {data['path']}"
            self.console_panel.log(message or "Action completed.")
        else:
            self.console_panel.log(message or "Action failed.")

    def _update_status_bar(self, project: dict[str, Any], active_scene: dict[str, Any]) -> None:
        project_name = str(project.get("name") or "No project")
        scene_name = str(active_scene.get("name") or active_scene.get("path") or "No scene")
        entity_count = int(active_scene.get("entity_count") or 0)
        dirty_label = "Unsaved" if active_scene.get("dirty") else "Saved"
        self.statusBar().showMessage(
            f"{project_name} | {scene_name} | Entities: {entity_count} | {dirty_label} | View: {self._active_center_tab}"
        )

    def _focus_project_panel(self) -> None:
        self._focus_bottom_tab("Project")
        self._set_rail_active("Project")

    def _focus_center_tab(self, name: str) -> None:
        for index in range(self.center_tabs.count()):
            if self.center_tabs.tabText(index).replace(" *", "") == name:
                self.center_tabs.setCurrentIndex(index)
                return

    def _focus_bottom_tab(self, name: str) -> None:
        for index in range(self.bottom_tabs.count()):
            if self.bottom_tabs.tabText(index) == name:
                self.bottom_tabs.setCurrentIndex(index)
                return

    def _on_center_tab_changed(self, index: int) -> None:
        self._active_center_tab = self.center_tabs.tabText(index).replace(" *", "") if index >= 0 else "Scene"
        self._update_status_bar(self.facade.get_project_manifest(), self.facade.get_active_scene_info())
        self._save_ui_preferences({"center_tab": self._active_center_tab})

    def _on_bottom_tab_changed(self, index: int) -> None:
        if index >= 0:
            tab_name = self.bottom_tabs.tabText(index)
            self.console_panel.log(f"Bottom tab active: {tab_name}")
            self._save_ui_preferences({"bottom_tab": tab_name})

    def _on_scene_selector_activated(self, index: int) -> None:
        if self._scene_selector_loading:
            return
        scene_ref = str(self.scene_combo.itemData(index) or "")
        if scene_ref:
            self._on_scene_requested(scene_ref)

    def _toggle_theme(self) -> None:
        self._theme_name = "frost_light" if self._theme_name == "frost_dark" else "frost_dark"
        app = QApplication.instance()
        if app is not None:
            load_theme(cast(QApplication, app), self._theme_name)
        self.theme_action.setText("Light Theme" if self._theme_name == "frost_dark" else "Dark Theme")
        for index in range(self.center_tabs.count()):
            widget = self.center_tabs.widget(index)
            if isinstance(widget, QtSceneViewportPanel):
                widget.set_theme_name(self._theme_name)
        self._save_ui_preferences({"theme": self._theme_name})

    def _active_viewport(self) -> QtSceneViewportPanel:
        widget = self.center_tabs.currentWidget()
        if isinstance(widget, QtSceneViewportPanel):
            return widget
        return self.scene_viewport

    def _reset_active_viewport_camera(self) -> None:
        self._active_viewport().reset_camera()

    def _frame_selected_in_active_viewport(self) -> None:
        self._active_viewport().frame_selected()

    def _on_console_command_submitted(self, command: str) -> None:
        self.console_panel.log(f"Unsupported console command: {command}", "warning")

    def _select_tool(self, selected_action: QAction) -> None:
        for action in (
            self.select_tool_action,
            self.move_tool_action,
            self.rotate_tool_action,
            self.scale_tool_action,
        ):
            action.setChecked(action is selected_action)
        self.console_panel.log(f"Tool selected: {selected_action.text()}")
        mode_name = selected_action.text()
        self.scene_viewport.set_gizmo_mode(mode_name)
        self.game_viewport.set_gizmo_mode(mode_name)

    def _set_entity_active(self, entity_name: str, active: bool) -> None:
        result = self.facade.set_entity_active(entity_name, active)
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _add_component_to_entity(self, entity_name: str, component_name: str) -> None:
        component_name = component_name.strip()
        if not component_name:
            return
        result = self.facade.add_component(entity_name, component_name)
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _remove_component_from_entity(self, entity_name: str, component_name: str) -> None:
        result = self.facade.remove_component(entity_name, component_name)
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _create_child_entity(self, parent_name: str, child_name: str) -> None:
        result = self.facade.create_child_entity(parent_name, child_name)
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _duplicate_entity(self, entity_name: str) -> None:
        result = self.facade.duplicate_entity(entity_name)
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _on_gizmo_entity_moved(self, entity_name: str, component_name: str, property_name: str, new_x: float, new_y: float) -> None:
        """Commit gizmo drag: move entity to final position."""
        self.facade.update_component_property(entity_name, component_name, "x", float(new_x))
        self.facade.update_component_property(entity_name, component_name, "y", float(new_y))
        self._refresh_scene_panels()

    def _on_gizmo_entity_rotated(
        self,
        entity_name: str,
        component_name: str,
        property_name: str,
        new_rotation: float,
    ) -> None:
        result = self.facade.update_component_property(
            entity_name,
            component_name,
            property_name,
            float(new_rotation),
        )
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    def _on_gizmo_entity_scaled(
        self,
        entity_name: str,
        component_name: str,
        property_name: str,
        new_scale_x: float,
        new_scale_y: float,
    ) -> None:
        x_result = self.facade.update_component_property(entity_name, component_name, "scale_x", float(new_scale_x))
        y_result = self.facade.update_component_property(entity_name, component_name, "scale_y", float(new_scale_y))
        self._log_action_result(y_result if y_result.get("success") else x_result)
        if x_result.get("success") and y_result.get("success"):
            self._refresh_scene_panels()

    def _reparent_entity(self, entity_name: str, new_parent_name: str) -> None:
        parent = new_parent_name if new_parent_name else None
        result = self.facade.set_entity_parent(entity_name, parent)
        self._log_action_result(result)
        if result.get("success"):
            self._refresh_scene_panels()

    # -- new slots (project panel / animator / viewport drop) -----------------

    def _on_asset_drag_started(self, file_path: str, asset_type: str) -> None:
        """Track drag from project panel for viewport drop handling."""
        self._dragging_asset = file_path
        self._dragging_asset_type = asset_type
        self.console_panel.log(f"Dragging asset: {Path(file_path).name}")

    def _on_project_sprite_editor(self, asset_path: str) -> None:
        """Open sprite editor for project panel asset."""
        accepted, img_path, slices = open_sprite_editor(asset_path, self)
        if accepted:
            existing = self.facade.get_sprite_metadata(img_path)
            if not isinstance(existing, dict):
                existing = {}
            merged = dict(existing)
            merged["slices"] = slices
            result = self.facade.save_sprite_metadata(img_path, merged)
            self._log_action_result(result)
            self.console_panel.log(f"Sprite editor: {len(slices)} slices saved for {img_path}")

    def _on_animator_slice_names_requested(self, entity_name: str) -> None:
        """Provide slice names from the entity's animator sprite sheet metadata."""
        info = self.facade.get_animator_info(entity_name)
        sheet_path = str(info.get("sprite_sheet") or "")
        slice_names: list[str] = []
        if sheet_path:
            try:
                metadata = self.facade.get_sprite_metadata(sheet_path)
                slices = metadata.get("slices", []) if isinstance(metadata, dict) else []
                slice_names = [str(s.get("name", "")) for s in slices if s.get("name")]
            except Exception:
                pass
        self.animator_panel.set_available_slice_names(slice_names)

    def _on_viewport_asset_dropped(self, file_path: str, world_x: float, world_y: float) -> None:
        """Create entity when asset is dropped on viewport at world position."""
        asset_type = self._dragging_asset_type
        ext = Path(file_path).suffix.lower()
        if not asset_type:
            if ext == ".prefab":
                asset_type = "prefab"
            elif ext in (".png", ".jpg", ".jpeg", ".bmp"):
                asset_type = "image"

        filename = Path(file_path).stem
        entities = self.facade.list_entities()
        existing_names = {str(e.get("name", "")) for e in entities}
        new_name = filename
        counter = 1
        while new_name in existing_names:
            new_name = f"{filename}_{counter}"
            counter += 1

        if asset_type == "prefab":
            result = self.facade.instantiate_prefab(
                path=file_path, name=new_name, x=world_x, y=world_y,
            )
            self._log_action_result(result)
            if result.get("success"):
                self.console_panel.log(f"Prefab instantiated: {new_name}")
                self._refresh_scene_panels()
            return

        result = self.facade.create_entity(new_name)
        if result.get("success"):
            self.facade.update_component_property(new_name, "Transform", "x", world_x)
            self.facade.update_component_property(new_name, "Transform", "y", world_y)
            if ext in (".png", ".jpg", ".jpeg", ".bmp"):
                self.facade.add_component(new_name, "Sprite", {"texture_path": file_path})
            self.facade.add_component(new_name, "Collider", {"width": 32, "height": 32})
            self._refresh_scene_panels()
