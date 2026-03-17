from __future__ import annotations

from PySide6.QtGui import QColor, QPalette


APP_STYLESHEET = """
QWidget {
    background: #11131a;
    color: #f3eee4;
    font-family: "Segoe UI Variable Text", "Bahnschrift", "Segoe UI";
    font-size: 10.5pt;
    selection-background-color: #c9a46b;
    selection-color: #17130d;
}
QLabel {
    background-color: transparent;
}
QMainWindow, QWidget#AppCanvas {
    background: #0d0f14;
}
QFrame#Card {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #151923, stop:1 #10141c);
    border: 1px solid #2a303c;
    border-radius: 22px;
}
QFrame#HeaderCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #171c26, stop:0.56 #11161f, stop:1 #0d1219);
    border: 1px solid #313847;
    border-radius: 32px;
}
QFrame#HeaderLogoCard {
    background: qradialgradient(cx:0.5, cy:0.42, radius:0.9, stop:0 rgba(28, 35, 48, 245), stop:0.72 rgba(18, 23, 33, 230), stop:1 rgba(13, 17, 24, 214));
    border: 1px solid rgba(201, 164, 107, 92);
    border-radius: 28px;
}
QFrame#LoaderShell {
    background: #10151d;
    border: 1px solid #28303d;
    border-radius: 30px;
}
QFrame#LoginCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #141922, stop:0.58 #10151d, stop:1 #0d1219);
    border: 1px solid #28303d;
    border-radius: 26px;
}
QLineEdit, QComboBox, QSpinBox {
    background: #10151d;
    border: 1px solid #28303b;
    border-radius: 14px;
    padding: 11px 14px;
    color: #f5efe5;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    background: #151b24;
    border: 1px solid #c9a46b;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QComboBox QAbstractItemView {
    background: #141922;
    border: 1px solid #2d3442;
    selection-background-color: #c9a46b;
    selection-color: #17130d;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d5b47d, stop:1 #ba8e4e);
    color: #17120b;
    border: none;
    border-radius: 15px;
    padding: 12px 20px;
    font-family: "Bahnschrift";
    font-weight: 700;
    letter-spacing: 0.4px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #e0bf88, stop:1 #c79958);
}
QPushButton:pressed {
    background: #ad8044;
}
QPushButton:disabled {
    background: #3a4352;
    color: #9ca6b7;
}
QLabel#HeroEyebrow {
    color: #c9a46b;
    font-family: "Bahnschrift";
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
}
QLabel#HeroTitle {
    font-family: "Bahnschrift";
    font-size: 28pt;
    font-weight: 700;
    letter-spacing: 0.5px;
}
QLabel#HeaderMainTitle {
    color: #f6f1e8;
    font-family: "Bahnschrift";
    font-size: 30pt;
    font-weight: 700;
    letter-spacing: 0.3px;
}
QLabel#HeaderLead {
    color: #d9c7a4;
    font-size: 11.2pt;
    font-weight: 600;
}
QLabel#HeaderNote {
    color: #98a4b6;
    font-size: 9.7pt;
}
QFrame#HeaderDivider {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(201, 164, 107, 0), stop:0.18 rgba(201, 164, 107, 70), stop:0.5 rgba(201, 164, 107, 120), stop:0.82 rgba(201, 164, 107, 70), stop:1 rgba(201, 164, 107, 0));
    border: none;
}
QLabel#HeaderContextLabel {
    color: #c9a46b;
    font-family: "Bahnschrift";
    font-size: 8.6pt;
    font-weight: 700;
    letter-spacing: 2.1px;
    text-transform: uppercase;
}
QLabel#HeaderContextValue {
    color: #f1eadf;
    font-family: "Bahnschrift";
    font-size: 14pt;
    font-weight: 700;
}
QLabel#HeaderContextNote {
    color: #8e9aac;
    font-size: 9.3pt;
}
QLabel#LoaderEyebrow {
    color: #c9a46b;
    font-family: "Bahnschrift";
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 2.2px;
    text-transform: uppercase;
}
QLabel#LoaderTitle {
    font-family: "Bahnschrift";
    font-size: 21pt;
    font-weight: 700;
    letter-spacing: 0.4px;
    background-color: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}
QLabel#LoaderSubtitle {
    color: #9aa6b8;
    font-size: 10.2pt;
    background-color: transparent;
}
QWidget#LoaderStatusCard {
    background-color: transparent;
    border: none;
    border-radius: 18px;
}
QLabel#LoaderStatus {
    color: #f3eee4;
    font-size: 10.8pt;
    font-weight: 600;
    background-color: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}
QLabel#LoaderHint {
    color: #c9a46b;
    font-size: 8.8pt;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    background-color: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}
QLabel#LoginEyebrow {
    color: #c9a46b;
    font-family: "Bahnschrift";
    font-size: 8.8pt;
    font-weight: 700;
    letter-spacing: 1.8px;
    text-transform: uppercase;
}
QLabel#LoginTitle {
    font-family: "Bahnschrift";
    font-size: 18pt;
    font-weight: 700;
}
QLabel#LoginLead {
    color: #a3acbd;
    font-size: 10pt;
}
QLineEdit#LoginInput {
    background: transparent;
    border: none;
    border-bottom: 1px solid #313948;
    border-radius: 0px;
    padding: 10px 2px 8px 2px;
    color: #f5efe5;
}
QLineEdit#LoginInput:focus {
    background: transparent;
    border: none;
    border-bottom: 1px solid #c9a46b;
}
QPushButton#LoginButton {
    margin-top: 4px;
}
QLabel#LoginStatus {
    color: #99a3b4;
    font-size: 9.6pt;
}
QLabel#SectionTitle {
    font-family: "Bahnschrift";
    font-size: 16.5pt;
    font-weight: 700;
}
QLabel#SectionLead {
    color: #a3acbd;
    font-size: 10pt;
}
QLabel#HeaderBadge {
    background: #151b24;
    border: 1px solid #303846;
    border-radius: 14px;
    color: #d8c39c;
    padding: 7px 12px;
    font-size: 8.8pt;
    font-weight: 700;
    letter-spacing: 0.6px;
}
QLabel#Muted {
    color: #99a3b4;
}
QLabel#InlineNotice {
    background: #10151d;
    border: 1px solid #252d39;
    border-radius: 14px;
    color: #c7cfdb;
    padding: 11px 13px;
}
QFrame#RankingHeroCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #171c25, stop:0.56 #11161f, stop:1 #0d1219);
    border: 1px solid #313847;
    border-radius: 28px;
}
QLabel#RankingHeroTitle {
    color: #f6f1e8;
    font-family: "Bahnschrift";
    font-size: 22pt;
    font-weight: 700;
    letter-spacing: 0.3px;
}
QLabel#RankingHeroLead {
    color: #d9c7a4;
    font-size: 10.8pt;
    font-weight: 600;
}
QLabel#RankingStatusNotice {
    background: rgba(10, 14, 19, 148);
    border: 1px solid rgba(53, 62, 76, 210);
    border-radius: 16px;
    color: #c6cfdb;
    padding: 12px 14px;
}
QFrame#RankingOverviewCard {
    background: rgba(9, 13, 18, 164);
    border: 1px solid rgba(72, 81, 98, 205);
    border-radius: 18px;
    min-width: 138px;
}
QLabel#RankingOverviewValue {
    font-family: "Bahnschrift";
    font-size: 15pt;
    font-weight: 700;
}
QLabel#RankingOverviewLabel {
    color: #8f99ab;
    font-size: 8.4pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QFrame#RankingRowCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #151a23, stop:1 #10141c);
    border: 1px solid #2c3340;
    border-radius: 24px;
}
QFrame#RankingTopRow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #171c25, stop:1 #11161e);
    border: 1px solid rgba(168, 138, 92, 130);
    border-radius: 24px;
}
QFrame#RankingLeaderRow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1b2028, stop:0.52 #141922, stop:1 #11151d);
    border: 1px solid rgba(201, 164, 107, 180);
    border-radius: 24px;
}
QFrame#RankingPositionBadge {
    background: rgba(10, 14, 20, 176);
    border: 1px solid rgba(201, 164, 107, 120);
    border-radius: 18px;
}
QLabel#RankingPositionLabel {
    color: #9fa9b9;
    font-size: 7.6pt;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}
QLabel#RankingPositionValue {
    color: #e8dcc5;
    font-family: "Bahnschrift";
    font-size: 16pt;
    font-weight: 700;
}
QLabel#RankingPositionValueLeader {
    color: #f0d7a2;
    font-family: "Bahnschrift";
    font-size: 16pt;
    font-weight: 700;
}
QLabel#RankingMetaPill {
    background: rgba(10, 14, 20, 150);
    border: 1px solid rgba(56, 65, 78, 185);
    border-radius: 13px;
    color: #97a3b5;
    padding: 5px 10px;
    font-size: 8.8pt;
    font-weight: 600;
}
QFrame#RankingStatCard {
    background: rgba(10, 14, 20, 156);
    border: 1px solid rgba(56, 65, 78, 190);
    border-radius: 16px;
    min-width: 128px;
}
QLabel#RankingStatValue {
    font-family: "Bahnschrift";
    font-size: 13pt;
    font-weight: 700;
}
QLabel#RankingStatLabel {
    color: #8f99ab;
    font-size: 7.9pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QFrame#RankingInsightsPanel {
    background: rgba(9, 13, 18, 128);
    border: 1px solid rgba(49, 57, 70, 185);
    border-radius: 18px;
}
QLabel#RankingInsightsTitle {
    color: #c9a46b;
    font-size: 8.6pt;
    font-weight: 700;
    letter-spacing: 1.6px;
    text-transform: uppercase;
}
QFrame#RankingChampionChip {
    background: rgba(10, 14, 20, 168);
    border: 1px solid rgba(56, 65, 78, 180);
    border-radius: 14px;
}
QLabel#RankingChampionName {
    color: #e8edf6;
    font-size: 9.3pt;
    font-weight: 700;
}
QLabel#RankingChampionGames {
    color: #8ea1bb;
    font-size: 8.1pt;
}
QFrame#HomeHeroCard {
    background: transparent;
    border: none;
}
QLabel#HomeTopBadge {
    background: rgba(9, 12, 17, 180);
    border: 1px solid rgba(93, 76, 50, 180);
    border-radius: 13px;
    color: #dfc89f;
    padding: 7px 12px;
    font-size: 8.6pt;
    font-weight: 700;
    letter-spacing: 0.8px;
}
QLabel#HomeKicker {
    color: #d1ab71;
    font-family: "Bahnschrift";
    font-size: 8.8pt;
    font-weight: 700;
    letter-spacing: 2.6px;
    text-transform: uppercase;
}
QLabel#HomeHugeTitle {
    font-family: "Bahnschrift";
    font-size: 33pt;
    font-weight: 700;
    line-height: 1.0;
    color: #f5f1e8;
    letter-spacing: 0.4px;
}
QLabel#HomeCaption {
    color: #b9b0a4;
    font-size: 10.1pt;
}
QPushButton#HomePrimaryButton {
    min-width: 132px;
    padding: 12px 22px;
}
QPushButton#HomeSecondaryButton {
    background: rgba(12, 15, 20, 175);
    color: #ecd7b1;
    border: 1px solid rgba(112, 89, 55, 210);
    border-radius: 15px;
    padding: 12px 20px;
    min-width: 118px;
}
QPushButton#HomeSecondaryButton:hover {
    background: rgba(17, 21, 28, 210);
    border-color: #c39a5b;
}
QPushButton#HomeSecondaryButton:pressed {
    background: rgba(10, 13, 18, 235);
}
QPushButton#HomeQuickCardButton {
    background: rgba(8, 11, 16, 190);
    color: #f0eadf;
    border: 1px solid rgba(67, 74, 87, 210);
    border-radius: 20px;
    padding: 0px;
    min-height: 92px;
    text-align: left;
    font-size: 11pt;
    font-weight: 700;
}
QPushButton#HomeQuickCardButton:hover {
    background: rgba(12, 16, 22, 228);
    border-color: rgba(201, 164, 107, 210);
}
QPushButton#HomeQuickCardButton:pressed {
    background: rgba(9, 11, 15, 245);
}
QFrame#HomeQuickIconShell {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(18, 22, 30, 215), stop:1 rgba(10, 13, 18, 235));
    border: 1px solid rgba(201, 164, 107, 155);
    border-radius: 14px;
}
QLabel#HomeQuickCardTitle {
    color: #f3ede1;
    font-family: "Bahnschrift";
    font-size: 12.6pt;
    font-weight: 700;
    background-color: transparent;
    margin: 0px;
    padding: 0px;
}
QLabel#HomeQuickCardSubtitle {
    color: #c9a46b;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    background-color: transparent;
    margin: 0px;
    padding: 0px;
}
QLabel#HomeCredit {
    color: rgba(220, 206, 179, 150);
    font-size: 8.6pt;
    letter-spacing: 0.5px;
    background-color: transparent;
}
QFrame#PlayerShowcaseInfoPanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(8, 11, 16, 182), stop:1 rgba(13, 17, 24, 228));
    border: 1px solid rgba(205, 171, 115, 74);
    border-radius: 18px;
}
QLabel#PlayerShowcaseChampion {
    background-color: transparent;
    color: #f7f0e2;
    font-family: "Bahnschrift";
    font-size: 13.8pt;
    font-weight: 700;
}
QLabel#PlayerShowcaseSkin {
    background-color: transparent;
    color: #d6b06e;
    font-size: 8.8pt;
    font-weight: 700;
    letter-spacing: 0.4px;
}
QLabel#PlayerShowcaseSummoner {
    background-color: transparent;
    color: #f4ecde;
    font-size: 11.8pt;
    font-weight: 700;
}
QLabel#StatValue {
    font-family: "Bahnschrift";
    font-size: 17pt;
    font-weight: 700;
}
QLabel#StatLabel {
    color: #8f99ab;
    font-size: 8.8pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QTabWidget::pane {
    border: none;
    background: transparent;
    margin-top: 12px;
}
QTabBar::tab {
    background: #131823;
    border: 1px solid #2a313e;
    border-radius: 16px;
    color: #aeb7c7;
    padding: 10px 18px;
    margin-right: 8px;
    font-family: "Bahnschrift";
    font-weight: 700;
}
QTabBar::tab:selected {
    background: #c9a46b;
    border-color: #c9a46b;
    color: #17120b;
}
QTabBar::tab:hover:!selected {
    background: #1a202c;
    color: #eff3f8;
}
QScrollArea, QStackedWidget {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 4px 0 4px 0;
}
QScrollBar::handle:vertical {
    background: #3a4250;
    border-radius: 6px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: #505a6c;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar:horizontal, QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
    border: none;
    height: 0px;
}
QFrame#MatchWin {
    background: #112320;
    border: 1px solid #35584c;
    border-radius: 16px;
}
QFrame#MatchLoss {
    background: #23151a;
    border: 1px solid #67414b;
    border-radius: 16px;
}
"""


def build_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0d0f14"))
    palette.setColor(QPalette.WindowText, QColor("#f3eee4"))
    palette.setColor(QPalette.Base, QColor("#10151d"))
    palette.setColor(QPalette.AlternateBase, QColor("#151923"))
    palette.setColor(QPalette.ToolTipBase, QColor("#151923"))
    palette.setColor(QPalette.ToolTipText, QColor("#f3eee4"))
    palette.setColor(QPalette.Text, QColor("#f3eee4"))
    palette.setColor(QPalette.Button, QColor("#c9a46b"))
    palette.setColor(QPalette.ButtonText, QColor("#17120b"))
    palette.setColor(QPalette.Highlight, QColor("#c9a46b"))
    palette.setColor(QPalette.HighlightedText, QColor("#17120b"))
    return palette
