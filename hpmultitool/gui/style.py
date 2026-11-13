"""Colour tokens and Qt style sheets for the dark and light theme."""

from __future__ import annotations

THEMES = {
    "dark": {
        "bg": "#0f1419", "surface": "#161c24", "surface2": "#1d252f", "input": "#111820",
        "border": "#273241", "text": "#e6edf3", "muted": "#8b98a5",
        "accent": "#2dd4bf", "accent_hover": "#5eead4", "accent_text": "#04201c",
        "danger": "#f87171", "warn": "#fbbf24", "ok": "#34d399",
        "plot_bg": "#111820", "grid": "#273241",
    },
    "light": {
        "bg": "#eef1f5", "surface": "#ffffff", "surface2": "#f5f7fa", "input": "#ffffff",
        "border": "#d5dce5", "text": "#17212b", "muted": "#5b6b7b",
        "accent": "#0d9488", "accent_hover": "#0f766e", "accent_text": "#ffffff",
        "danger": "#dc2626", "warn": "#b45309", "ok": "#059669",
        "plot_bg": "#ffffff", "grid": "#d5dce5",
    },
}

DEVICE_COLORS = ["#2dd4bf", "#f59e0b", "#a78bfa", "#f472b6", "#60a5fa", "#a3e635"]
MONO_FONTS = "'JetBrains Mono', 'DejaVu Sans Mono', 'Cascadia Mono', Consolas, monospace"


def stylesheet(name: str, checkmark: str = "") -> str:
    c = THEMES[name]
    return f"""
    QWidget {{ background: {c['bg']}; color: {c['text']}; font-size: 10pt; }}
    QToolTip {{ background: {c['surface2']}; color: {c['text']}; border: 1px solid {c['border']};
               padding: 6px; border-radius: 6px; }}
    #Header {{ background: {c['surface']}; border-bottom: 1px solid {c['border']}; }}
    #AppTitle {{ font-size: 15pt; font-weight: 700; background: transparent; }}
    #AppSubtitle {{ color: {c['muted']}; background: transparent; }}
    #Badge {{ background: {c['warn']}; color: #1b1400; border-radius: 9px; padding: 2px 10px;
              font-weight: 600; }}
    #Card {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}
    #Card QWidget {{ background: transparent; }}
    #CardTitle {{ font-size: 11pt; font-weight: 700; }}
    #Muted, QLabel[muted="true"] {{ color: {c['muted']}; }}
    #Hint {{ color: {c['muted']}; background: {c['surface2']}; border-radius: 8px; padding: 8px; }}
    #Callout {{ background: {c['surface2']}; border-left: 3px solid {c['accent']};
                border-radius: 6px; padding: 8px; }}
    #DeviceRow {{ background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 10px; }}
    #DeviceRow[selected="true"] {{ border: 1px solid {c['accent']}; }}
    #DeviceName {{ font-size: 13pt; font-weight: 700; }}
    #Readout {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}
    #Readout QWidget {{ background: transparent; }}
    #ReadoutValue {{ font-family: {MONO_FONTS}; font-size: 26pt; font-weight: 600; }}
    #ReadoutName {{ font-size: 12pt; font-weight: 700; }}
    #ReadoutObject {{ font-size: 12pt; font-weight: 700; color: {c['text']};
                      background: {c['surface2']}; border-radius: 6px; padding: 1px 8px; }}
    #LoopBanner {{ background: {c['surface']}; border: 2px solid {c['accent']}; border-radius: 12px; }}
    #LoopBanner QWidget {{ background: transparent; }}
    #LivePanel {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}
    #LivePanel QWidget {{ background: transparent; }}
    #LiveDisplay {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 10px; }}
    #LiveValue {{ font-family: {MONO_FONTS}; font-size: 40pt; font-weight: 600; color: {c['text']}; }}
    #LiveFlags {{ color: {c['accent']}; font-size: 9pt; font-weight: 700; letter-spacing: 1px; }}
    QPushButton#Key {{ padding: 5px 8px; min-width: 44px; border-radius: 7px; font-weight: 600; }}
    QPushButton#Key:checked {{ background: {c['accent']}; color: {c['accent_text']};
                               border-color: {c['accent']}; }}
    QToolButton#Segment {{ padding: 6px 18px; border: 1px solid {c['border']}; border-radius: 8px;
                           font-weight: 700; color: {c['muted']}; }}
    QToolButton#Segment:checked {{ background: {c['accent']}; color: {c['accent_text']};
                                   border-color: {c['accent']}; }}
    #RecordLabel {{ color: {c['danger']}; font-weight: 700; }}
    #BannerTitle {{ font-size: 13pt; font-weight: 700; color: {c['accent']}; }}
    QListWidget {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 8px;
                   padding: 4px; }}
    QListWidget::item {{ padding: 4px 6px; border-radius: 5px; }}
    QListWidget::item:selected {{ background: {c['accent']}; color: {c['accent_text']}; }}
    QTextBrowser {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px;
                    padding: 8px; }}
    #SectionLabel {{ color: {c['muted']}; font-size: 9pt; font-weight: 700;
                     text-transform: uppercase; letter-spacing: 1px; }}

    QPushButton {{ background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 8px;
                   padding: 7px 14px; }}
    QPushButton:hover {{ border-color: {c['accent']}; }}
    QPushButton:pressed {{ background: {c['border']}; }}
    QPushButton:disabled {{ color: {c['muted']}; border-color: {c['border']}; }}
    QPushButton#Primary {{ background: {c['accent']}; color: {c['accent_text']}; border: none;
                           font-weight: 700; }}
    QPushButton#Primary:hover {{ background: {c['accent_hover']}; }}
    QPushButton#Primary:disabled {{ background: {c['border']}; color: {c['muted']}; }}
    QPushButton#Danger {{ background: transparent; color: {c['danger']}; border: 1px solid {c['danger']};
                          font-weight: 700; }}
    QPushButton#Danger:disabled {{ color: {c['muted']}; border-color: {c['border']}; }}
    QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 8px;
                   padding: 4px 8px; }}
    QToolButton:hover {{ border-color: {c['border']}; background: {c['surface2']}; }}

    QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
        background: {c['input']}; border: 1px solid {c['border']}; border-radius: 8px;
        padding: 5px 8px; selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; }}
    QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {c['accent']}; }}
    QComboBox:disabled, QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
        color: {c['muted']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{ background: {c['surface2']}; border: 1px solid {c['border']};
        selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; outline: 0; }}
    QCheckBox, QRadioButton {{ background: transparent; spacing: 8px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px;
                            border: 1.5px solid {c['muted']}; background: {c['input']}; }}
    QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}
    QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']};
                                    image: url(CHECKMARK); }}
    QCheckBox::indicator:disabled {{ border-color: {c['border']}; }}
    QCheckBox::indicator:checked:disabled {{ background: {c['border']}; }}

    QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 10px; top: -1px;
                        background: {c['surface']}; }}
    QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 8px 16px; margin-right: 2px;
                    border-bottom: 2px solid transparent; font-weight: 600; }}
    QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
    QTabBar::tab:hover {{ color: {c['text']}; }}

    QProgressBar {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 6px;
                    height: 10px; text-align: center; color: transparent; }}
    QProgressBar::chunk {{ background: {c['accent']}; border-radius: 5px; }}

    QHeaderView::section {{ background: {c['surface2']}; color: {c['muted']}; border: none;
                            border-bottom: 1px solid {c['border']}; padding: 6px; font-weight: 600; }}
    QTableView {{ background: {c['surface']}; alternate-background-color: {c['surface2']};
                  gridline-color: {c['border']}; border: none; }}
    QScrollArea {{ border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 30px; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 4px; min-width: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QSplitter::handle {{ background: {c['bg']}; }}
    QStatusBar {{ background: {c['surface']}; color: {c['muted']}; border-top: 1px solid {c['border']}; }}
    QGroupBox {{ border: none; }}
    """.replace("CHECKMARK", checkmark.replace("\\", "/"))


def checkmark_file(name: str) -> str:
    """Write the check mark used by QCheckBox as a small SVG and return its path."""
    from ..paths import data_dir
    color = THEMES[name]["accent_text"]
    folder = data_dir() / "ui"
    folder.mkdir(exist_ok=True)
    path = folder / f"check_{name}.svg"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
           f'<path d="M3.5 8.5l3 3 6-7" fill="none" stroke="{color}" stroke-width="2.2" '
           f'stroke-linecap="round" stroke-linejoin="round"/></svg>')
    if not path.exists() or path.read_text() != svg:
        path.write_text(svg)
    return str(path)
