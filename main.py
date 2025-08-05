
import sys
import os
import logging
from urllib.parse import quote_plus, urlparse, parse_qs
from pathlib import Path
import re
import random
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import QCoreApplication, QStringListModel, QThread, pyqtSignal, Qt, QTimer, QEvent, QPoint, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from gensim.models import Word2Vec
from sklearn.metrics.pairwise import linear_kernel
from scipy.io import mmread
import pickle
import webbrowser

# 루트 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# 콘솔 핸들러
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# 파일 핸들러 (UTF-8 인코딩)
file_handler = logging.FileHandler('recommendation.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# 기존 핸들러 제거
if logger.hasHandlers():
    logger.handlers.clear()

# 핸들러 등록
logger.addHandler(console_handler)
logger.addHandler(file_handler)


class LoadingWidget(QWidget):
    """로딩 애니메이션 위젯"""

    def __init__(self):
        super().__init__()
        self.angle = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.rotate)
        self.setFixedSize(120, 120)

    def start_animation(self):
        self.timer.start(50)

    def stop_animation(self):
        self.timer.stop()

    def rotate(self):
        self.angle = (self.angle + 12) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        center = rect.center()
        radius = min(rect.width(), rect.height()) // 2 - 15
        painter.translate(center)
        painter.rotate(self.angle)
        gradient = QConicalGradient(0, 0, 0)
        gradient.setColorAt(0.0, QColor(52, 152, 219, 255))
        gradient.setColorAt(0.3, QColor(155, 89, 182, 255))
        gradient.setColorAt(0.7, QColor(46, 204, 168, 255))
        gradient.setColorAt(1.0, QColor(52, 152, 219, 100))
        pen = QPen(QBrush(gradient), 6, cap=Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(-radius, -radius, radius * 2, radius * 2, 0, 270 * 16)


class RecommendationThread(QThread):
    """추천 작업 스레드"""
    recommendation_finished = pyqtSignal(list)
    recommendation_error = pyqtSignal(str)

    def __init__(self, app_instance, input_text, is_keyword=False, index=None):
        super().__init__()
        self.app_instance = app_instance
        self.input_text = input_text
        self.is_keyword = is_keyword
        self.index = index

    def run(self):
        try:
            logging.debug(f"RecommendationThread 시작: 입력={self.input_text}, 키워드 여부={self.is_keyword}, 인덱스={self.index}")
            if self.is_keyword:
                recommendations = self.app_instance.keyword_recommendation(self.input_text)
            else:
                recommendations = self.app_instance.game_title_recommendation(title=self.input_text, index=self.index)
            logging.debug(f"RecommendationThread 완료: 추천 결과={recommendations}")
            self.recommendation_finished.emit(recommendations)
        except Exception as e:
            error_msg = f"RecommendationThread 오류: {str(e)}"
            logging.error(error_msg)
            self.recommendation_error.emit(error_msg)


class GameTooltipWidget(QWidget):
    """게임 툴팁 위젯 (Description만 표시)"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(
            "QWidget { background: rgba(255, 255, 255, 0.95); border: 2px solid #3498db; border-radius: 10px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("color: #2c3e50; font-size: 12px;")
        layout.addWidget(self.description_label)
        self.hide()

    def set_content(self, description):
        logging.debug(f"툴팁 설정: 설명={description[:50]}...")
        description = description[:200] + "..." if len(description) > 200 else description
        self.description_label.setText(description or "설명 없음")
        self.adjustSize()


class GameInfoWidget(QWidget):
    """게임 정보 표시 위젯 - 이름과 Description만 표시"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background: rgba(255, 255, 255, 0.95); border: 2px solid #3498db; border-radius: 10px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.title_label = QLabel("게임 정보")
        self.title_label.setFont(QFont("Malgun Gothic", 16, QFont.Bold))
        self.title_label.setStyleSheet("color: #2c3e50;")
        layout.addWidget(self.title_label)

        self.name_label = QLabel("이름: ")
        self.name_label.setStyleSheet("color: #2c3e50; font-size: 12px;")
        layout.addWidget(self.name_label)

        self.description_label = QLabel("설명: ")
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("color: #2c3e50; font-size: 12px; max-height: 200px;")
        layout.addWidget(self.description_label)

    def set_info(self, name, description):
        self.name_label.setText(f"이름: {name}")
        description = description[:300] + "..." if len(description) > 300 else description
        self.description_label.setText(f"설명: {description or '설명 없음'}")
        self.adjustSize()


class GameRecommendationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.widget_List = []
        self.current_selected_game = None
        self.models_loaded = False
        self.init_ui()
        self.load_models()
        self.setup_connections()
        self.tooltip_widget = None
        self.tooltip_timer = QTimer()
        self.tooltip_timer.setSingleShot(True)
        self.tooltip_timer.timeout.connect(self.show_tooltip_delayed)
        self.current_tooltip_game = None
        logging.debug(f"초기화 완료, models_loaded={self.models_loaded}")

    def init_ui(self):
        self.setWindowTitle("🎮 게임 추천 시스템")
        self.setMinimumSize(1600, 900)
        self.resize(1800, 1000)
        self.setStyleSheet(
            "QMainWindow { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #667eea, stop:1 #764ba2); } QWidget { font-family: 'Malgun Gothic', Arial, sans-serif; }")

        font = QFont("Malgun Gothic", 12)
        QApplication.setFont(font)

        self.centralwidget = QWidget()
        self.centralwidget.setStyleSheet("QWidget { background: transparent; }")
        self.setCentralWidget(self.centralwidget)

        main_layout = QHBoxLayout(self.centralwidget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(30)

        # 좌측 패널 (입력 및 결과)
        left_panel = QWidget()
        left_panel.setStyleSheet(
            "QWidget { background: rgba(255, 255, 255, 0.95); border-radius: 20px; border: 2px solid rgba(255, 255, 255, 0.3); }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(40, 40, 40, 40)
        left_layout.setSpacing(25)

        title_label = QLabel("🎮 게임 추천 시스템")
        title_label.setFont(QFont("Malgun Gothic", 28, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            "QLabel { color: #2c3e50; margin: 20px 0; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff6b6b, stop:1 #4ecdc4); -webkit-background-clip: text; border-radius: 15px; padding: 15px; background-color: rgba(255, 255, 255, 0.1); }")
        left_layout.addWidget(title_label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("QFrame { color: #bdc3c7; margin: 10px 0; }")
        left_layout.addWidget(line)

        combo_section = QWidget()
        combo_layout = QVBoxLayout(combo_section)
        combo_layout.setSpacing(10)
        combo_label = QLabel("📋 게임 목록에서 선택")
        combo_label.setFont(QFont("Malgun Gothic", 14, QFont.Bold))
        combo_label.setStyleSheet("QLabel { color: #34495e; margin-bottom: 5px; }")
        self.game_combobox = QComboBox()
        self.game_combobox.setFixedHeight(45)
        self.game_combobox.setStyleSheet(
            "QComboBox { border: 2px solid #3498db; border-radius: 12px; padding: 8px 15px; font-size: 14px; background: white; selection-background-color: #3498db; } QComboBox:hover { border-color: #2980b9; background: #ecf0f1; } QComboBox::drop-down { border: none; width: 30px; } QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 8px solid #3498db; margin-right: 10px; } QComboBox::item:hover { background: #e8f8f5; }")
        self.game_combobox.setFont(QFont("Malgun Gothic", 12))
        self.game_combobox.view().installEventFilter(self)
        logging.debug("QComboBox 뷰에 이벤트 필터 설치 완료")
        combo_layout.addWidget(combo_label)
        combo_layout.addWidget(self.game_combobox)
        left_layout.addWidget(combo_section)

        input_section = QWidget()
        input_section_layout = QVBoxLayout(input_section)
        input_section_layout.setSpacing(15)
        input_label = QLabel("✏️ 또는 직접 입력")
        input_label.setFont(QFont("Malgun Gothic", 14, QFont.Bold))
        input_label.setStyleSheet("QLabel { color: #34495e; margin-bottom: 5px; }")
        input_layout = QHBoxLayout()
        input_layout.setSpacing(15)
        self.game_input = QLineEdit()
        self.game_input.setFixedHeight(45)
        self.game_input.setPlaceholderText("게임 이름 또는 키워드를 입력하세요...")
        self.game_input.setFont(QFont("Malgun Gothic", 12))
        self.game_input.setStyleSheet(
            "QLineEdit { border: 2px solid #9b59b6; border-radius: 12px; padding: 8px 15px; font-size: 14px; background: white; } QLineEdit:focus { border-color: #8e44ad; background: #f8f9fa; } QLineEdit::placeholder { color: #95a5a6; font-style: italic; }")
        self.recommend_button = QPushButton("🚀 추천 시작")
        self.recommend_button.setFixedSize(150, 45)
        self.recommend_button.setFont(QFont("Malgun Gothic", 12, QFont.Bold))
        self.recommend_button.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff6b6b, stop:1 #ff8e8e); color: white; border: none; border-radius: 12px; } QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff5252, stop:1 #ff7979); } QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e74c3c, stop:1 #c0392b); }")
        input_layout.addWidget(self.game_input, 3)
        input_layout.addWidget(self.recommend_button, 1)
        input_section_layout.addWidget(input_label)
        input_section_layout.addLayout(input_layout)
        left_layout.addWidget(input_section)

        self.loading_widget = LoadingWidget()
        self.loading_label = QLabel("🔄 추천 중...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setFont(QFont("Malgun Gothic", 16, QFont.Bold))
        self.loading_label.setStyleSheet(
            "QLabel { color: #3498db; margin: 20px 0; padding: 15px; background: rgba(52, 152, 219, 0.1); border-radius: 15px; }")
        loading_layout = QVBoxLayout()
        loading_layout.setSpacing(20)
        loading_layout.addWidget(self.loading_widget, alignment=Qt.AlignCenter)
        loading_layout.addWidget(self.loading_label)
        self.loading_container = QWidget()
        self.loading_container.setLayout(loading_layout)
        self.loading_container.hide()
        left_layout.addWidget(self.loading_container)

        self.result_label = QLabel("🎯 추천된 게임")
        self.result_label.setFont(QFont("Malgun Gothic", 18, QFont.Bold))
        self.result_label.setStyleSheet(
            "QLabel { color: #2c3e50; margin: 20px 0 10px 0; padding: 10px; background: rgba(46, 204, 113, 0.1); border-radius: 10px; border-left: 4px solid #2ecc71; font-weight: bold; }")
        self.result_label.setWordWrap(True)
        self.result_label.hide()
        self.result_list = QListWidget()
        self.result_list.setMinimumHeight(300)
        self.result_list.setFont(QFont("Malgun Gothic", 12))
        self.result_list.setStyleSheet(
            "QListWidget { border: 2px solid #2ecc71; border-radius: 15px; background: white; padding: 10px; font-size: 14px; } QListWidget::item { border: 1px solid #ecf0f1; border-radius: 8px; padding: 15px; margin: 5px; background: #f8f9fa; } QListWidget::item:hover { background: #e8f8f5; } QListWidget::item:selected { background: #2ecc71; color: white; border-color: #27ae60; }")
        self.result_list.hide()
        left_layout.addWidget(self.result_label)
        left_layout.addWidget(self.result_list)
        left_layout.addStretch()

        # 중간 패널 (기준 게임 정보)
        middle_panel = QWidget()
        middle_panel.setStyleSheet(
            "QWidget { background: rgba(255, 255, 255, 0.95); border-radius: 20px; border: 2px solid rgba(255, 255, 255, 0.3); }")
        middle_layout = QVBoxLayout(middle_panel)
        middle_layout.setContentsMargins(40, 40, 40, 40)
        middle_layout.setSpacing(30)

        ref_title = QLabel("🔍 기준 게임 정보")
        ref_title.setFont(QFont("Malgun Gothic", 20, QFont.Bold))
        ref_title.setAlignment(Qt.AlignCenter)
        ref_title.setStyleSheet(
            "QLabel { color: #2c3e50; margin-bottom: 20px; padding: 15px; background: rgba(155, 89, 182, 0.1); border-radius: 15px; border-left: 4px solid #9b59b6; }")
        middle_layout.addWidget(ref_title)

        self.ref_widget_youtube = QWidget()
        self.widget_List.append(self.ref_widget_youtube)
        self.ref_widget_youtube.setMinimumSize(500, 300)
        self.ref_widget_youtube.setStyleSheet("background-color: rgb(84, 84, 84);")
        self.ref_widget_youtube.setObjectName("ref_widget_youtube")
        self.ref_webview = QWebEngineView(self.ref_widget_youtube)
        self.ref_webview.setUrl(QUrl("about:blank"))
        self.ref_webview.setGeometry(QtCore.QRect(0, 0, 500, 300))
        self.ref_webview.loadFinished.connect(self.on_ref_webview_load_finished)
        middle_layout.addWidget(self.ref_widget_youtube)

        self.ref_game_info_widget = GameInfoWidget()
        self.ref_game_info_widget.hide()
        middle_layout.addWidget(self.ref_game_info_widget)
        middle_layout.addStretch()

        # 우측 패널 (게임 미리보기)
        right_panel = QWidget()
        right_panel.setStyleSheet(
            "QWidget { background: rgba(255, 255, 255, 0.95); border-radius: 20px; border: 2px solid rgba(255, 255, 255, 0.3); }")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(40, 40, 40, 40)
        right_layout.setSpacing(30)

        image_title = QLabel("🖼️ 게임 미리보기")
        image_title.setFont(QFont("Malgun Gothic", 20, QFont.Bold))
        image_title.setAlignment(Qt.AlignCenter)
        image_title.setStyleSheet(
            "QLabel { color: #2c3e50; margin-bottom: 20px; padding: 15px; background: rgba(155, 89, 182, 0.1); border-radius: 15px; border-left: 4px solid #9b59b6; }")
        right_layout.addWidget(image_title)

        self.widget_youtube = QWidget()
        self.widget_List.append(self.widget_youtube)
        self.widget_youtube.setMinimumSize(500, 300)
        self.widget_youtube.setStyleSheet("background-color: rgb(84, 84, 84);")
        self.widget_youtube.setObjectName("widget_youtube")
        self.webview = QWebEngineView(self.widget_youtube)
        self.webview.setUrl(QUrl("about:blank"))
        self.webview.setGeometry(QtCore.QRect(0, 0, 500, 300))
        self.webview.loadFinished.connect(self.on_webview_load_finished)
        right_layout.addWidget(self.widget_youtube)

        self.game_info_widget = GameInfoWidget()
        self.game_info_widget.hide()
        right_layout.addWidget(self.game_info_widget)

        self.play_button = QPushButton("🎮 지금 바로 플레이!!")
        self.play_button.setFixedSize(300, 70)
        self.play_button.setFont(QFont("Malgun Gothic", 16, QFont.Bold))
        self.play_button.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff4757, stop:1 #ff3742); color: white; border: none; border-radius: 20px; font-weight: bold; font-style: italic; text-transform: uppercase; } QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff3742, stop:1 #ff2f3a); } QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #c0392b, stop:1 #a93226); }")
        self.play_button.setEnabled(False)
        right_layout.addWidget(self.play_button, alignment=Qt.AlignCenter)
        right_layout.addStretch()

        # 메인 레이아웃에 패널 추가
        main_layout.addWidget(left_panel, 3)
        main_layout.addWidget(middle_panel, 2)
        main_layout.addWidget(right_panel, 2)

    def load_models(self):
        try:
            # CSV 로드
            try:
                self.game_data = pd.read_csv("./Crawling_data/steam_game_translated.csv", encoding='utf-8')
            except UnicodeDecodeError:
                logging.warning("UTF-8로 CSV 로드 실패, cp949로 재시도")
                self.game_data = pd.read_csv("./Crawling_data/steam_game_translated.csv", encoding='cp949')

            # 데이터 검증
            required_columns = ['Title', 'Description']
            missing_columns = [col for col in required_columns if col not in self.game_data.columns]
            if missing_columns:
                raise ValueError(f"CSV 파일에 필수 열이 없습니다: {missing_columns}")
            if self.game_data.empty:
                raise ValueError("CSV 파일이 비어 있습니다.")

            # 데이터 전처리
            self.game_data['Title'] = self.game_data['Title'].astype(str).str.strip()
            self.game_data['Description'] = self.game_data['Description'].fillna('no description')

            # 게임 제목 목록 생성 (CSV 순서 유지, 중복 제거)
            self.game_titles = list(dict.fromkeys(self.game_data['Title'].dropna().tolist()))
            if not self.game_titles:
                raise ValueError("게임 제목 목록이 비어 있습니다.")
            logging.debug(f"로드된 게임 수: {len(self.game_titles)}, 처음 5개: {self.game_titles[:5]}")

            # 콤보박스 업데이트
            self.game_combobox.clear()
            self.game_combobox.addItems(self.game_titles)

            self.game_descriptions = self.game_data.set_index('Title')['Description'].to_dict()
            self.game_images = self.game_data.set_index('Title').get('image_path', pd.Series(dtype=str)).to_dict()

            # 자동 완성 설정
            model = QStringListModel(self.game_titles, self)
            completer = QCompleter(model, self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            completer.setMaxVisibleItems(10)
            completer.popup().setStyleSheet("""
                QAbstractItemView {
                    background: #ffffff;
                    border: 2px solid #3498db;
                    border-radius: 8px;
                    padding: 5px;
                    font-family: 'Malgun Gothic', Arial, sans-serif;
                    font-size: 14px;
                    color: #2c3e50;
                }
                QAbstractItemView::item {
                    padding: 8px;
                    border-radius: 5px;
                }
                QAbstractItemView::item:selected {
                    background: #3498db;
                    color: white;
                }
            """)
            self.game_input.setCompleter(completer)
            logging.debug(f"자동 완성 설정 완료: 게임 제목 수={len(self.game_titles)}")

            self.game_combobox.update()
            QApplication.processEvents()
        except Exception as e:
            logging.error(f"CSV 데이터 로드 오류: {str(e)}")
            QMessageBox.critical(self, "오류", f"CSV 데이터 로드 중 오류: {str(e)}")
            self.game_titles = []
            self.game_descriptions = {}
            self.game_images = {}
            return

        # 모델 로드
        try:
            self.word2vec_model = Word2Vec.load("./model/word2vec_steam.model")
            logging.debug("Word2Vec 모델 로드 완료")
        except Exception as e:
            logging.error(f"Word2Vec 모델 로드 오류: {str(e)}")
            self.word2vec_model = None

        try:
            self.tfidf_matrix = mmread("./model/tfidf_steam.mtx").tocsr()
            with open("./model/tfidf_steam.pickle", "rb") as f:
                self.tfidf_vectorizer = pickle.load(f)
            logging.debug("TF-IDF 모델 로드 완료")
        except Exception as e:
            logging.error(f"TF-IDF 모델 로드 오류: {str(e)}")
            self.tfidf_matrix = None
            self.tfidf_vectorizer = None

        self.models_loaded = (self.word2vec_model is not None and
                              self.tfidf_matrix is not None and
                              self.tfidf_vectorizer is not None)
        logging.debug(f"모델 로드 상태: models_loaded={self.models_loaded}")

    def setup_connections(self):
        try:
            self.game_combobox.currentIndexChanged.connect(self.on_combobox_changed)
            self.recommend_button.clicked.connect(self.start_recommendation)
            self.result_list.itemClicked.connect(self.on_game_selected)
            self.play_button.clicked.connect(self.on_play_button_clicked)
            self.game_input.returnPressed.connect(self.start_recommendation)
            logging.debug("시그널-슬롯 연결 완료")
        except Exception as e:
            logging.error(f"시그널 연결 오류: {str(e)}")

    def eventFilter(self, obj, event):
        if obj == self.game_combobox.view():
            if event.type() == QEvent.MouseMove:
                index = self.game_combobox.view().indexAt(event.pos())
                if index.isValid():
                    game_name = self.game_combobox.itemText(index.row())
                    if game_name != self.current_tooltip_game:
                        self.hide_game_tooltip()
                        self.current_tooltip_game = game_name
                        self.tooltip_timer.start(300)  # 반응성 향상
                        logging.debug(f"툴팁 타이머 시작: 게임={game_name}")
                else:
                    self.hide_game_tooltip()
                return True
            elif event.type() == QEvent.Leave:
                self.hide_game_tooltip()
                logging.debug("드롭다운 뷰 벗어남, 툴팁 숨김")
                return True
        return super().eventFilter(obj, event)
    def show_tooltip_delayed(self):
        if self.current_tooltip_game:
            game_name = self.current_tooltip_game
            global_pos = QCursor.pos()
            if not self.tooltip_widget:
                self.tooltip_widget = GameTooltipWidget(self)
                logging.debug("툴팁 위젯 생성")
            description = self.game_descriptions.get(game_name, "설명 없음")
            self.tooltip_widget.set_content(description)
            self.tooltip_widget.adjustSize()
            screen = QApplication.desktop().screenGeometry()
            tooltip_pos = global_pos + QPoint(10, -self.tooltip_widget.height() - 10)
            if tooltip_pos.x() + self.tooltip_widget.width() > screen.right():
                tooltip_pos.setX(screen.right() - self.tooltip_widget.width())
            if tooltip_pos.y() < screen.top():
                tooltip_pos.setY(screen.top())
            self.tooltip_widget.move(tooltip_pos)
            self.tooltip_widget.show()
            self.tooltip_widget.raise_()
            logging.debug(f"툴팁 표시: 게임={game_name}, 위치={tooltip_pos}")

    def hide_game_tooltip(self):
        if self.tooltip_widget:
            self.tooltip_widget.hide()
            logging.debug("툴팁 숨김")
        self.current_tooltip_game = None
        self.tooltip_timer.stop()

    def start_recommendation(self):
        logging.debug(f"추천 시작: models_loaded={self.models_loaded}")
        if not self.models_loaded:
            QMessageBox.warning(self, "경고", "추천 모델을 로드하지 못했습니다.")
            logging.warning("모델 로드 실패로 추천 중단")
            return

        user_input = self.game_input.text().strip() or self.game_combobox.currentText().strip()
        if not user_input:
            QMessageBox.warning(self, "경고", "게임 이름 또는 키워드를 입력하거나 선택하세요.")
            logging.warning("입력값 없음")
            return

        # 대소문자 무시 부분 일치 검색
        matched_title, index = None, None
        for i, title in enumerate(self.game_titles):
            if user_input.lower() in title.lower():
                matched_title = title
                index = self.game_data[self.game_data['Title'] == title].index[0]
                break
        is_keyword = matched_title is None
        user_input = matched_title if matched_title else user_input

        logging.debug(f"추천 시작: 입력={user_input}, 키워드 여부={is_keyword}, matched_title={matched_title}, 인덱스={index}")
        self.show_loading(True)
        self.hide_results()

        try:
            self.recommendation_thread = RecommendationThread(self, user_input, is_keyword, index)
            self.recommendation_thread.recommendation_finished.connect(self.on_recommendation_finished)
            self.recommendation_thread.recommendation_error.connect(self.on_recommendation_error)
            self.recommendation_thread.start()
            logging.debug("RecommendationThread 시작됨")
        except Exception as e:
            logging.error(f"RecommendationThread 시작 오류: {str(e)}")
            self.show_loading(False)
            QMessageBox.critical(self, "오류", f"추천 스레드 시작 실패: {str(e)}")

    def show_loading(self, show):
        if show:
            self.loading_container.show()
            self.loading_widget.start_animation()
        else:
            self.loading_container.hide()
            self.loading_widget.stop_animation()

    def hide_results(self):
        self.result_label.hide()
        self.result_list.hide()
        self.play_button.hide()
        self.play_button.setEnabled(False)
        self.game_info_widget.hide()
        self.webview.setUrl(QUrl("about:blank"))
        self.ref_webview.setUrl(QUrl("about:blank"))
        self.ref_game_info_widget.hide()

    def on_recommendation_finished(self, recommendations):
        self.show_loading(False)
        input_text = self.recommendation_thread.input_text
        is_keyword = self.recommendation_thread.is_keyword
        if recommendations:
            # 기준 게임 이름 또는 키워드 표시
            label_text = f"🎯 추천된 게임 (기준: {input_text})" if not is_keyword else f"🎯 추천된 게임 (키워드: {input_text})"
            self.result_label.setText(label_text)
            self.result_label.show()
            self.result_list.show()
            self.result_list.clear()
            for game in recommendations[:5]:
                self.result_list.addItem(game)
            logging.debug(f"추천 완료: 기준={input_text}, 키워드 여부={is_keyword}, 추천={recommendations[:5]}")

            # 기준 게임 정보 업데이트
            if not is_keyword:
                self.load_reference_game_info(input_text)
                self.ref_game_info_widget.show()
            else:
                self.ref_webview.setUrl(QUrl("about:blank"))
                self.ref_game_info_widget.hide()
        else:
            QMessageBox.information(self, "알림", "추천할 게임을 찾지 못했습니다.")
            self.ref_webview.setUrl(QUrl("about:blank"))
            self.ref_game_info_widget.hide()
            logging.debug(f"추천 결과 없음: 기준={input_text}, 키워드 여부={is_keyword}")
        QApplication.processEvents()

    def on_recommendation_error(self, error_msg):
        self.show_loading(False)
        QMessageBox.critical(self, "오류", f"추천 중 오류: {error_msg}")
        logging.error(f"추천 오류: {error_msg}")

    def on_combobox_changed(self):
        selected_game = self.game_combobox.currentText()
        if selected_game:
            self.game_input.setText(selected_game)
            logging.debug(f"콤보박스에서 선택된 게임: {selected_game}")

    def on_game_selected(self, item):
        selected_game = item.text()
        self.current_selected_game = selected_game
        self.load_game_image(selected_game)
        self.update_game_info(selected_game)
        self.play_button.show()
        self.play_button.setEnabled(True)
        logging.debug(f"추천 결과에서 게임 선택됨: {selected_game}")

    def update_game_info(self, game_name):
        description = self.game_descriptions.get(game_name, "설명 없음")
        self.game_info_widget.set_info(game_name, description)
        self.game_info_widget.show()
        logging.debug(f"게임 정보 업데이트: 이름={game_name}, 설명={description[:50]}...")

    def load_reference_game_info(self, game_name):
        try:
            # 게임 정보 업데이트
            description = self.game_descriptions.get(game_name, "설명 없음")
            self.ref_game_info_widget.set_info(game_name, description)
            logging.debug(f"기준 게임 정보 업데이트: {game_name}, 설명={description[:50]}...")

            # 유튜브 영상 로드
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            driver = webdriver.Chrome(options=chrome_options)
            logging.debug("Selenium 드라이버 초기화 완료 (기준 게임)")

            search_query = quote_plus(f"{game_name} trailershort")
            search_url = f"https://www.youtube.com/results?search_query={search_query}"
            driver.get(search_url)
            logging.debug(f"유튜브 검색 페이지 로드 (기준): {search_url}")

            wait = WebDriverWait(driver, 10)
            thumbnails = wait.until(
                EC.presence_of_all_elements_located((By.XPATH, '//*[@id="thumbnail"]/yt-image/img')))
            if len(thumbnails) >= 3:
                third_thumbnail = thumbnails[2]
                video_link = third_thumbnail.find_element(By.XPATH, "./ancestor::a[@id='thumbnail']").get_attribute(
                    "href")
                logging.debug(f"추출된 영상 URL (기준): {video_link}")

                parsed_url = urlparse(video_link)
                if "shorts" in parsed_url.path:
                    video_id = parsed_url.path.split("/shorts/")[1]
                elif "watch" in parsed_url.path:
                    video_id = parse_qs(parsed_url.query).get("v", [None])[0]
                else:
                    raise ValueError("알 수 없는 URL 형식")

                if not video_id:
                    raise ValueError("video_id 추출 실패")

                embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1"
                logging.debug(f"기준 게임 영상 임베드 URL: {embed_url}")
                self.ref_webview.setUrl(QUrl(embed_url))
            else:
                logging.warning(f"기준 게임의 3번째 쇼츠 영상을 찾을 수 없습니다: {game_name}")
                self.ref_webview.setUrl(QUrl(search_url))
        except Exception as e:
            logging.error(f"기준 게임 영상 로드 오류: {str(e)}")
            self.ref_webview.setUrl(QUrl(search_url))
        finally:
            if 'driver' in locals():
                driver.quit()
                logging.debug("Selenium 드라이버 종료 (기준 게임)")

    def load_game_image(self, game_name):
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            driver = webdriver.Chrome(options=chrome_options)
            logging.debug("Selenium 드라이버 초기화 완료")

            search_query = quote_plus(f"{game_name} trailershort")
            search_url = f"https://www.youtube.com/results?search_query={search_query}"
            driver.get(search_url)
            logging.debug(f"유튜브 검색 페이지 로드: {search_url}")

            wait = WebDriverWait(driver, 10)
            thumbnails = wait.until(
                EC.presence_of_all_elements_located((By.XPATH, '//*[@id="thumbnail"]/yt-image/img')))
            if len(thumbnails) >= 3:
                third_thumbnail = thumbnails[2]
                video_link = third_thumbnail.find_element(By.XPATH, "./ancestor::a[@id='thumbnail']").get_attribute(
                    "href")
                logging.debug(f"추출된 영상 URL: {video_link}")

                parsed_url = urlparse(video_link)
                if "shorts" in parsed_url.path:
                    video_id = parsed_url.path.split("/shorts/")[1]
                elif "watch" in parsed_url.path:
                    video_id = parse_qs(parsed_url.query).get("v", [None])[0]
                else:
                    raise ValueError("알 수 없는 URL 형식")

                if not video_id:
                    raise ValueError("video_id 추출 실패")

                embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1"
                logging.debug(f"3번째 쇼츠 영상 임베드 URL: {embed_url}")
                self.webview.setUrl(QUrl(embed_url))
            else:
                logging.warning(f"3번째 쇼츠 영상을 찾을 수 없음: {game_name}")
                self.webview.setUrl(QUrl(search_url))
                QMessageBox.warning(self, "알림", f"'{game_name}'의 쇼츠 영상을 찾을 수 없습니다.")
        except Exception as e:
            logging.error(f"영상 로드 오류: {str(e)}")
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(game_name + ' trailershort')}"
            self.webview.setUrl(QUrl(search_url))
            QMessageBox.critical(self, "오류", f"유튜브 영상을 불러올 수 없습니다: {str(e)}")
        finally:
            if 'driver' in locals():
                driver.quit()
                logging.debug("Selenium 드라이버 종료")

    def on_ref_webview_load_finished(self, success):
        if success:
            logging.debug("기준 게임 WebEngineView 페이지 로드 성공")
            self.ref_webview.page().runJavaScript("document.querySelector('video') ? 'Video found' : 'No video'",
                                                  lambda result: logging.debug(f"기준 WebEngineView 비디오 상태: {result}"))
        else:
            logging.error("기준 게임 WebEngineView 페이지 로드 실패")

    def on_webview_load_finished(self, success):
        if success:
            logging.debug("WebEngineView 페이지 로드 성공")
            self.webview.page().runJavaScript("document.querySelector('video') ? 'Video found' : 'No video'",
                                              lambda result: logging.debug(f"WebEngineView 비디오 상태: {result}"))
        else:
            logging.error("WebEngineView 페이지 로드 실패")
            QMessageBox.warning(self, "알림", "유튜브 영상 로드에 실패했습니다. 네트워크를 확인하세요.")

    def on_play_button_clicked(self):
        try:
            if not self.current_selected_game:
                logging.warning("선택된 게임 없음")
                QMessageBox.warning(self, "경고", "게임을 먼저 선택하세요.")
                return
            game_name = self.current_selected_game
            logging.debug(f"플레이 버튼 클릭: 게임={game_name}")
            url = f"https://store.steampowered.com/search/?term={quote_plus(game_name)}"
            logging.debug(f"Steam URL 열기: {url}")
            webbrowser.open(url)
        except Exception as e:
            logging.error(f"플레이 버튼 오류: {str(e)}")
            QMessageBox.critical(self, "오류", f"Steam 페이지를 열 수 없습니다: {str(e)}")

    def get_sentence_vector(self, tokens, model):
        """Word2Vec 토큰 리스트로 문장 벡터 생성"""
        valid_tokens = [token for token in tokens if token in model.wv]
        if not valid_tokens:
            logging.debug("유효한 Word2Vec 토큰이 없음, 0 벡터 반환")
            return np.zeros(model.vector_size)
        return np.mean([model.wv[token] for token in valid_tokens], axis=0)

    def game_title_recommendation(self, title=None, index=None):
        logging.debug(f"game_title_recommendation 시작: 제목={title}, 인덱스={index}")
        if not self.models_loaded or self.tfidf_matrix is None or self.tfidf_matrix.shape[0] == 0 or \
                self.tfidf_vectorizer is None or self.word2vec_model is None:
            logging.warning("필수 모델이 로드되지 않았습니다.")
            return []

        try:
            # 게임 인덱스 결정
            if index is not None:
                if not (0 <= index < len(self.game_data)):
                    logging.warning(f"유효하지 않은 인덱스: {index}")
                    return []
                game_idx = index
                game_title = self.game_data.iloc[game_idx]['Title']
            else:
                if title is None or title not in self.game_data['Title'].values:
                    logging.warning(f"제목 '{title}'이 데이터에 없습니다.")
                    return []
                game_idx = self.game_data[self.game_data['Title'] == title].index[0]
                game_title = title
            logging.debug(f"선택된 게임: {game_title}, 인덱스: {game_idx}")

            # TF-IDF 기반 코사인 유사도
            tfidf_ref = self.tfidf_matrix[game_idx]
            if tfidf_ref.nnz == 0:
                logging.warning(f"TF-IDF 벡터가 비어 있습니다: {game_title}")
                return []
            tfidf_cosine_sim = cosine_similarity(tfidf_ref, self.tfidf_matrix).flatten()  # 1D 배열 보장
            logging.debug(f"TF-IDF 코사인 유사도 형상: {tfidf_cosine_sim.shape}, 처음 5개 값: {tfidf_cosine_sim[:5]}")

            # Word2Vec 기반 코사인 유사도
            tokens = [desc.split() for desc in self.game_data['Description'].fillna('no description')]
            ref_vector = self.get_sentence_vector(tokens[game_idx], self.word2vec_model)
            if np.all(ref_vector == 0):
                logging.warning(f"Word2Vec 참조 벡터가 0입니다: {game_title}")
                return []
            all_vectors = np.array([self.get_sentence_vector(tok, self.word2vec_model) for tok in tokens])
            w2v_cosine_sim = cosine_similarity([ref_vector], all_vectors).flatten()  # 1D 배열 보장
            logging.debug(f"Word2Vec 코사인 유사도 형상: {w2v_cosine_sim.shape}, 처음 5개 값: {w2v_cosine_sim[:5]}")

            # 유효한 인덱스 필터링
            valid_indices = [
                i for i, (tok, tfidf) in enumerate(zip(tokens, self.tfidf_matrix))
                if any(t in self.word2vec_model.wv for t in tok) and tfidf.nnz > 0
            ]
            if not valid_indices:
                logging.warning("유효한 벡터가 없습니다.")
                return []
            logging.debug(f"유효 인덱스 수: {len(valid_indices)}")

            # 슬라이싱
            tfidf_cosine_sim = tfidf_cosine_sim[valid_indices]
            w2v_cosine_sim = w2v_cosine_sim[valid_indices]
            valid_df = self.game_data.iloc[valid_indices]
            logging.debug(f"슬라이싱 후 TF-IDF 형상: {tfidf_cosine_sim.shape}, Word2Vec 형상: {w2v_cosine_sim.shape}")

            # TF-IDF와 Word2Vec 결합
            combined_sim = 0.5 * tfidf_cosine_sim + 0.5 * w2v_cosine_sim
            logging.debug(f"결합된 유사도 형상: {combined_sim.shape}, 처음 5개 값: {combined_sim[:5]}")

            # 자기 자신 제외 및 상위 100개 추천
            sim_scores = []
            for i, score in enumerate(combined_sim):
                orig_idx = valid_indices[i]
                if orig_idx != game_idx:
                    sim_scores.append((i, float(score)))  # 스칼라로 변환
            if not sim_scores:
                logging.warning("유효한 유사도 점수가 없습니다.")
                return []

            # 상위 100개 선택 (또는 가능한 최대 개수)
            sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)[:10]
            if len(sim_scores) < 5:
                logging.warning(f"상위 추천이 5개 미만입니다: {len(sim_scores)}개")
                game_indices = [valid_indices[score[0]] for score in sim_scores]
            else:
                # 상위 100개 중 무작위 5개 선택
                random_selection = random.sample(sim_scores, 5)
                game_indices = [valid_indices[score[0]] for score in random_selection]

            recommendations = valid_df.iloc[[valid_df.index.get_loc(idx) for idx in game_indices]]['Title'].tolist()
            logging.debug(f"game_title_recommendation 완료: 추천={recommendations}")
            return recommendations
        except Exception as e:
            logging.error(f"게임 추천 오류: {str(e)}")
            return []

    def keyword_recommendation(self, keyword):
        logging.debug(f"keyword_recommendation 시작: 키워드={keyword}")
        if not self.models_loaded or not self.tfidf_matrix or not self.tfidf_vectorizer:
            logging.warning("TF-IDF 모델이 로드되지 않았습니다.")
            return []
        try:
            keyword_vector = self.tfidf_vectorizer.transform([keyword])
            logging.debug(f"키워드 벡터 형상: {keyword_vector.shape}")
            cosine_similarities = linear_kernel(keyword_vector, self.tfidf_matrix).flatten()
            logging.debug(f"코사인 유사도 형상: {cosine_similarities.shape}")

            # 상위 100개 인덱스 선택
            similar_indices = np.argsort(cosine_similarities)[-10:][::-1]
            # 유사도가 0보다 큰 항목 필터링
            valid_indices = [i for i in similar_indices if cosine_similarities[i] > 0 and i < len(self.game_titles)]

            if len(valid_indices) < 5:
                logging.warning(f"유효한 추천이 5개 미만입니다: {len(valid_indices)}개")
                recommendations = [self.game_titles[i] for i in valid_indices]
            else:
                # 상위 100개 중 무작위 5개 선택
                random_indices = random.sample(valid_indices, 5)
                recommendations = [self.game_titles[i] for i in random_indices]

            logging.debug(f"keyword_recommendation 완료: 추천={recommendations}")
            return recommendations
        except Exception as e:
            logging.error(f"키워드 추천 오류: {str(e)}")
            return []


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    main_window = GameRecommendationApp()
    main_window.show()
    sys.exit(app.exec_())
