from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread,QTimer


    
#all this class is doing is creating a seperate thread to continously output action commands. there is a better way but its the easiest atm.
class Looping_Thread(QThread):
    actions_signal = pyqtSignal(int)


    def __init__(self, parent):
        super().__init__(parent=parent)
        self.parent = parent

  
        self._run_flag = True

    def run(self):
    
        # capture from web camx
        while self._run_flag:
                actions = 1
                self.actions_signal.emit(actions)
                QThread.msleep(50)


    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        #blank = np.zeros((self.width, self.height, 3), dtype=np.uint8) 
        #self.change_pixmap_signal.emit(blank)

        self._run_flag = False
        self.wait()



