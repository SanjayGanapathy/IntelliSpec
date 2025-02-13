#Packages and Imports

import sys
import serial
import serial.tools.list_ports
import time
import google.generativeai as genai
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                            QHBoxLayout, QWidget, QLabel, QComboBox, QFrame,
                            QTextEdit, QLineEdit, QSplitter, QMessageBox)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QPalette, QColor, QFont
import qdarktheme
import markdown
from dotenv import load_dotenv
import os
import math

# Load environment variables
load_dotenv()

class SerialThread(QThread):
    data_received = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, port, baudrate=9600):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.serial = None

    def run(self):
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=0.1)
            while self.running:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8').strip()
                    if line:
                        self.data_received.emit(line)
                time.sleep(0.01)  # Prevent CPU hogging
        except Exception as e:
            self.error_occurred.emit(str(e))

    def write(self, data):
        if self.serial and self.serial.is_open:
            try:
                self.serial.write(data)
            except Exception as e:
                self.error_occurred.emit(str(e))

    def stop(self):
        self.running = False
        if self.serial:
            self.serial.close()

class ChatWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.model = None
        self.init_ui()
        if self.api_key:
            self.set_api_key(self.api_key)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                border-radius: 10px;
                padding: 10px;
                color: #ffffff;
            }
        """)
        
        # Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message here...")
        self.input_field.returnPressed.connect(self.send_message)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                border-radius: 15px;
                padding: 10px;
                color: #ffffff;
            }
        """)
        
        # API Key field
        self.api_key_field = QLineEdit()
        self.api_key_field.setPlaceholderText("Enter Gemini API Key...")
        self.api_key_field.setEchoMode(QLineEdit.Password)
        self.api_key_field.textChanged.connect(self.set_api_key)
        self.api_key_field.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                border-radius: 15px;
                padding: 10px;
                color: #ffffff;
            }
        """)
        
        layout.addWidget(QLabel("Gemini Chat Assistant"))
        if not self.api_key:  # Only show API key field if no key in environment
            layout.addWidget(self.api_key_field)
        layout.addWidget(self.chat_display)
        layout.addWidget(self.input_field)

    def set_api_key(self, key):
        if key.strip():
            self.api_key = key.strip()
            genai.configure(api_key=self.api_key)
            try:
                self.model = genai.GenerativeModel('gemini-pro')
                self.append_formatted_message("System", "API Key set successfully! Chat is ready.")
            except Exception as e:
                self.append_formatted_message("Error", str(e))

    def append_formatted_message(self, sender, message):
        html_content = markdown.markdown(message)
        
        if sender == "You":
            color = "#4CAF50"  # Green
        elif sender == "Assistant":
            color = "#2196F3"  # Blue
        elif sender == "System":
            color = "#FFC107"  # Yellow
        else:
            color = "#F44336"  # Red for errors
            
        formatted_html = f'<div style="margin-bottom: 10px;"><span style="color: {color}; font-weight: bold;">{sender}:</span> {html_content}</div>'
        self.chat_display.append(formatted_html)

    def send_message(self):
        if not self.api_key or not self.model:
            self.append_formatted_message("Error", "Please set your Gemini API key first.")
            return
            
        message = self.input_field.text().strip()
        if message:
            self.append_formatted_message("You", message)
            self.input_field.clear()
            
            try:
                response = self.model.generate_content(message)
                self.append_formatted_message("Assistant", response.text)
            except Exception as e:
                self.append_formatted_message("Error", str(e))

class SpectrophotometerUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.serial_thread = None
        self.init_ui()
        
        # Variables for calculations
        self.dark_voltage = 0.110
        self.initial_voltage = None
        self.calibrating = False
        
        # Status update timer for connection monitoring
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_connection_status)
        self.status_timer.start(1000)

    def init_ui(self):
        self.setWindowTitle('IntellispecUI')
        self.setMinimumSize(1200, 800)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side (main content)
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        # Port selection and status
        port_layout = QHBoxLayout()
        port_label = QLabel('Select Port:')
        port_label.setStyleSheet("font-size: 14px;")
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)
        self.port_combo.setStyleSheet("""
            QComboBox {
                background-color: #2d2d2d;
                border-radius: 5px;
                padding: 5px;
                min-height: 30px;
                font-size: 14px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
                margin-right: 8px;
            }
        """)
        self.refresh_ports()
        self.port_combo.currentTextChanged.connect(self.connect_to_port)
        
        refresh_btn = QPushButton('🔄')
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.clicked.connect(self.refresh_ports)
        refresh_btn.setToolTip("Refresh port list")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                border-radius: 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
        """)
        
        self.status_label = QLabel('Not Connected')
        self.status_label.setStyleSheet("""
            QLabel {
                color: #F44336;
                font-size: 14px;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 10px;
                background-color: rgba(244, 67, 54, 0.1);
            }
        """)
        
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(refresh_btn)
        port_layout.addSpacing(20)
        port_layout.addWidget(self.status_label)
        port_layout.addStretch()
        layout.addLayout(port_layout)

        # Measurements Display
        measurements_layout = QHBoxLayout()
        
        # Voltage Display
        self.voltage_frame = QFrame()
        self.voltage_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.voltage_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 15px;
                padding: 20px;
            }
        """)
        voltage_layout = QVBoxLayout(self.voltage_frame)
        self.voltage_label = QLabel('Voltage')
        self.voltage_label.setAlignment(Qt.AlignCenter)
        self.voltage_value = QLabel('0.000 V')
        self.voltage_value.setAlignment(Qt.AlignCenter)
        self.voltage_value.setFont(QFont('Arial', 24))
        voltage_layout.addWidget(self.voltage_label)
        voltage_layout.addWidget(self.voltage_value)
        
        # Absorbance Display
        self.absorbance_frame = QFrame()
        self.absorbance_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.absorbance_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 15px;
                padding: 20px;
            }
        """)
        absorbance_layout = QVBoxLayout(self.absorbance_frame)
        self.absorbance_label = QLabel('Absorbance')
        self.absorbance_label.setAlignment(Qt.AlignCenter)
        self.absorbance_value = QLabel('0.000 A')
        self.absorbance_value.setAlignment(Qt.AlignCenter)
        self.absorbance_value.setFont(QFont('Arial', 24))
        absorbance_layout.addWidget(self.absorbance_label)
        absorbance_layout.addWidget(self.absorbance_value)

        # Transmittance Display
        self.transmittance_frame = QFrame()
        self.transmittance_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.transmittance_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 15px;
                padding: 20px;
            }
        """)
        transmittance_layout = QVBoxLayout(self.transmittance_frame)
        self.transmittance_label = QLabel('Transmittance')
        self.transmittance_label.setAlignment(Qt.AlignCenter)
        self.transmittance_value = QLabel('100.0 %')
        self.transmittance_value.setAlignment(Qt.AlignCenter)
        self.transmittance_value.setFont(QFont('Arial', 24))
        transmittance_layout.addWidget(self.transmittance_label)
        transmittance_layout.addWidget(self.transmittance_value)

        measurements_layout.addWidget(self.voltage_frame)
        measurements_layout.addWidget(self.absorbance_frame)
        measurements_layout.addWidget(self.transmittance_frame)
        layout.addLayout(measurements_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Calibrate Button
        self.calibrate_btn = QPushButton('Calibrate')
        self.calibrate_btn.clicked.connect(self.calibrate)
        self.calibrate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 50px;
                padding: 20px;
                font-size: 18px;
                min-width: 150px;
                min-height: 150px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
        """)
        
        # Measure Button
        self.measure_btn = QPushButton('Measure')
        self.measure_btn.clicked.connect(self.measure)
        self.measure_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 50px;
                padding: 20px;
                font-size: 18px;
                min-width: 150px;
                min-height: 150px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
        """)

        button_layout.addWidget(self.calibrate_btn)
        button_layout.addWidget(self.measure_btn)
        layout.addLayout(button_layout)
        
        # Add left widget to splitter
        splitter.addWidget(left_widget)
        
        # Right side (chat widget)
        self.chat_widget = ChatWidget()
        splitter.addWidget(self.chat_widget)
        
        # Set initial splitter sizes (70% main content, 30% chat)
        splitter.setSizes([700, 300])
        
        main_layout.addWidget(splitter)
        
        # Disable buttons initially
        self.calibrate_btn.setEnabled(False)
        self.measure_btn.setEnabled(False)

    def refresh_ports(self):
        current_port = self.port_combo.currentText()
        self.port_combo.clear()
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo.addItems(ports)
        
        # Try to reselect the previous port
        if current_port in ports:
            self.port_combo.setCurrentText(current_port)

    def connect_to_port(self, port):
        # Stop existing thread if any
        if self.serial_thread:
            self.serial_thread.stop()
            self.serial_thread.wait()
        
        if port:
            try:
                self.serial_thread = SerialThread(port)
                self.serial_thread.data_received.connect(self.handle_serial_data)
                self.serial_thread.error_occurred.connect(self.handle_serial_error)
                self.serial_thread.start()
                
                # Enable buttons
                self.calibrate_btn.setEnabled(True)
                self.measure_btn.setEnabled(True)
                
                self.status_label.setText('Connected')
                self.status_label.setStyleSheet("color: #4CAF50;")  # Green
            except Exception as e:
                self.handle_serial_error(str(e))

    def update_connection_status(self):
        if not self.serial_thread or not self.serial_thread.isRunning():
            self.status_label.setText('Not Connected')
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #F44336;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 5px 10px;
                    border-radius: 10px;
                    background-color: rgba(244, 67, 54, 0.1);
                }
            """)
            self.calibrate_btn.setEnabled(False)
            self.measure_btn.setEnabled(False)

    def handle_serial_data(self, line):
        
        #Process incoming data from the serial port.
        #Updates voltage, absorbance, and transmittance displays.
        # Print raw data for debugging
        print(f"Received raw data: '{line}'")
        
        # Skip empty lines or pure whitespace
        if not line or line.isspace():
            return
            
        try:
            # Handle initial voltage (calibration)
            if "Initial Voltage (Blank):" in line:
                voltage_str = line.split(":")[-1].strip()
                try:
                    voltage = float(voltage_str)
                    self.initial_voltage = voltage  # This is V0
                    self.voltage_value.setText(f"{voltage:.3f} V")
                    # Since this is calibration, set all values to baseline
                    self.absorbance_value.setText("0.000 A")
                    self.transmittance_value.setText("100.0 %")
                except ValueError as e:
                    print(f"Error parsing initial voltage: {e}")
                return
                
            # Handle regular voltage reading
            elif "Voltage:" in line:
                voltage_str = line.split(":")[-1].strip()
                try:
                    voltage = float(voltage_str)  # This is V
                    self.voltage_value.setText(f"{voltage:.3f} V")
                    
                    if self.initial_voltage is not None:
                        # Common values used in calculations
                        V0 = self.initial_voltage
                        V = voltage
                        Vd = 0.110  # dark signal
                        
                        try:
                            numerator = V0 - Vd
                            denominator = V - Vd
                            
                            if denominator <= 0 or numerator <= 0:
                                absorbance = 2.00
                            else:
                                # Calculate absorbance: A = log_10((V0-Vd)/(V-Vd))
                                ratio = numerator / denominator - 0.5
                                if ratio > 100:  # Safety check for very high ratios
                                    absorbance = 2.00

                                else:
                                    absorbance = math.log10(ratio)
                                    if math.isnan(absorbance) or math.isinf(absorbance):
                                        absorbance = 2.00
                        except (ValueError, ZeroDivisionError):
                            absorbance = 2.0
                                    
                        self.absorbance_value.setText(f"{absorbance:.3f} A")
                        
                        # Calculate transmittance
                        if absorbance >= 2.00:
                            transmittance = 0.0
                        else:
                            transmittance = 100 * (10 ** -absorbance)
                        
                        self.transmittance_value.setText(f"{transmittance:.1f} %")
                        
                except ValueError as e:
                    print(f"Error parsing voltage: {e}")
                    
        except Exception as e:
            print(f"Error processing data: {e}")
            print(f"Invalid data received: {line}")

    def handle_serial_error(self, error_msg):
        self.status_label.setText('Error')
        self.status_label.setStyleSheet("""
            QLabel {
                color: #F44336;
                font-size: 14px;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 10px;
                background-color: rgba(244, 67, 54, 0.1);
            }
        """)
        QMessageBox.warning(self, "Serial Error", str(error_msg))
        self.calibrate_btn.setEnabled(False)
        self.measure_btn.setEnabled(False)

    def calibrate(self):
        if self.serial_thread:
            self.calibrating = True
            self.calibrate_btn.setEnabled(False)
            self.measure_btn.setEnabled(False)
            
            # Reset values
            self.initial_voltage = None
            self.voltage_value.setText("0.000 V")
            self.absorbance_value.setText("0.000 A")
            self.transmittance_value.setText("100.0 %")
            
            # Send calibrate command
            print("Starting calibration...")
            self.serial_thread.write(b'calibrate\n')
            QTimer.singleShot(12000, self.finish_calibration)

    def finish_calibration(self):
        self.calibrating = False
        if self.serial_thread and self.serial_thread.isRunning():
            self.calibrate_btn.setEnabled(True)
            self.measure_btn.setEnabled(True)
            if self.initial_voltage is None:
                print("Warning: No initial voltage was set during calibration")

    def measure(self):
        if self.serial_thread:
            self.calibrate_btn.setEnabled(False)
            self.measure_btn.setEnabled(False)
            self.serial_thread.write(b'read\n')
            QTimer.singleShot(7000, self.enable_buttons)

    def enable_buttons(self):
        if self.serial_thread and self.serial_thread.isRunning():
            self.calibrate_btn.setEnabled(True)
            self.measure_btn.setEnabled(True)

    def closeEvent(self, event):
        if self.serial_thread:
            self.serial_thread.stop()
            self.serial_thread.wait()
        event.accept()

def main():
    app = QApplication(sys.argv)
    qdarktheme.setup_theme("dark")
    window = SpectrophotometerUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()