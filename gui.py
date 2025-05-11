import sys
import os
import markdown
import random
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                              QWidget, QGraphicsDropShadowEffect, QTextBrowser)
from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QPixmap


class NotificationDot(QMainWindow):
    def __init__(self, icon_path=None):
        super().__init__()
        
        # Configurazione finestra principale
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Dimensioni e colori
        self.dot_size = 50
        self.normal_color = QColor(50, 150, 250)  # Blu
        self.notification_color = QColor(250, 100, 100)  # Rosso
        self.has_notification = False
        
        # Carica l'icona personalizzata se specificata
        self.custom_icon = None
        if icon_path and os.path.exists(icon_path):
            self.custom_icon = QPixmap(icon_path)
        
        # Posizionamento schermo
        self.setFixedSize(self.dot_size, self.dot_size)
        self.move_to_bottom_right()
        
        # Variabili di stato
        self.dragging = False
        self.drag_position = QPoint()
        self.popup = None
        self.notification_message = ""
        
        # Configurazione iniziale
        self.init_ui()
        
    def init_ui(self):
        """Inizializza l'interfaccia utente"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Effetto ombra
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(2, 2)
        central_widget.setGraphicsEffect(shadow)
        
        # Mostra la finestra
        self.show()
    
    def move_to_bottom_right(self):
        """Posiziona il pallino in basso a destra dello schermo"""
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        x = screen_geometry.width() - self.dot_size - 20
        y = screen_geometry.height() - self.dot_size - 20
        self.move(x, y)
    
    def paintEvent(self, event):
        """Disegna il pallino e, se necessario, l'indicatore di notifica"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Disegna il pallino
        rect = QRect(0, 0, self.dot_size, self.dot_size)
        
        # Bordo del pallino - bordo bianco e sottile
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setBrush(self.notification_color if self.has_notification else self.normal_color)
        painter.drawEllipse(rect)
        
        # Disegna l'icona personalizzata o quella predefinita
        if self.custom_icon:
            # Calcola la dimensione dell'icona
            icon_size = int(self.dot_size * 0.8)
            icon_rect = QRect(
                int((self.dot_size - icon_size) / 2),
                int((self.dot_size - icon_size) / 2),
                icon_size,
                icon_size
            )
            
            # Ridimensiona l'icona
            scaled_icon = self.custom_icon.scaled(
                icon_size, icon_size, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            # Applicazione della maschera circolare
            # Crea una maschera circolare per l'icona
            mask = QPixmap(scaled_icon.size())
            mask.fill(Qt.transparent)
            mask_painter = QPainter(mask)
            mask_painter.setRenderHint(QPainter.Antialiasing)
            mask_painter.setBrush(Qt.black)
            mask_painter.setPen(Qt.NoPen)
            mask_painter.drawEllipse(0, 0, icon_size, icon_size)
            mask_painter.end()
            
            # Applica la maschera
            icon_pixmap = QPixmap(scaled_icon.size())
            icon_pixmap.fill(Qt.transparent)
            icon_painter = QPainter(icon_pixmap)
            icon_painter.setClipRegion(mask.mask())
            icon_painter.drawPixmap(0, 0, scaled_icon)
            icon_painter.end()
            
            # Disegna l'icona circolare
            painter.drawPixmap(icon_rect, icon_pixmap)
        else:
            # Disegna l'icona predefinita (un cerchio bianco)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            icon_size = self.dot_size * 0.4
            icon_rect = QRect(
                int((self.dot_size - icon_size) / 2),
                int((self.dot_size - icon_size) / 2),
                int(icon_size),
                int(icon_size)
            )
            painter.drawEllipse(icon_rect)
        
        # Disegna l'indicatore di notifica se necessario
        if self.has_notification:
            notification_size = 12
            painter.setBrush(QBrush(QColor(255, 50, 50)))  # Rosso vivo
            painter.drawEllipse(
                self.dot_size - notification_size - 3,
                3,
                notification_size,
                notification_size
            )
    
    def mousePressEvent(self, event):
        """Gestisce il click sul pallino"""
        if event.button() == Qt.LeftButton:
            if self.has_notification:
                self.show_notification_popup()
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        """Gestisce il trascinamento del pallino"""
        if event.buttons() & Qt.LeftButton and self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
    
    def mouseReleaseEvent(self, event):
        """Gestisce il rilascio del mouse dopo il click"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
    
    def set_notification(self, message):
        """Imposta lo stato di notifica e memorizza il messaggio"""
        self.has_notification = True
        self.notification_message = message
        self.update()  # Ridisegna il pallino
    
    def clear_notification(self):
        """Rimuove lo stato di notifica"""
        self.has_notification = False
        self.notification_message = ""
        self.update()  # Ridisegna il pallino
    
    def show_notification_popup(self):
        """Mostra il popup con il messaggio di notifica in formato Markdown"""
        if self.popup:
            self.popup.close()
        
        # Crea un nuovo popup
        self.popup = NotificationPopup(self, self.notification_message)
        
        # Ottenere la posizione globale del pallino
        dot_pos = self.mapToGlobal(QPoint(0, 0))
        
        # Calcola posizione orizzontale (alla sinistra del pallino)
        popup_x = max(0, dot_pos.x() - self.popup.width() - 10)  # 10px di spazio
        
        # Posizionamento verticale
        # Il bordo inferiore del popup è allineato con il bordo inferiore del pallino
        # e il popup si estende verso l'alto
        popup_y = dot_pos.y() + self.height() - self.popup.height()
        
        # Verifica se il popup va fuori dallo schermo superiore
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        if popup_y < 0:
            # Se va fuori dallo schermo in alto, lo posiziona in cima allo schermo
            popup_y = 0
        
        # Controllo se il popup va fuori dallo schermo a sinistra
        if popup_x < 0:
            # Posiziona il popup alla destra del pallino
            popup_x = dot_pos.x() + self.width() + 10
        
        self.popup.move(popup_x, popup_y)
        self.popup.show()
        
        # Pulisce la notifica dopo che è stata mostrata
        self.clear_notification()


class NotificationPopup(QWidget):
    def __init__(self, parent, message):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        
        # Configurazione del popup - MODIFICATO: dimensioni aumentate
        self.setMinimumWidth(500)  # Aumentato da 350
        self.setMaximumWidth(650)  # Aumentato da 450
        
        # Layout principale
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)  # Margini aumentati
        self.setLayout(layout)
        
        # Converte Markdown in HTML
        html_content = markdown.markdown(message)
        
        # Browser di testo per visualizzare il contenuto HTML
        text_browser = QTextBrowser()
        text_browser.setHtml(html_content)
        text_browser.setOpenExternalLinks(True)
        text_browser.setMinimumHeight(250)  # MODIFICATO: Altezza minima aumentata da 120
        
        # Stile per il browser di testo
        text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #f8f8f8;
                color: #333;
                font-family: Arial, sans-serif;
                font-size: 15px;  /* Dimensione del testo aumentata */
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;  /* Padding aumentato */
            }
        """)
        
        # Aggiungi il testo al layout
        layout.addWidget(text_browser)
        
        # Stile complessivo del popup
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 2px solid #007bff;
                border-radius: 8px;
            }
        """)
        
        # Aggiunge un'ombra al popup
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)
        
        # Imposta le dimensioni in base al contenuto
        self.adjustSize()
    
    def mousePressEvent(self, event):
        """Chiude il popup quando viene cliccato"""
        self.close()


# Esempio di utilizzo
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Percorso dell'icona (nella stessa cartella del file Python)
    icon_path = "call_assistant_icon.png"  # Nome file icona specificato
    
    # Crea l'icona notifica con l'icona personalizzata
    notification_dot = NotificationDot(icon_path)
    
    # Lista di esempio di notifiche
    notification_messages = [
        """
# Nuova Email
Hai ricevuto una **nuova email** da Mario Rossi.
Oggetto: *Riunione settimanale*
        """,
        
        """
# Promemoria
Oggi hai un **appuntamento** alle 15:30.
- Preparare la presentazione
- Portare i documenti
        """,
        
        """
# Aggiornamento Sistema
È disponibile un nuovo aggiornamento.
[Clicca qui](https://www.example.com) per installarlo.
        """,
        
        """
# Notifica Importante
Il tuo rapporto mensile è pronto per essere revisionato.
        """
    ]
    
    # Timer per notifiche periodiche
    notification_timer = QTimer()
    
    # Funzione per mostrare notifiche periodiche
    def show_periodic_notification():
        if not notification_dot.has_notification:
            message = random.choice(notification_messages)
            notification_dot.set_notification(message)
    
    # Collega il timer alla funzione di notifica
    notification_timer.timeout.connect(show_periodic_notification)
    
    # Avvia il timer: mostra una notifica ogni 15 secondi
    notification_timer.start(15000)
    
    # Mostra la prima notifica dopo 3 secondi
    QTimer.singleShot(3000, show_periodic_notification)
    
    # Gestisce sia versioni vecchie che nuove di PySide6
    try:
        sys.exit(app.exec())
    except AttributeError:
        sys.exit(app.exec_())