# -*- coding: utf-8 -*-
"""High-DPI immune horizontal segmented sub-tab switcher for QGIS 2.5D Styling."""
from __future__ import annotations

from typing import List, Optional

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

_QWidgetBase = QWidget if QWidget is not None else object


class StylingSubTabs(_QWidgetBase):
    """Segmented horizontal tab switcher using native QPushButton widgets.
    Completely avoids Windows Vista/11 QTabBar DrawThemeTextEx text clipping.
    """

    currentChanged = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._buttons: List[QPushButton] = []
        self._widgets: List[QWidget] = []

        main_lyt = QVBoxLayout(self)
        main_lyt.setContentsMargins(0, 0, 0, 0)
        main_lyt.setSpacing(0)

        # Tab Bar Header Frame
        self._header_frame = QFrame()
        self._header_frame.setObjectName("subTabHeader")
        self._header_lyt = QHBoxLayout(self._header_frame)
        self._header_lyt.setContentsMargins(2, 0, 2, 0)
        self._header_lyt.setSpacing(4)
        self._header_lyt.addStretch()

        main_lyt.addWidget(self._header_frame)

        # Content Stack
        self._stack = QStackedWidget()
        self._stack.setObjectName("subTabStack")
        main_lyt.addWidget(self._stack)

    def addTab(self, widget: QWidget, text: str) -> int:
        idx = len(self._buttons)
        clean_text = text.strip()
        btn = QPushButton(clean_text)
        btn.setCheckable(True)
        btn.setObjectName("subTabBtn")
        btn.setCursor(Qt.PointingHandCursor if hasattr(Qt, "PointingHandCursor") else Qt.ArrowCursor)
        btn.clicked.connect(lambda checked, i=idx: self.setCurrentIndex(i))

        self._header_lyt.insertWidget(idx, btn)
        self._buttons.append(btn)

        self._stack.addWidget(widget)
        self._widgets.append(widget)

        if idx == 0:
            btn.setChecked(True)
            self._stack.setCurrentIndex(0)

        return idx

    def setTabToolTip(self, index: int, tooltip: str) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setToolTip(tooltip)

    def setCurrentIndex(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            for i, b in enumerate(self._buttons):
                b.setChecked(i == index)
            self._stack.setCurrentIndex(index)
            self.currentChanged.emit(index)

    def currentIndex(self) -> int:
        return self._stack.currentIndex()

    def count(self) -> int:
        return len(self._buttons)

    def widget(self, index: int) -> Optional[QWidget]:
        if 0 <= index < len(self._widgets):
            return self._widgets[index]
        return None
