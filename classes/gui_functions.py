from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QFileDialog
import sys
from PyQt5.QtGui import QWheelEvent
from PyQt5 import QtGui
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPixmap,QIcon
from PyQt5.QtCore import Qt, QTimer, PYQT_VERSION_STR
from PyQt5 import QtWidgets, QtGui, QtCore
import cv2
import os
from os.path import expanduser
import openpyxl 
import pandas as pd
from datetime import datetime
import sys
from PyQt5.QtWidgets import QApplication
import numpy as np
import cv2
import matplotlib.pyplot as plt 
import time
import platform
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame



from classes.gui_widgets import Ui_MainWindow

from classes.arduino_class import ArduinoHandler
from classes.joystick_class import Mac_Controller,Linux_Controller,Windows_Controller
from classes.simulation_class import HelmholtzSimulator
from classes.loop_class import Looping_Thread
from classes.acoustic_class import AcousticClass
from classes.halleffect_class import HallEffect




class MainWindow(QtWidgets.QMainWindow):
    positionChanged = QtCore.pyqtSignal(QtCore.QPoint)

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent=parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        #create folder in homerdiractory of user
        if "Windows" in platform.platform():
            home_dir = expanduser("C:")
            new_dir_name = "Tracking Data"
            desktop_path = os.path.join(home_dir, "Microrobots")
            self.new_dir_path = os.path.join(desktop_path, new_dir_name)
            if not os.path.exists(self.new_dir_path):
                os.makedirs(self.new_dir_path)
        else:
            home_dir = expanduser("~")
            new_dir_name = "Tracking Data"
            desktop_path = os.path.join(home_dir, "Desktop")
            self.new_dir_path = os.path.join(desktop_path, new_dir_name)
            if not os.path.exists(self.new_dir_path):
                os.makedirs(self.new_dir_path)


        self.save_status = False
        self.output_workbook = None
        
        
        

        self.acoustic_frequency = 0
        self.gradient_status = 0
        self.magnetic_field_list = []
        
        self.actions = [0,0,0,0,0,0,0,0,0,0,0,0,0]
        self.Bx, self.By, self.Bz = 0,0,0
        self.Mx, self.My, self.Mz = 0,0,0
        self.alpha, self.gamma, self.psi, self.freq = 0,0,0,0
        self.sensorBx, self.sensorBy, self.sensorBz = 0,0,0
        self.field_magnitude = 100

        #control tab functions
        self.joystick_status = False
        self.manual_status = False


        #connect to arduino
        if "mac" in platform.platform():
            self.tbprint("Detected OS: macos")
            PORT = "/dev/cu.usbmodem11401"
            self.controller_actions = Mac_Controller()
        elif "Linux" in platform.platform():
            self.tbprint("Detected OS: Linux")
            PORT = "/dev/ttyACM0"
            self.controller_actions = Linux_Controller()
        elif "Windows" in platform.platform():
            self.tbprint("Detected OS:  Windows")
            PORT = "COM4"
            self.controller_actions = Windows_Controller()
        else:
            self.tbprint("undetected operating system")
            PORT = None
        
        self.arduino = ArduinoHandler(self.tbprint)
        self.arduino.connect(PORT)
        
        
        #define, simulator class, pojection class, and acoustic class
        self.simulator = HelmholtzSimulator(self.ui.magneticfieldsimlabel, width=310, height=310, dpi=200)
        self.simulator.start()
        self.acoustic_module = AcousticClass()
        self.halleffect = HallEffect(self)
        self.halleffect.sensor_signal.connect(self.update_halleffect_sensor)
        self.halleffect.start()
        
        #start looping
        self.loop = Looping_Thread(self)
        self.loop.actions_signal.connect(self.update_actions)
        self.loop.start()
        
        pygame.init()
        if pygame.joystick.get_count() == 0:
            self.tbprint("No Joystick Connected...")
            
        else:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.tbprint("Connected to: "+str(self.joystick.get_name()))
        
        self.ui.gradient_status_checkbox.toggled.connect(self.gradientcommand)
        self.ui.savedatabutton.clicked.connect(self.savedata)
        self.ui.magneticfrequencydial.valueChanged.connect(self.get_slider_vals)
        self.ui.gammadial.valueChanged.connect(self.get_slider_vals)
        self.ui.psidial.valueChanged.connect(self.get_slider_vals)
        self.ui.applyacousticbutton.clicked.connect(self.apply_acoustic)
        self.ui.acousticfreq_spinBox.valueChanged.connect(self.get_acoustic_frequency)
        self.ui.alphaspinBox.valueChanged.connect(self.spinbox_alphachanged)
        self.ui.alphadial.valueChanged.connect(self.dial_alphachanged)
        self.ui.resetdefaultbutton.clicked.connect(self.resetparams)
        #self.ui.simulationbutton.clicked.connect(self.toggle_simulation)

        self.ui.joystickbutton.clicked.connect(self.toggle_joystick_status)
        self.ui.manualapplybutton.clicked.connect(self.get_manual_bfieldbuttons)
        self.ui.manualfieldBx.valueChanged.connect(self.get_slider_vals)
        self.ui.manualfieldBy.valueChanged.connect(self.get_slider_vals)
        self.ui.manualfieldBz.valueChanged.connect(self.get_slider_vals)
        self.ui.import_excel_actions.clicked.connect(self.read_excel_actions)
        self.ui.apply_actions.clicked.connect(self.apply_excel_actions)

        self.excel_file_name = None
        self.excel_actions_df = None
        self.excel_actions_status = False
     

    def spinbox_alphachanged(self):
        self.ui.alphadial.setValue(self.ui.alphaspinBox.value())
    
    def dial_alphachanged(self):
        self.ui.alphaspinBox.setValue(self.ui.alphadial.value())

    def gradientcommand(self):
        self.gradient_status = int(self.ui.gradient_status_checkbox.isChecked())
    

    def read_excel_actions(self):
        options = QFileDialog.Options()
        self.excel_file_name, _ = QFileDialog.getOpenFileName(self, "Open Excel File", "", "Excel Files (*.xlsx *.xls)", options=options)
        if self.excel_file_name:
            self.excel_actions_df = pd.read_excel(self.excel_file_name)
            
        
    def apply_excel_actions(self):
        if self.ui.apply_actions.isChecked():
            self.excel_actions_status = True
            self.actions_counter = 0
            self.ui.apply_actions.setText("Stop")
        else:
            self.excel_actions_status = False
            self.ui.apply_actions.setText("Apply")
            self.apply_actions(False)




    def update_actions(self, actions):
            
        if self.joystick_status == True:
            type, self.Bx, self.By, self.Bz, self.alpha, self.gamma, self.freq, self.psi, _ = self.controller_actions.run(self.joystick)
            self.psi = np.radians(self.ui.psidial.value())
            
            if type == 1:
                self.gamma = np.radians(180)
                self.freq = self.ui.magneticfrequencydial.value()
            
            elif type == 2:
                self.gamma = np.radians(0)
                self.freq = self.ui.magneticfrequencydial.value()
            
            else:
                self.gamma = np.radians(self.ui.gammadial.value())
                if self.freq != 0:
                    self.freq = self.ui.magneticfrequencydial.value()
        
        elif self.manual_status == True:
            self.Bx = self.ui.manualfieldBx.value()/100
            self.By = self.ui.manualfieldBy.value()/100
            self.Bz = self.ui.manualfieldBz.value()/100
            
            self.freq = self.ui.magneticfrequencydial.value()
            self.gamma = np.radians(self.ui.gammadial.value())
            self.psi = np.radians(self.ui.psidial.value())

            self.alpha = np.radians(self.ui.alphadial.value())
        
        elif self.excel_actions_status == True and self.excel_actions_df is not None:            
            self.actions_counter +=1
            if self.actions_counter < self.excel_actions_df['Frame'].iloc[-1]:
                filtered_row = self.excel_actions_df[self.excel_actions_df['Frame'] == self.actions_counter]
                
                self.Bx = float(filtered_row["Bx"])
                self.By = float(filtered_row["By"])
                self.Bz = float(filtered_row["Bz"])
                self.alpha = float(filtered_row["Alpha"])
                self.gamma = float(filtered_row["Gamma"])
                self.freq = float(filtered_row["Rolling Frequency"])
                self.psi = float(filtered_row["Psi"])
                self.gradient = float(filtered_row["Gradient"])
                self.acoustic_freq = float(filtered_row["Acoustic Frequency"])
            
            else:
                self.excel_actions_status = False
                self.ui.apply_actions.setText("Apply")
                self.ui.apply_actions.setChecked(False)
                self.apply_actions(False)

            
        
        #DEFINE CURRENT MAGNETIC FIELD OUTPUT TO A LIST 
        self.actions = [self.Bx, self.By, self.Bz, self.alpha, self.gamma, self.freq, self.psi, self.gradient_status,
                        self.acoustic_frequency, self.sensorBx, self.sensorBy, self.sensorBz] 
        
        self.magnetic_field_list.append(self.actions)
        self.apply_actions(True)
        
        #IF SAVE STATUS THEN CONTINOUSLY SAVE THE CURRENT ROBOT PARAMS AND MAGNETIC FIELD PARAMS TO AN EXCEL ROWS
        if self.save_status == True:
            self.magnetic_field_sheet.append(self.actions)
           

    def apply_actions(self, status):
        #the purpose of this function is to output the actions via arduino, 
        # show the actions via the simulator
        # and record the actions by appending the field_list
        
        #toggle between alpha and orient
        if self.freq > 0:
            if self.ui.swimradio.isChecked():
                self.simulator.roll = False
            elif self.ui.rollradio.isChecked():
                self.alpha = self.alpha - np.pi/2
                self.simulator.roll = True

        #zero output
        if status == False:
            self.manual_status = False
            self.Bx, self.By, self.Bz, self.alpha, self.gamma, self.freq, self.psi, self.acoustic_frequency = 0,0,0,0,0,0,0,0

        #output current actions to simulator

        self.simulator.Bx = self.Bx
        self.simulator.By = self.By
        self.simulator.Bz = self.Bz
        self.simulator.alpha = self.alpha
        self.simulator.gamma = self.gamma
        self.simulator.psi = self.psi
        self.simulator.freq = self.freq/15
        self.simulator.omega = 2 * np.pi * self.simulator.freq

         #send arduino commands
        self.arduino.send(self.Bx, self.By, self.Bz, self.alpha, self.gamma, self.freq, self.psi, self.gradient_status, self.acoustic_frequency)
    


    def start_data_record(self):
        self.output_workbook = openpyxl.Workbook()
            
        #create sheet for magneti field actions
        self.magnetic_field_sheet = self.output_workbook.create_sheet(title="Magnetic Field Actions")#self.output_workbook.active
        self.magnetic_field_sheet.append(["Bx", "By", "Bz", "Alpha", "Gamma", "Rolling Frequency", "Psi", "Gradient?", "Acoustic Frequency","Sensor Bx", "Sensor By", "Sensor Bz"])

    
        #tell update_actions function to start appending data to the sheets
        self.save_status = True



    def stop_data_record(self):
        #tell update_actions function to stop appending data to the sheets
        self.save_status = False
        file_path  = os.path.join(self.new_dir_path, self.date+".xlsx")
        
        #add trajectory to file after the fact
        if self.output_workbook is not None:
   
            #save and close workbook
            self.output_workbook.remove(self.output_workbook["Sheet"])
            self.output_workbook.save(file_path)

            self.output_workbook.close()
            self.output_workbook = None

    
    def savedata(self):
        if self.ui.savedatabutton.isChecked():
            self.ui.savedatabutton.setText("Stop")
            self.start_data_record()
        else:
            self.ui.savedatabutton.setText("Save Data")
            self.date = datetime.now().strftime('%Y.%m.%d-%H.%M.%S')
            self.stop_data_record()
            
    
    """def toggle_simulation(self):
        if self.ui.simulationbutton.isChecked():
            self.simulator.start()
            self.tbprint("Simulation Off")
            self.ui.simulationbutton.setText("Simulation Off")
        else:
            self.simulator.stop()
            self.tbprint("Simulation On")
            self.ui.simulationbutton.setText("Simulation On")"""
   

            
            
    

    def toggle_joystick_status(self):
        if pygame.joystick.get_count() != 0:
            if self.ui.joystickbutton.isChecked():
                self.joystick_status = True
                self.ui.joystickbutton.setText("Stop")
                self.tbprint("Joystick On")
            else:
                self.joystick_status = False
                self.ui.joystickbutton.setText("Joystick")
                self.tbprint("Joystick Off")
                self.apply_actions(False)
        else:
            self.tbprint("No Joystick Connected...")



    def get_acoustic_frequency(self):
        if self.ui.applyacousticbutton.isChecked():
            self.acoustic_frequency = self.ui.acousticfreq_spinBox.value()
            #self.tbprint("Control On: {} Hz".format(self.acoustic_frequency))
            self.apply_acoustic()
        
    
    def apply_acoustic(self):
        if self.ui.applyacousticbutton.isChecked():
            self.ui.applyacousticbutton.setText("Stop")
            #self.tbprint("Control On: {} Hz".format(self.acoustic_frequency))
            self.acoustic_frequency = self.ui.acousticfreq_spinBox.value()
            #self.acoustic_module.start(self.acoustic_frequency, 0)
            self.apply_actions(True)
            self.ui.led.setStyleSheet("\n"
"                background-color: rgb(0, 255, 0);\n"
"                border-style: outset;\n"
"                border-width: 3px;\n"
"                border-radius: 12px;\n"
"                border-color: rgb(0, 255, 0);\n"
"         \n"
"                padding: 6px;")
        
        else:
            self.ui.applyacousticbutton.setText("Apply")
            #self.tbprint("Acoustic Module Off")
            #self.acoustic_module.stop()
            self.acoustic_frequency = 0
            self.ui.led.setStyleSheet("\n"
"                background-color: rgb(255, 0, 0);\n"
"                border-style: outset;\n"
"                border-width: 3px;\n"
"                border-radius: 12px;\n"
"                border-color: rgb(255, 0, 0);\n"
"         \n"
"                padding: 6px;")
            #self.apply_actions(False)
       
        

    def tbprint(self, text):
        #print to textbox
        self.ui.plainTextEdit.appendPlainText("$ "+ text)


    
    
    def update_halleffect_sensor(self, vals):
        sensorBx, sensorBy, sensorBz = vals
        self.ui.bxlabel.setText("Bx:{}".format(sensorBx))
        self.ui.bylabel.setText("By:{}".format(sensorBy))
        self.ui.bzlabel.setText("Bz:{}".format(sensorBz))
        self.sensorBx = sensorBx
        self.sensorBy = sensorBy
        self.sensorBz = sensorBz
    
    def get_manual_bfieldbuttons(self):
        if self.ui.manualapplybutton.isChecked():
            self.manual_status = True
            self.ui.manualapplybutton.setText("Stop")
        else:
            self.ui.manualapplybutton.setText("Apply")
            self.apply_actions(False)
    


       
    def get_slider_vals(self):
       
      
        magneticfreq = self.ui.magneticfrequencydial.value()
        gamma = self.ui.gammadial.value()
        psi = self.ui.psidial.value()
        #alpha = self.ui.alphaspinBox.value()
            

        self.ui.gammalabel.setText("Gamma: {}".format(gamma))
        self.ui.psilabel.setText("Psi: {}".format(psi))
        self.ui.rollingfrequencylabel.setText("Freq: {}".format(magneticfreq))

         
        
    def resetparams(self):
    
        self.ui.gammadial.setSliderPosition(90)
        self.ui.psidial.setSliderPosition(90)
        self.ui.magneticfrequencydial.setSliderPosition(10)
        self.ui.acousticfreq_spinBox.setValue(1000000)


    def closeEvent(self, event):
        """
        called when x button is pressed
        """
        self.loop.stop()
        self.simulator.stop()
        self.apply_actions(False)
        self.halleffect.stop()
        self.arduino.close()
