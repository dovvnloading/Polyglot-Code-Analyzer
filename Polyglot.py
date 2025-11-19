# Copyright 2025 Matthew Robert Wesney
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Polyglot Code Analyzer
======================

A desktop application built with PySide6 that performs static analysis on software 
projects to generate code metrics (lines of code, comments, blanks, technical debt).

Key Features:
- Multi-threaded directory scanning to prevent UI freezing.
- Custom Neumorphic Design System (Soft UI) implemented via custom QWidgets and painting.
- Support for 50+ programming languages.
- Technical debt detection via tag scanning (TODO, FIXME, etc.).

Author: Matthew Wesney
License: Apache 2.0
"""


import sys
import os
import threading
import time
import re
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QTextEdit, QGraphicsDropShadowEffect,
    QProgressBar, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QObject, QSize, QPoint, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter, QPen, QBrush, QRadialGradient, QPainterPath

# ============================================================================
# THEME MANAGER
# ============================================================================

class ThemeManager:
    """
    Centralized configuration for the application's color palette.
    
    Handles the switching between Light and Dark modes by maintaining two
    distinct dictionaries of color values. This allows widgets to query
    current theme attributes dynamically.
    """
    
    # Neumorphism requires specific mid-tone backgrounds to allow
    # highlights and shadows to be visible simultaneously.
    LIGHT = {
        'BG_COLOR': "#E0E5EC",
        'SHADOW_LIGHT': QColor("#FFFFFF"),
        'SHADOW_DARK': QColor("#A3B1C6"),
        'TEXT_COLOR': "#4A4A4A",
        'ACCENT': "#6D5DFC",
        'SUCCESS': "#28a745",
        'WARNING': "#ffc107",
        'DANGER': "#dc3545"
    }
    
    DARK = {
        'BG_COLOR': "#2b2b2b",
        'SHADOW_LIGHT': QColor("#3d3d3d"),
        'SHADOW_DARK': QColor("#1e1e1e"),
        'TEXT_COLOR': "#E0E0E0",
        'ACCENT': "#8a7dff",
        'SUCCESS': "#4cd964",
        'WARNING': "#ffd60a",
        'DANGER': "#ff3b30"
    }
    
    def __init__(self):
        self.current_theme = self.LIGHT.copy()
        self.is_dark = False
    
    def set_dark_mode(self):
        """Switch internal state to Dark palette."""
        self.current_theme = self.DARK.copy()
        self.is_dark = True
    
    def set_light_mode(self):
        """Switch internal state to Light palette."""
        self.current_theme = self.LIGHT.copy()
        self.is_dark = False
    
    def get(self, key):
        """Retrieve a specific color value from the active theme."""
        return self.current_theme.get(key)

# Global instance for access across modules/classes
theme_manager = ThemeManager()

# ============================================================================
# SIGNALS/EVENTS
# ============================================================================

class AppSignals(QObject):
    """
    Defines the signal interface for thread communication.
    
    Since Qt GUI widgets can only be updated from the main thread,
    worker threads use these signals to pass data back to the UI.
    """
    # Emits percentage (int) and status message (str)
    progress_update = Signal(int, str) 
    # Emits the final result dictionary
    analysis_done = Signal(dict)
    # Emits error messages
    analysis_error = Signal(str)

app_signals = AppSignals()

# ============================================================================
# ADVANCED ANALYSIS WORKER
# ============================================================================

class CodeSyntax:
    """
    Static helper class to map file extensions to comment syntax.
    Used to identify if a line constitutes a comment in a specific language.
    """
    COMMENTS = {
        '//': ['.c', '.cpp', '.h', '.hpp', '.cc', '.java', '.js', '.jsx', '.ts', '.tsx', '.cs', '.go', '.rs', '.swift', '.kt', '.dart', '.scala', '.groovy', '.php'],
        '#':  ['.py', '.pyw', '.rb', '.sh', '.bash', '.yaml', '.yml', '.dockerfile', '.pl', '.r', '.ps1'],
        '--': ['.sql', '.lua', '.hs'],
        '%':  ['.m', '.tex'],
        '<!--': ['.html', '.xml', '.htm']
    }

    @staticmethod
    def get_comment_marker(ext):
        """Returns the single-line comment token for the given extension."""
        for marker, extensions in CodeSyntax.COMMENTS.items():
            if ext in extensions:
                return marker
        return None

def count_lines_complex(content: str, ext: str) -> dict:
    """
    Parses file content to categorize lines.
    
    Args:
        content (str): The full text content of the file.
        ext (str): The file extension (used for comment syntax detection).
        
    Returns:
        dict: A breakdown of 'code', 'comment', 'blank', and 'todo' counts.
    """
    stats = {'code': 0, 'comment': 0, 'blank': 0, 'todo': 0}
    
    if not content:
        return stats

    marker = CodeSyntax.get_comment_marker(ext)
    lines = content.splitlines()
    
    # Regex to identify common Technical Debt tags
    # \b ensures we match whole words (e.g., "TODO" not "mastodon")
    todo_pattern = re.compile(r'\b(TODO|FIXME|HACK|BUG|XXX)\b', re.IGNORECASE)
    
    for line in lines:
        stripped = line.strip()
        
        # Scan for technical debt tags regardless of line type
        if todo_pattern.search(line):
            stats['todo'] += 1

        # Categorize the line type
        if not stripped:
            stats['blank'] += 1
        elif marker and stripped.startswith(marker):
            stats['comment'] += 1
        else:
            stats['code'] += 1
            
    return stats

def analyze_project(path):
    """
    The main worker function designed to run in a separate thread.
    
    Implementation Strategy:
    1. Define strict whitelist of supported extensions to avoid parsing binary/media files.
    2. Pass 1: Walk the directory tree purely to count files. This is required to
       accurately scale the progress bar.
    3. Pass 2: Open and parse files. Emit progress signals periodically.
    """
    try:
        # Comprehensive list of text-based source code extensions
        code_extensions = {
            '.py', '.pyw', '.c', '.cpp', '.h', '.hpp', '.cc', '.java', '.js', '.jsx', 
            '.ts', '.tsx', '.html', '.htm', '.css', '.scss', '.less', '.json', '.xml', 
            '.yaml', '.yml', '.md', '.txt', '.php', '.rb', '.go', '.rs', '.swift', 
            '.kt', '.kts', '.cs', '.sh', '.bash', '.bat', '.ps1', '.lua', '.pl', 
            '.sql', '.r', '.m', '.mm', '.dart', '.vb', '.vbs', '.scala', '.groovy',
            '.asm', '.s', '.properties', '.ini', '.toml', '.dockerfile'
        }
        
        # Directories to completely exclude from traversal
        ignore_dirs = {
            '.git', '__pycache__', '.vscode', 'node_modules', 'venv', '.idea', 
            '.pytest_cache', 'build', 'dist', '.vs', '.egg-info', 'coverage', 
            'bin', 'obj', 'target', '.gradle', '.mytpy', 'vendor'
        }

        # --- PASS 1: Structure Scan ---
        app_signals.progress_update.emit(0, "Scanning directory structure...")
        file_list = []
        for root, dirs, files in os.walk(path):
            # Modify dirs in-place to prune ignored directories from traversal
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file_name in files:
                _, ext = os.path.splitext(file_name)
                if ext.lower() in code_extensions or file_name.lower() == 'dockerfile':
                    file_list.append(os.path.join(root, file_name))
        
        total_files = len(file_list)
        if total_files == 0:
            app_signals.analysis_done.emit({'summary': None})
            return

        # --- PASS 2: Content Analysis ---
        summary = {
            'total_files': 0, 
            'total_lines': 0,
            'lines_code': 0,
            'lines_comment': 0,
            'lines_blank': 0,
            'total_todos': 0,
            'file_breakdown': {}
        }
        
        processed = 0
        
        for file_path in file_list:
            processed += 1
            # Rate-limit UI updates to prevent event loop flooding
            if processed % 5 == 0 or processed == total_files:
                pct = int((processed / total_files) * 100)
                app_signals.progress_update.emit(pct, f"Analyzing: {os.path.basename(file_path)}")

            try:
                _, ext = os.path.splitext(file_path)
                ext = ext.lower() if ext else 'No Ext'
                
                # 'errors=ignore' is crucial to prevent crashes on files with mixed encoding
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Basic binary check (Null bytes usually indicate binary files masquerading as text)
                    if not content or '\0' in content:
                        continue

                    stats = count_lines_complex(content, ext)
                    
                    # Update Global Totals
                    total_l = stats['code'] + stats['comment'] + stats['blank']
                    summary['total_files'] += 1
                    summary['total_lines'] += total_l
                    summary['lines_code'] += stats['code']
                    summary['lines_comment'] += stats['comment']
                    summary['lines_blank'] += stats['blank']
                    summary['total_todos'] += stats['todo']
                    
                    # Update Per-Extension Statistics
                    if ext not in summary['file_breakdown']:
                        summary['file_breakdown'][ext] = {
                            'count': 0, 'lines': 0, 'code': 0, 'comment': 0, 'blank': 0, 'todo': 0
                        }
                    
                    s_ext = summary['file_breakdown'][ext]
                    s_ext['count'] += 1
                    s_ext['lines'] += total_l
                    s_ext['code'] += stats['code']
                    s_ext['comment'] += stats['comment']
                    s_ext['blank'] += stats['blank']
                    s_ext['todo'] += stats['todo']

            except Exception:
                # Fail silently on individual file permission errors to keep the batch running
                continue
                    
        app_signals.analysis_done.emit({'summary': summary})
    except Exception as e:
        app_signals.analysis_error.emit(str(e))

# ============================================================================
# NEUMORPHIC WIDGETS
# ============================================================================

class NeumorphicButton(QWidget):
    """
    A custom QWidget wrapper that simulates a 3D Neumorphic Button.
    
    Qt Limitation Workaround:
    A single QWidget can generally only have one QGraphicsEffect applied.
    Neumorphism requires TWO shadows (a light source top-left, and a shadow bottom-right).
    
    Solution:
    This class acts as a container (Self) holding a child QPushButton.
    - The Container renders the Light Highlight.
    - The Child Button renders the Dark Shadow.
    The result is a composite visual that looks like a single extruded element.
    """
    clicked = Signal()
    
    def __init__(self, text="", parent=None, width=160, height=50):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4) # Padding allows shadow bleed
        
        self.inner_btn = QPushButton(text)
        self.inner_btn.setCursor(Qt.PointingHandCursor)
        # Forward the signal
        self.inner_btn.clicked.connect(self.clicked.emit)
        
        # Create the two distinct shadow effects
        self.dark_shadow = QGraphicsDropShadowEffect()
        self.dark_shadow.setBlurRadius(12)
        self.dark_shadow.setOffset(4, 4)
        
        self.light_shadow = QGraphicsDropShadowEffect()
        self.light_shadow.setBlurRadius(12)
        self.light_shadow.setOffset(-4, -4)
        
        # Assign effects to separate layers
        self.inner_btn.setGraphicsEffect(self.dark_shadow)
        self.setGraphicsEffect(self.light_shadow)
        
        self.layout.addWidget(self.inner_btn)
        self.update_theme()

    def setEnabled(self, enabled):
        self.inner_btn.setEnabled(enabled)
        super().setEnabled(enabled)

    def update_theme(self):
        """Refreshes colors/styles based on current ThemeManager state."""
        bg = theme_manager.get('BG_COLOR')
        text = theme_manager.get('TEXT_COLOR')
        self.dark_shadow.setColor(theme_manager.get('SHADOW_DARK'))
        self.light_shadow.setColor(theme_manager.get('SHADOW_LIGHT'))
        
        # Container styling
        self.setStyleSheet(f"NeumorphicButton {{ background-color: {bg}; border-radius: {self.height()//2}px; }}")
        
        # Inner button styling (margin mimics the 'press' effect slightly)
        self.inner_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg}; color: {text}; border: none;
                border-radius: {(self.height()//2)-4}px; font-weight: bold; font-size: 12px;
            }}
            QPushButton:pressed {{ background-color: {bg}; margin: 2px; }}
            QPushButton:disabled {{ color: #999999; }}
        """)

class NeumorphicIconButton(QWidget):
    """
    A specialized circular toggle button that draws its own icon (Sun/Moon)
    using QPainter to ensure crisp rendering at any scale/DPI.
    """
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)
        
        # Layout setup to hold the inner button
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(0)
        
        self.inner_btn = QPushButton()
        self.inner_btn.setCursor(Qt.PointingHandCursor)
        self.inner_btn.clicked.connect(self.clicked.emit)
        self.inner_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Apply Neumorphic shadows
        self.dark_shadow = QGraphicsDropShadowEffect()
        self.dark_shadow.setBlurRadius(10)
        self.dark_shadow.setOffset(3, 3)
        
        self.light_shadow = QGraphicsDropShadowEffect()
        self.light_shadow.setBlurRadius(10)
        self.light_shadow.setOffset(-3, -3)
        
        self.inner_btn.setGraphicsEffect(self.dark_shadow)
        self.setGraphicsEffect(self.light_shadow)
        self.layout.addWidget(self.inner_btn)
        
        # Override paint event to draw custom vector graphics
        self.inner_btn.paintEvent = self._paint_inner_btn
        self.update_theme()

    def _paint_inner_btn(self, event):
        """Custom painting for the icon (Sun or Moon) depending on theme state."""
        painter = QPainter(self.inner_btn)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.inner_btn.rect()
        # Adjust rect to ensure anti-aliasing doesn't get clipped by widget bounds
        draw_rect = rect.adjusted(2, 2, -2, -2)
        
        # Draw Background (Circle)
        bg = QColor(theme_manager.get('BG_COLOR'))
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(draw_rect)
        
        # Draw Icon (Accent Color)
        accent = QColor(theme_manager.get('ACCENT'))
        painter.setBrush(QBrush(accent))
        
        center = draw_rect.center()
        
        if theme_manager.is_dark:
            # Draw Moon: Create a circle, then subtract another circle to make a crescent
            path = QPainterPath()
            path.addEllipse(center, 8, 8)
            cut = QPainterPath()
            cut.addEllipse(QPoint(center.x() + 4, center.y() - 4), 8, 8)
            path = path.subtracted(cut)
            painter.drawPath(path)
        else:
            # Draw Sun: Circle + iterating lines for rays
            painter.drawEllipse(center, 5, 5)
            painter.setPen(QPen(accent, 2, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(Qt.NoBrush)
            radius_inner = 8
            radius_outer = 11
            
            for i in range(8):
                painter.save()
                painter.translate(center)
                painter.rotate(i * 45)
                painter.drawLine(0, -radius_inner, 0, -radius_outer)
                painter.restore()

    def update_theme(self):
        self.dark_shadow.setColor(theme_manager.get('SHADOW_DARK'))
        self.light_shadow.setColor(theme_manager.get('SHADOW_LIGHT'))
        self.setStyleSheet(f"background-color: {theme_manager.get('BG_COLOR')}; border-radius: 24px;")
        # Inner button is transparent; paintEvent handles the fill
        self.inner_btn.setStyleSheet("border: none; background: transparent;")
        self.inner_btn.update()

class NeumorphicProgressBar(QWidget):
    """
    A custom progress bar that renders an 'inset' (sunken) track using
    manual QPainter paths, and a 'raised' progress fill.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self.value = 0
        self.status_text = ""
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {theme_manager.get('BG_COLOR')};
                border-radius: 12px;
            }}
        """)
        
    def set_value(self, val, text=""):
        self.value = val
        self.status_text = text
        self.update() # Trigger repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        
        shadow_dark = theme_manager.get('SHADOW_DARK')
        shadow_light = theme_manager.get('SHADOW_LIGHT')
        accent = QColor(theme_manager.get('ACCENT'))
        
        # 1. Draw Trough (Simulating Inset Depth)
        # We draw borders manually: 
        # Top/Left = Shadow (Dark)
        # Bottom/Right = Highlight (Light)
        pen_width = 2
        
        # Top/Left inner shadow path
        path_tl = QPainterPath()
        path_tl.moveTo(rect.bottomLeft())
        path_tl.lineTo(rect.topLeft())
        path_tl.lineTo(rect.topRight())
        painter.setPen(QPen(shadow_dark, pen_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path_tl)
        
        # Bottom/Right inner highlight path
        path_br = QPainterPath()
        path_br.moveTo(rect.topRight())
        path_br.lineTo(rect.bottomRight())
        path_br.lineTo(rect.bottomLeft())
        painter.setPen(QPen(shadow_light, pen_width))
        painter.drawPath(path_br)
        
        # 2. Draw Progress Fill
        if self.value > 0:
            prog_width = (rect.width() - 4) * (self.value / 100.0)
            prog_rect = QRectF(2, 2, prog_width, rect.height() - 4)
            if prog_width > 10:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(accent))
                painter.drawRoundedRect(prog_rect, 10, 10)
                
        # 3. Draw Status Text
        if self.status_text:
            painter.setPen(QColor(theme_manager.get('TEXT_COLOR')))
            painter.setFont(QFont("Segoe UI", 9))
            label = f"{self.value}% - {self.status_text}" if self.value < 100 else "Done"
            painter.drawText(rect, Qt.AlignCenter, label)

class NeumorphicTextEdit(QTextEdit):
    """
    A read-only text display formatted to look 'sunken' into the interface.
    Uses CSS border styling to mimic lighting effects (Dark Top/Left, Light Bottom/Right).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Select a project to analyze...")
        
        # Scrollbar Policy Fixes:
        # Disable horizontal scroll to prevent layout drift on HTML tables.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        
        self.update_theme()
        
    def update_theme(self):
        bg = theme_manager.get('BG_COLOR')
        text = theme_manager.get('TEXT_COLOR')
        s_dark = theme_manager.get('SHADOW_DARK').name()
        s_light = theme_manager.get('SHADOW_LIGHT').name()
        
        # CSS Hack for Inset Look:
        # Explicitly set border colors to create 3D depth perception.
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {bg};
                color: {text};
                border-top: 2px solid {s_dark};
                border-left: 2px solid {s_dark};
                border-bottom: 2px solid {s_light};
                border-right: 2px solid {s_light};
                border-radius: 15px;
                padding: 20px;
                font-family: "Segoe UI", sans-serif;
                font-size: 13px;
            }}
            QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background-color: {s_dark}; min-height: 20px; border-radius: 5px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)

# ============================================================================
# MAIN WINDOW
# ============================================================================

class CustomTitleBar(QWidget):
    """
    A custom implementation of a window title bar to replace the OS native bar.
    Allows for complete thematic consistency (Neumorphic design) and standard 
    window operations (Drag, Minimize, Maximize, Close).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(40)
        self.drag_position = None
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 10, 0)
        layout.setSpacing(10)
        
        # App Icon
        self.icon_label = QLabel("</>")
        self.icon_label.setFont(QFont("Consolas", 12, QFont.Bold))
        self.icon_label.setFixedSize(30, 30)
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        # App Title
        self.title_label = QLabel("Polyglot Code Analyzer")
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addStretch()
        
        # Standard Window Controls
        self.minimize_btn = self._create_control_btn("_")
        self.minimize_btn.clicked.connect(self.parent_window.showMinimized)
        self.maximize_btn = self._create_control_btn("□")
        self.maximize_btn.clicked.connect(self._toggle_maximize)
        self.close_btn = self._create_control_btn("✕")
        self.close_btn.clicked.connect(self.parent_window.close)
        
        layout.addWidget(self.minimize_btn)
        layout.addWidget(self.maximize_btn)
        layout.addWidget(self.close_btn)
        self.update_theme()
    
    def _create_control_btn(self, text):
        btn = QPushButton(text)
        btn.setFixedSize(30, 30)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(QFont("Arial", 10))
        return btn
        
    def _toggle_maximize(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
        else:
            self.parent_window.showMaximized()
    
    # -- Drag to Move Implementation --
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position is not None and not self.parent_window.isMaximized():
            self.parent_window.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
            
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton: self._toggle_maximize()
    
    def update_theme(self):
        bg = theme_manager.get('BG_COLOR')
        text = theme_manager.get('TEXT_COLOR')
        self.setStyleSheet(f"background-color: {bg};")
        self.icon_label.setStyleSheet(f"color: {theme_manager.get('ACCENT')}; background-color: transparent;")
        self.title_label.setStyleSheet(f"color: {text}; background-color: transparent;")
        
        btn_style = f"QPushButton {{ background-color: transparent; color: {text}; border: none; border-radius: 5px; }} QPushButton:hover {{ background-color: rgba(128, 128, 128, 0.2); }}"
        close_style = f"QPushButton {{ background-color: transparent; color: {text}; border: none; border-radius: 5px; }} QPushButton:hover {{ background-color: #ff5f57; color: white; }}"
        
        self.minimize_btn.setStyleSheet(btn_style)
        self.maximize_btn.setStyleSheet(btn_style)
        self.close_btn.setStyleSheet(close_style)

class MainWindow(QMainWindow):
    """
    The application root window.
    Constructs the UI layout, handles high-level event orchestration (file selection, theme toggling),
    and processes signal data from the analysis thread.
    """
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("Polyglot Code Analyzer")
        self.resize(1000, 800)
        self.current_project_path = None
        
        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
    
    def _setup_ui(self):
        """Builds the widget hierarchy."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.title_bar = CustomTitleBar(self)
        main_layout.addWidget(self.title_bar)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(40, 30, 40, 40)
        content_layout.setSpacing(20)
        
        # Header Row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)
        header_layout.setAlignment(Qt.AlignVCenter)
        
        self.select_project_button = NeumorphicButton("SELECT PROJECT", width=180)
        self.select_project_button.clicked.connect(self._select_project)
        
        self.project_path_label = QLabel("No project selected")
        self.project_path_label.setWordWrap(True)
        
        # Theme Toggle
        self.theme_toggle = NeumorphicIconButton()
        self.theme_toggle.clicked.connect(self._toggle_theme)
        
        header_layout.addWidget(self.select_project_button)
        header_layout.addWidget(self.project_path_label, 1)
        header_layout.addWidget(self.theme_toggle)
        
        # Progress Indicator
        self.progress_bar = NeumorphicProgressBar()
        
        # Main Output Display
        self.analysis_display = NeumorphicTextEdit()
        
        content_layout.addLayout(header_layout)
        content_layout.addWidget(self.progress_bar)
        content_layout.addWidget(self.analysis_display, 1)
        
        main_layout.addWidget(content_widget, 1)
    
    def _apply_theme(self):
        """Propagates theme changes to all child widgets."""
        bg = theme_manager.get('BG_COLOR')
        text = theme_manager.get('TEXT_COLOR')
        
        self.setStyleSheet(f"QMainWindow {{ background-color: {bg}; }} QWidget {{ background-color: {bg}; color: {text}; }}")
        self.project_path_label.setStyleSheet(f"color: {text}; background-color: transparent; font-style: italic; font-size: 12px; padding-left: 10px;")
        
        self.title_bar.update_theme()
        self.select_project_button.update_theme()
        self.theme_toggle.update_theme()
        self.analysis_display.update_theme()
        self.progress_bar.update()

    def _connect_signals(self):
        """Connects worker signals to UI slots."""
        app_signals.analysis_done.connect(self._on_analysis_complete)
        app_signals.analysis_error.connect(self._on_analysis_error)
        app_signals.progress_update.connect(self._on_progress)
    
    def _select_project(self):
        """Opens directory picker and starts the analysis thread."""
        path = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if path:
            self.current_project_path = path
            self.project_path_label.setText(f"Target: {path}")
            self.analysis_display.setText("")
            self.select_project_button.setEnabled(False)
            self.progress_bar.set_value(0, "Initializing...")
            
            # Launch analysis in daemon thread so it closes if app closes
            thread = threading.Thread(target=analyze_project, args=(path,), daemon=True)
            thread.start()
    
    def _toggle_theme(self):
        if theme_manager.is_dark: theme_manager.set_light_mode()
        else: theme_manager.set_dark_mode()
        self._apply_theme()
    
    def _on_progress(self, value, text):
        self.progress_bar.set_value(value, text)

    def _on_analysis_complete(self, data):
        """Generates and displays the HTML report from the raw summary data."""
        self.progress_bar.set_value(100, "Complete")
        self.select_project_button.setEnabled(True)
        
        if not data['summary']:
            self.analysis_display.setHtml("<p>No code files found.</p>")
            return

        summary = data['summary']
        accent = theme_manager.get('ACCENT')
        text_col = theme_manager.get('TEXT_COLOR')
        success = theme_manager.get('SUCCESS')
        danger = theme_manager.get('DANGER')
        
        # Construct HTML Report
        html = []
        
        # 1. High-level Cards
        html.append(f"<h1 style='color:{accent};'>Analysis Report</h1>")
        html.append(f"<div style='margin-bottom:20px;'>")
        
        # Styled using table cells as pseudo-cards
        box_style = f"border: 2px solid {theme_manager.get('SHADOW_DARK').name()}; padding: 10px; border-radius: 8px; margin-right:10px;"
        
        html.append(f"<table width='100%'><tr>")
        html.append(f"<td width='33%'><div style='{box_style}'>Files<br><b style='font-size:18px; color:{accent}'>{summary['total_files']}</b></div></td>")
        html.append(f"<td width='33%'><div style='{box_style}'>Total Lines<br><b style='font-size:18px; color:{accent}'>{summary['total_lines']:,}</b></div></td>")
        html.append(f"<td width='33%'><div style='{box_style}'>Debt Tags (TODO)<br><b style='font-size:18px; color:{danger}'>{summary['total_todos']}</b></div></td>")
        html.append(f"</tr></table></div>")
        
        # 2. Code Composition Bar
        total = summary['total_lines']
        if total > 0:
            p_code = (summary['lines_code'] / total) * 100
            p_comm = (summary['lines_comment'] / total) * 100
            p_blnk = (summary['lines_blank'] / total) * 100
            
            html.append(f"<h3 style='color:{text_col}'>Composition</h3>")
            # Qt HTML supports simplified tables better than Flexbox divs
            html.append(f"<table width='100%' height='12' cellspacing='0' cellpadding='0'><tr>")
            if p_code > 0: html.append(f"<td width='{p_code}%' bgcolor='{success}'></td>")
            if p_comm > 0: html.append(f"<td width='{p_comm}%' bgcolor='{accent}'></td>")
            if p_blnk > 0: html.append(f"<td width='{p_blnk}%' bgcolor='{theme_manager.get('SHADOW_DARK').name()}'></td>")
            html.append(f"</tr></table>")
            
            html.append(f"<p style='font-size:11px; color:{text_col}'>")
            html.append(f"<span style='color:{success}'>■</span> Code: {summary['lines_code']:,} ({p_code:.1f}%) &nbsp;&nbsp;")
            html.append(f"<span style='color:{accent}'>■</span> Comments: {summary['lines_comment']:,} ({p_comm:.1f}%) &nbsp;&nbsp;")
            html.append(f"<span style='color:{text_col}'>■</span> Blank: {summary['lines_blank']:,} ({p_blnk:.1f}%)")
            html.append(f"</p>")

        # 3. Detailed Breakdown Table
        html.append(f"<h3 style='color:{text_col}; margin-top:20px;'>Language Breakdown</h3>")
        sorted_items = sorted(summary['file_breakdown'].items(), key=lambda x: x[1]['lines'], reverse=True)
        
        html.append(f"<table width='100%' cellspacing='0' cellpadding='6'>")
        html.append(f"<tr style='background-color:rgba(0,0,0,0.05); color:{text_col};'><th align='left'>Ext</th><th align='right'>Files</th><th align='right'>Total Lines</th><th align='right'>Code Only</th><th align='right'>Comments</th></tr>")
        
        for ext, info in sorted_items:
            html.append(f"<tr>")
            html.append(f"<td><b style='color:{accent}'>{ext}</b></td>")
            html.append(f"<td align='right'>{info['count']}</td>")
            html.append(f"<td align='right'>{info['lines']:,}</td>")
            html.append(f"<td align='right' style='color:{success}'>{info['code']:,}</td>")
            html.append(f"<td align='right' style='color:{text_col}'>{info['comment']:,}</td>")
            html.append(f"</tr>")
            
        html.append("</table>")
        self.analysis_display.setHtml("".join(html))
    
    def _on_analysis_error(self, error):
        self.progress_bar.set_value(0, "Error")
        self.analysis_display.setHtml(f"<h3 style='color:red;'>Analysis Failed</h3><p>{error}</p>")
        self.select_project_button.setEnabled(True)

# ============================================================================
# APP ENTRY
# ============================================================================

def main():
    app = QApplication(sys.argv)
    # Fusion style provides a clean, platform-agnostic base
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
