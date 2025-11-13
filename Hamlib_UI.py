"""
Hamlib UI - A Hamlib GUI for managing installations and running rigctld, rotctld, and ampctld.

Author: Bruno, CS8ABG
License: MIT License

Features:
    - Download and install the latest Hamlib release from GitHub.
    - List supported radios, rotors, and amplifiers.
    - Configure and run rigctld, rotctld, and ampctld with a user-friendly interface.
    - Show real-time output from the running processes.
    
MIT License:
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
"""

import sys
import os
import shutil
import zipfile
import threading
import subprocess
import re
from pathlib import Path
import requests
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSettings
import serial.tools.list_ports

HAMLIB_DIR = Path.cwd() / "hamlib"
BIN_DIR = HAMLIB_DIR / "bin"
GITHUB_RELEASES_API = "https://api.github.com/repos/Hamlib/Hamlib/releases"

def get_icon_path(filename="hamlib_ui.ico"):
    if getattr(sys, 'frozen', False):
        # Running from PyInstaller exe
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, filename)
def ensure_hamlib_dir():
    HAMLIB_DIR.mkdir(exist_ok=True)
def download_latest_release(progress_callback=None):
    try:
        r = requests.get(GITHUB_RELEASES_API + "/latest", timeout=15)
        r.raise_for_status()
        latest = r.json()
        asset_url, asset_name = None, None
        for a in latest.get("assets", []):
            name = a.get("name","").lower()
            if name.endswith(".zip") and "w64" in name:
                asset_url = a["browser_download_url"]
                asset_name = a["name"]
                break
        if not asset_url:
            for a in latest.get("assets", []):
                name = a.get("name","").lower()
                if name.endswith(".zip"):
                    asset_url = a["browser_download_url"]
                    asset_name = a["name"]
                    break
        if not asset_url:
            asset_url = latest.get('zipball_url')
            asset_name = f"hamlib-{latest.get('tag_name','latest')}.zip"
        ensure_hamlib_dir()
        dest = HAMLIB_DIR / asset_name
        with requests.get(asset_url, stream=True, timeout=60) as rr:
            rr.raise_for_status()
            total = int(rr.headers.get('Content-Length', 0))
            downloaded = 0
            with open(dest, 'wb') as f:
                for chunk in rr.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total:
                            progress_callback(downloaded / total)
        for item in HAMLIB_DIR.iterdir():
            if item == dest: continue
            if item.is_dir(): shutil.rmtree(item)
            else: item.unlink()
        with zipfile.ZipFile(dest, 'r') as z:
            z.extractall(HAMLIB_DIR)
        return True, f"Installed release {latest.get('tag_name','unknown')}"
    except Exception as e:
        return False, f"Download/extract failed: {e}"
def get_latest_bin_dir():
    if not HAMLIB_DIR.exists(): return None
    candidates = []
    for sub in HAMLIB_DIR.iterdir():
        if (sub/"bin"/"rigctld.exe").exists():
            candidates.append(sub)
    if candidates:
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        return latest/"bin"
    if (HAMLIB_DIR/"bin"/"rigctld.exe").exists():
        return HAMLIB_DIR/"bin"
    return None
def find_exe(name):
    """Find rigctld.exe, rotctld.exe, ampctld.exe"""
    bin_dir = get_latest_bin_dir()
    if bin_dir and (bin_dir/name).exists():
        return bin_dir/name
    for root, dirs, files in os.walk(HAMLIB_DIR):
        if name in files:
            return Path(root)/name
    return None
def get_installed_version():
    rig_path = find_exe("rigctld.exe")
    if not rig_path: return None
    try:
        p = subprocess.run([str(rig_path), '--version'], capture_output=True, text=True, timeout=5)
        out = p.stdout.strip() or p.stderr.strip()
        if not out: return 'unknown'
        parts = out.split()
        if len(parts)>=4:
            return f"{parts[1]} {parts[2]} {parts[-1]}"
        return out.splitlines()[0]
    except:
        return 'unknown'
def clean_name(text):
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\b(v|ver|rev)\s*\d+.*', '', text, flags=re.I)
    return text.strip()
def parse_rig_list(text):
    lines = text.splitlines()
    rigs = []
    start = 0
    for i, line in enumerate(lines):
        if re.search(r'Rig\s*#', line):
            start = i + 1
            break
    for line in lines[start:]:
        if not line.strip():
            continue
        parts = re.split(r'\s{2,}', line.strip())
        if len(parts) < 3:
            continue
        try:
            rid = int(parts[0])
        except ValueError:
            continue
        mfg = parts[1].strip()
        model = parts[2].strip()
        label = f"{mfg} - {model}"
        rigs.append({'id': rid, 'mfg': mfg, 'model': model, 'label': label})
    return rigs
def parse_device_list(text):
    lines = text.splitlines()
    devices = []
    start = 0
    for i, line in enumerate(lines):
        if re.search(r'Rotator|Amplifier|Device|Model', line, re.I):
            start = i + 1
            break
    for line in lines[start:]:
        if not line.strip():
            continue
        parts = re.split(r'\s{2,}', line.strip())
        if len(parts) < 3:
            continue
        try:
            did = int(parts[0])
        except ValueError:
            continue
        mfg = parts[1].strip()
        model = parts[2].strip()
        label = f"{mfg} - {model}"
        devices.append({'id': did, 'mfg': mfg, 'model': model, 'label': label})
    return devices
def list_serial_ports():
    return [p.device for p in serial.tools.list_ports.comports()]
class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    progress = QtCore.pyqtSignal(float)
    message = QtCore.pyqtSignal(str)
class DownloadThread(QtCore.QThread):
    signals = WorkerSignals()
    def run(self):
        def cb(progress): self.signals.progress.emit(progress)
        ok,msg=download_latest_release(progress_callback=cb)
        self.signals.message.emit(msg)
        self.signals.finished.emit()
class RigctlListThread(QtCore.QThread):
    result = QtCore.pyqtSignal(list)
    signals = WorkerSignals()
    def run(self):
        rig_path = find_exe("rigctld.exe")
        if not rig_path:
            self.result.emit([])
            self.signals.message.emit("rigctld.exe not found")
            return
        try:
            p = subprocess.run([str(rig_path), '--list'], capture_output=True, text=True, timeout=20)
            rigs = parse_rig_list(p.stdout + p.stderr)
            self.result.emit(rigs)
        except Exception as e:
            self.signals.message.emit(f"Failed to run rigctld --list: {e}")
            self.result.emit([])
class RotctlListThread(QtCore.QThread):
    result = QtCore.pyqtSignal(list)
    signals = WorkerSignals()
    def run(self):
        exe = find_exe("rotctld.exe")
        if not exe:
            self.result.emit([])
            self.signals.message.emit("rotctld.exe not found")
            return
        try:
            p = subprocess.run([str(exe), '--list'], capture_output=True, text=True, timeout=10)
            devices = parse_device_list(p.stdout)
            self.result.emit(devices)
        except Exception as e:
            self.signals.message.emit(f"rotctld --list failed: {e}")
            self.result.emit([])
class AmpctlListThread(QtCore.QThread):
    result = QtCore.pyqtSignal(list)
    signals = WorkerSignals()
    def run(self):
        exe = find_exe("ampctld.exe")
        if not exe:
            self.result.emit([])
            self.signals.message.emit("ampctld.exe not found")
            return
        try:
            p = subprocess.run([str(exe), '--list'], capture_output=True, text=True, timeout=10)
            devices = parse_device_list(p.stdout)
            self.result.emit(devices)
        except Exception as e:
            self.signals.message.emit(f"ampctld --list failed: {e}")
            self.result.emit([])
class HamlibRunner(QtCore.QObject):
    started = QtCore.pyqtSignal()
    stopped = QtCore.pyqtSignal()
    output = QtCore.pyqtSignal(str)
    def __init__(self, exe_name):
        super().__init__()
        self.process=None
        self.exe_name=exe_name
    def start(self,args):
        if self.process: self.output.emit("Already running"); return
        exe_path = find_exe(self.exe_name)
        if not exe_path: self.output.emit(f"{self.exe_name} not found!"); return
        try:
            self.process=subprocess.Popen([str(exe_path)]+args, cwd=str(exe_path.parent),
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.started.emit()
            threading.Thread(target=self._reader_thread, daemon=True).start()
        except Exception as e:
            self.output.emit(f"Failed to start: {e}"); self.process=None
    def _reader_thread(self):
        try:
            assert self.process
            for line in self.process.stdout:
                self.output.emit(line.rstrip('\n'))
            self.process.wait()
        finally:
            self.process=None
            self.stopped.emit()
    def stop(self):
        if self.process:
            try: self.process.terminate()
            except: pass
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("hamlib UI")
        self.setWindowIcon(QIcon("hamlib_ui.ico"))
        self.setFixedSize(380, 241)
        self.radio_runner = HamlibRunner("rigctld.exe")
        self.rotor_runner = HamlibRunner("rotctld.exe")
        self.amp_runner = HamlibRunner("ampctld.exe")
        self._init_ui()
        self._connect_signals()
        self.refresh_installed_version()
        self.refresh_serial_ports()
        self.load_rig_list()
        self.load_rotor_amp_list()
        self.settings = QSettings("HamlibUI", "HamlibUIApp")
        self.load_settings()
    def _init_ui(self):
        w = QtWidgets.QWidget(); self.setCentralWidget(w)
        main_layout = QtWidgets.QVBoxLayout(w)
        self.tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(self.tabs)
        self._init_radio_tab()
        self._init_rotor_tab()
        self._init_amp_tab()
        self.show_output_checkbox = QtWidgets.QCheckBox("Show Output")
        self.show_output_checkbox.setChecked(False)
        main_layout.addWidget(self.show_output_checkbox, alignment=QtCore.Qt.AlignRight)
        self.output_text = QtWidgets.QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setVisible(False)
        main_layout.addWidget(self.output_text)
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)
        self.installed_label = QtWidgets.QLabel("Installed: (none)")
        self.status_bar.addPermanentWidget(self.installed_label)
        self.download_button = QtWidgets.QPushButton("Download latest release")
        self.status_bar.addWidget(self.download_button)
    def load_settings(self):
        radio_id = self.settings.value("radio_id", "")
        rotor_id = self.settings.value("rotor_id", "")
        amp_id = self.settings.value("amp_id", "")
        self.serial_combo.setCurrentText(self.settings.value("radio_serial", ""))
        self.baud_combo.setCurrentText(self.settings.value("radio_baud", "9600"))
        self.civ_edit.setText(self.settings.value("civ_address", "00h"))
        self.ptt_checkbox.setChecked(self.settings.value("ptt_enabled", False, type=bool))
        self.ptt_port_combo.setCurrentText(self.settings.value("ptt_port", ""))
        self.ptt_type_combo.setCurrentText(self.settings.value("ptt_type", "RTS"))
        self.tcp_spin.setValue(int(self.settings.value("radio_tcp", 4532)))
        self.rot_serial_combo.setCurrentText(self.settings.value("rotor_serial", ""))
        self.rot_baud_combo.setCurrentText(self.settings.value("rotor_baud", "9600"))
        self.rot_port_spin.setValue(int(self.settings.value("rotor_tcp", 4533)))
        self.amp_serial_combo.setCurrentText(self.settings.value("amp_serial", ""))
        self.amp_baud_combo.setCurrentText(self.settings.value("amp_baud", "9600"))
        self.amp_port_spin.setValue(int(self.settings.value("amp_tcp", 4534)))
        self.show_output_checkbox.setChecked(self.settings.value("show_output", False, type=bool))
        QtCore.QTimer.singleShot(500, self.restore_selected_items)
    def restore_selected_items(self):
        for combo, id_value in [(self.radio_combo, self.settings.value("radio_id", "")),
                                (self.rot_combo, self.settings.value("rotor_id", "")),
                                (self.amp_combo, self.settings.value("amp_id", ""))]:
            for i in range(combo.count()):
                data = combo.itemData(i)
                if data and str(data.get("id","")) == str(id_value):
                    combo.setCurrentIndex(i)
                    break
    def _init_radio_tab(self):
        tab=QtWidgets.QWidget()
        layout=QtWidgets.QVBoxLayout(tab)
        row1=QtWidgets.QHBoxLayout(); row1.addWidget(QtWidgets.QLabel("Radio:"))
        self.radio_combo=QtWidgets.QComboBox(); self.radio_combo.setFixedWidth(220)
        row1.addWidget(self.radio_combo, stretch=2)
        self.civ_label=QtWidgets.QLabel("CI-V:")
        self.civ_edit=QtWidgets.QLineEdit(); self.civ_edit.setPlaceholderText("00h"); self.civ_edit.setFixedWidth(40)
        self.civ_edit.setEnabled(False)
        row1.addWidget(self.civ_label); row1.addWidget(self.civ_edit)
        layout.addLayout(row1)
        row2=QtWidgets.QHBoxLayout(); row2.addWidget(QtWidgets.QLabel("Serial Port:"))
        self.serial_combo=QtWidgets.QComboBox(); row2.addWidget(self.serial_combo)
        row2.addWidget(QtWidgets.QLabel("Baud Rate:"))
        self.baud_combo=QtWidgets.QComboBox(); self.baud_combo.addItems(['300','1200','2400','4800','9600','19200','38400','57600','115200'])
        row2.addWidget(self.baud_combo)
        layout.addLayout(row2)
        row3=QtWidgets.QHBoxLayout()
        self.ptt_checkbox=QtWidgets.QCheckBox("External PTT"); row3.addWidget(self.ptt_checkbox)
        self.ptt_port_label=QtWidgets.QLabel("PTT Port:"); self.ptt_port_combo=QtWidgets.QComboBox()
        self.ptt_type_label=QtWidgets.QLabel("PTT Type:"); self.ptt_type_combo=QtWidgets.QComboBox(); self.ptt_type_combo.addItems(['RTS','DTR'])
        for w in [self.ptt_port_label,self.ptt_port_combo,self.ptt_type_label,self.ptt_type_combo]: w.setEnabled(False)
        for w in [self.ptt_port_label,self.ptt_port_combo,self.ptt_type_label,self.ptt_type_combo]: row3.addWidget(w)
        layout.addLayout(row3)
        row4=QtWidgets.QHBoxLayout(); row4.addWidget(QtWidgets.QLabel("TCP Port:"))
        self.tcp_spin=QtWidgets.QSpinBox(); self.tcp_spin.setRange(1,65535); self.tcp_spin.setValue(4532)
        row4.addWidget(self.tcp_spin); row4.addStretch(); layout.addLayout(row4)
        row5=QtWidgets.QHBoxLayout()
        self.connect_button=QtWidgets.QPushButton("Connect"); self.stop_button=QtWidgets.QPushButton("Stop")
        self.connect_button.setEnabled(True); self.stop_button.setEnabled(False)
        row5.addWidget(self.connect_button); row5.addWidget(self.stop_button); layout.addLayout(row5)
        self.tabs.addTab(tab,"Radio")
    def _init_rotor_tab(self):
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab)
        row1 = QtWidgets.QHBoxLayout(); row1.addWidget(QtWidgets.QLabel("Rotor:"))
        self.rot_combo = QtWidgets.QComboBox(); self.rot_combo.setFixedWidth(300) 
        row1.addWidget(self.rot_combo)
        layout.addLayout(row1)
        row2 = QtWidgets.QHBoxLayout(); row2.addWidget(QtWidgets.QLabel("Serial Port:"))
        self.rot_serial_combo = QtWidgets.QComboBox(); row2.addWidget(self.rot_serial_combo)
        row2.addWidget(QtWidgets.QLabel("Baud Rate:"))
        self.rot_baud_combo = QtWidgets.QComboBox()
        self.rot_baud_combo.addItems(['300','1200','2400','4800','9600','19200','38400','57600','115200'])
        row2.addWidget(self.rot_baud_combo); layout.addLayout(row2)
        row3 = QtWidgets.QHBoxLayout(); row3.addWidget(QtWidgets.QLabel("TCP Port:"))
        self.rot_port_spin = QtWidgets.QSpinBox(); self.rot_port_spin.setRange(1,65535); self.rot_port_spin.setValue(4533)
        row3.addWidget(self.rot_port_spin); row3.addStretch(); layout.addLayout(row3)
        row4 = QtWidgets.QHBoxLayout()
        self.rot_connect = QtWidgets.QPushButton("Connect"); self.rot_stop = QtWidgets.QPushButton("Stop")
        self.rot_connect.setEnabled(True); self.rot_stop.setEnabled(False)
        row4.addWidget(self.rot_connect); row4.addWidget(self.rot_stop); layout.addLayout(row4)
        self.tabs.addTab(tab,"Rotor")
    def _init_amp_tab(self):
        tab = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(tab)
        row1 = QtWidgets.QHBoxLayout(); row1.addWidget(QtWidgets.QLabel("Amplifier:"))
        self.amp_combo = QtWidgets.QComboBox(); self.amp_combo.setFixedWidth(285)
        row1.addWidget(self.amp_combo); layout.addLayout(row1)
        row2 = QtWidgets.QHBoxLayout(); row2.addWidget(QtWidgets.QLabel("Serial Port:"))
        self.amp_serial_combo = QtWidgets.QComboBox(); row2.addWidget(self.amp_serial_combo)
        row2.addWidget(QtWidgets.QLabel("Baud Rate:"))
        self.amp_baud_combo = QtWidgets.QComboBox()
        self.amp_baud_combo.addItems(['300','1200','2400','4800','9600','19200','38400','57600','115200'])
        row2.addWidget(self.amp_baud_combo); layout.addLayout(row2)
        row3 = QtWidgets.QHBoxLayout(); row3.addWidget(QtWidgets.QLabel("TCP Port:"))
        self.amp_port_spin = QtWidgets.QSpinBox(); self.amp_port_spin.setRange(1,65535); self.amp_port_spin.setValue(4534)
        row3.addWidget(self.amp_port_spin); row3.addStretch(); layout.addLayout(row3)
        row4 = QtWidgets.QHBoxLayout()
        self.amp_connect = QtWidgets.QPushButton("Connect"); self.amp_stop = QtWidgets.QPushButton("Stop")
        self.amp_connect.setEnabled(True); self.amp_stop.setEnabled(False)
        row4.addWidget(self.amp_connect); row4.addWidget(self.amp_stop); layout.addLayout(row4)
        self.tabs.addTab(tab,"Amplifier")
    def _connect_signals(self):
        self.download_button.clicked.connect(self._on_download_clicked)
        self.radio_combo.currentIndexChanged.connect(self._on_radio_changed)
        self.ptt_checkbox.stateChanged.connect(self._on_ptt_toggled)
        self.connect_button.clicked.connect(lambda: self._start_runner(self.radio_runner, "radio"))
        self.stop_button.clicked.connect(lambda: self._stop_runner(self.radio_runner, "radio"))
        self.rot_connect.clicked.connect(lambda: self._start_runner(self.rotor_runner, "rotor"))
        self.rot_stop.clicked.connect(lambda: self._stop_runner(self.rotor_runner, "rotor"))
        self.amp_connect.clicked.connect(lambda: self._start_runner(self.amp_runner, "amp"))
        self.amp_stop.clicked.connect(lambda: self._stop_runner(self.amp_runner, "amp"))
        for r in [self.radio_runner, self.rotor_runner, self.amp_runner]:
            r.output.connect(self._append_output)
            r.started.connect(lambda r=r: self._on_runner_started(r))
            r.stopped.connect(lambda r=r: self._on_runner_stopped(r))
        self.show_output_checkbox.stateChanged.connect(self._on_show_output_toggled)
    def _start_runner(self, runner, tab):
        args=[]
        if tab=="radio":
            idx = self.radio_combo.currentIndex()
            data = self.radio_combo.itemData(idx)
            if not data: 
                QtWidgets.QMessageBox.warning(self,"No radio","Select radio")
                return
            args = [f"--model={data['id']}"]
            device = self.serial_combo.currentText()
            if device:
                args.append(f"--rig-file={device}")
            if "icom" in data.get("mfg","").lower():
                civ = self.civ_edit.text().strip()
                if civ:
                    args.append(f"--civaddr={civ}")
            if self.ptt_checkbox.isChecked():
                args.append(f"--ptt-file={self.ptt_port_combo.currentText()}")
                args.append(f"--ptt-type={self.ptt_type_combo.currentText()}")
            baud = self.baud_combo.currentText()
            if baud:
                args.append(f"--serial-speed={baud}")
            port = self.tcp_spin.value()
            args.append(f"--port={port}")
        elif tab=="rotor":
            device=self.rot_serial_combo.currentText(); args.append(f"--rot-file={device}" if device else "")
            baud=self.rot_baud_combo.currentText(); args.append(f"--serial-speed={baud}" if baud else "")
            args.append(f"--port={self.rot_port_spin.value()}")
        elif tab=="amp":
            device=self.amp_serial_combo.currentText(); args.append(f"--amp-file={device}" if device else "")
            baud=self.amp_baud_combo.currentText(); args.append(f"--serial-speed={baud}" if baud else "")
            args.append(f"--port={self.amp_port_spin.value()}")
        args = [a for a in args if a]; args.append("-vvvv")
        self._append_output(f"Starting {tab} with: {' '.join(args)}")
        runner.start(args)
    def _stop_runner(self, runner, tab):
        runner.stop()
        self._append_output(f"{tab.capitalize()} stopped")
    def _on_runner_started(self, runner):
        if runner==self.radio_runner: self.connect_button.setEnabled(False); self.stop_button.setEnabled(True)
        elif runner==self.rotor_runner: self.rot_connect.setEnabled(False); self.rot_stop.setEnabled(True)
        elif runner==self.amp_runner: self.amp_connect.setEnabled(False); self.amp_stop.setEnabled(True)
    def _on_runner_stopped(self, runner):
        if runner==self.radio_runner: self.connect_button.setEnabled(True); self.stop_button.setEnabled(False)
        elif runner==self.rotor_runner: self.rot_connect.setEnabled(True); self.rot_stop.setEnabled(False)
        elif runner==self.amp_runner: self.amp_connect.setEnabled(True); self.amp_stop.setEnabled(False)
    def _append_output(self,text): self.output_text.append(text)
    def _on_show_output_toggled(self, state):
        show = state == QtCore.Qt.Checked
        self.output_text.setVisible(show)
        self.setFixedSize(380, 400 if show else 241)
    def refresh_installed_version(self):
        v=get_installed_version(); self.installed_label.setText(f"Installed: {v or '(none)'}")
    def refresh_serial_ports(self):
        ports=list_serial_ports()
        for combo in [self.serial_combo,self.ptt_port_combo,self.rot_serial_combo,self.amp_serial_combo]:
            combo.clear(); combo.addItems(ports)
    def load_rig_list(self):
        self.rig_thread=RigctlListThread()
        self.rig_thread.result.connect(self._on_rig_list_result)
        self.rig_thread.start()
    def _on_rig_list_result(self, rigs):
        self.radio_combo.clear()
        for r in rigs:
            self.radio_combo.addItem(r['label'], r)
    def load_rotor_amp_list(self):
        self.rot_thread = RotctlListThread()
        self.rot_thread.result.connect(self._on_rot_list_result)
        self.rot_thread.start()
        self.amp_thread = AmpctlListThread()
        self.amp_thread.result.connect(self._on_amp_list_result)
        self.amp_thread.start()
    def _on_rot_list_result(self, devices):
        self.rot_combo.clear()
        for d in devices:
            self.rot_combo.addItem(d['label'], d)
    def _on_amp_list_result(self, devices):
        self.amp_combo.clear()
        for d in devices:
            self.amp_combo.addItem(d['label'], d)
    def _on_radio_changed(self,idx):
        data=self.radio_combo.itemData(idx)
        self.civ_edit.setEnabled("icom" in (data.get("mfg","").lower()) if data else False)
        self.connect_button.setEnabled(bool(data))
    def _on_ptt_toggled(self,state):
        en=(state==QtCore.Qt.Checked)
        for w in [self.ptt_port_label,self.ptt_port_combo,self.ptt_type_label,self.ptt_type_combo]:
            w.setEnabled(en)
    def _on_download_clicked(self):
        self.progress_dialog=QtWidgets.QProgressDialog("Downloading Hamlib...","Cancel",0,100,self)
        self.progress_dialog.setWindowModality(QtCore.Qt.ApplicationModal); self.progress_dialog.show()
        self.download_button.setEnabled(False)
        self.dl_thread=DownloadThread()
        self.dl_thread.signals.progress.connect(lambda p:self.progress_dialog.setValue(int(p*100)))
        self.dl_thread.signals.message.connect(self._append_output)
        self.dl_thread.signals.finished.connect(self._on_download_finished)
        self.dl_thread.start()
    def _on_download_finished(self):
        self.progress_dialog.close(); self.download_button.setEnabled(True)
        self.refresh_installed_version()
        self.load_rig_list()
        self.load_rotor_amp_list()
    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)
    def save_settings(self):
        idx = self.radio_combo.currentIndex()
        data = self.radio_combo.itemData(idx)
        self.settings.setValue("radio_id", data['id'] if data else "")
        self.settings.setValue("radio_serial", self.serial_combo.currentText())
        self.settings.setValue("radio_baud", self.baud_combo.currentText())
        self.settings.setValue("civ_address", self.civ_edit.text())
        self.settings.setValue("ptt_enabled", self.ptt_checkbox.isChecked())
        self.settings.setValue("ptt_port", self.ptt_port_combo.currentText())
        self.settings.setValue("ptt_type", self.ptt_type_combo.currentText())
        self.settings.setValue("radio_tcp", self.tcp_spin.value())
        idx = self.rot_combo.currentIndex()
        data = self.rot_combo.itemData(idx)
        self.settings.setValue("rotor_id", data['id'] if data else "")
        self.settings.setValue("rotor_serial", self.rot_serial_combo.currentText())
        self.settings.setValue("rotor_baud", self.rot_baud_combo.currentText())
        self.settings.setValue("rotor_tcp", self.rot_port_spin.value())
        idx = self.amp_combo.currentIndex()
        data = self.amp_combo.itemData(idx)
        self.settings.setValue("amp_id", data['id'] if data else "")
        self.settings.setValue("amp_serial", self.amp_serial_combo.currentText())
        self.settings.setValue("amp_baud", self.amp_baud_combo.currentText())
        self.settings.setValue("amp_tcp", self.amp_port_spin.value())
        self.settings.setValue("show_output", self.show_output_checkbox.isChecked())
def main():
    app=QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QIcon("hamlib_ui.ico"))
    win=MainWindow()
    win.setWindowIcon(QIcon("hamlib_ui.ico"))
    win.show()
    sys.exit(app.exec_())
if __name__=="__main__":
    main()
