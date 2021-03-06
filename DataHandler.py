import socket
import util
import re
import os
import time
from datetime import datetime, timedelta
import threading
import DatabaseHandler as db
import queue
import sys
sys.path.append('./AutoID_ML')
import AutoID_ML.fromback as fb
from AutoID_ML.button_bitid import Button

class DataHandler(threading.Thread):
    def __init__(self, stop_event):
        threading.Thread.__init__(self)
        self._stop = stop_event
        self.xInput = {}
        self.xInput['RSSI'] = 0 
        self.xInput['EPC'] = ''
        self.threshold = -100
        config = util.loadConfig()
        self.s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.host = config['readerIP']
        self.port = config['readerPort']
        self.maxRSSI = -200 
        self.maxEPC = ''
        self.bufSize = 2048
        self.index = 0
        self.resultlist = []
        try:
            self.s.connect((self.host, self.port))
        except BlockingIOError:
            pass
        resetThread = threading.Thread(target=self.resetEPC, args=())
        resetThread.start()
    def resetEPC(self):
        while True:
            self.maxRSSI = -300 
            self.maxEPC = ''
            time.sleep(1)
    def updateEPC(self, rssi, epc):
        if rssi > self.maxRSSI:
            self.maxRSSI = rssi
            self.maxEPC = epc
    def getTopTag(self):
        if self.maxRSSI > self.threshold:
            print('EPC info' +str(self.maxRSSI) +self.maxEPC)
            return self.maxEPC 
        else:
            return 'None' 
    def getObjectInfo(self, objName):
        tagList = db.mongoHandler.getRelatedSensors(objName)
        tagStateList = self.processdata(tagList)
        infoList = []
        for tag, tagState in tagList, tagStateList:
            tagSem = db.mongoHandler.getTagSemantic(tag, tagState)
            infoList.append({"tag": tag, "state": tagSem})
        return infoList
    def processdata(self, EPClist):
        buttonlist = []
        for item in EPClist:
            tempbutton = Button(item)
            buttonlist.append(tempbutton)
        timeEnd = timedelta(seconds = 0)
        win = timedelta(seconds=0.2)
        step = timedelta(seconds=0.1)
        resultlist = []
        # while True:
        if len(self.xInput['ReaderTimestamp']):
            while True:
                temp = max(self.xInput['ReaderTimestamp'])
                # 考虑两个时间节点，一个是按照step走的timeEnd，还有一个是现在接收到的数据的最迟时间
                if  temp > timeEnd:
                    timeEnd = temp
                    break
                else:
                    time.sleep(0.1)
            timeStart = timeEnd - win
            index  = lower_bound(self.xInput['ReaderTimestamp'],index,len(self.xInput['ReaderTimestamp']),timeStart)
            for item in buttonlist:
                resultlist.append(item.winstatusChangelist(self.xInput,index))
            # print(button.winstatusChangelist(xInput,index))
            timeEnd = timeEnd+step
        return resultlist
    def run(self):
        first_number = ''
        reset_thread = threading.Thread(target=self.resetEPC, args=())
        reset_thread.start()
        while True:
            data = self.s.recv(self.bufSize).decode()
            if data:
                # 处理不完整的信息
                data = first_number + data
                first_number = ''
                while not  data[-1:] == '\n':
                    first_number = data[-1:] + first_number
                    data =  data[:-1]
                datalist = re.split('[,;]', data)
                i = 0
                for item in datalist:
                    k = i % 9
                    if item == '':
                        continue
                    else:
                        if k  ==  1:
                            self.xInput['EPC'] = item
                        elif k == 2:
                            self.xInput['Antenna'] = int(item)
                        elif k == 3:
                            self.xInput['Freq'] = float(item)
                        elif k == 4:
                            self.xInput['ReaderTimestamp'] = timedelta(seconds = (float(item)/1000))
                        elif k == 5:
                            self.xInput['RSSI'] = float(item)
                        elif k == 6:
                            self.xInput['Doppler'] = float(item)
                        elif k == 7:
                            self.xInput['Phase'] = float(item)
                        elif k == 8:
                            self.xInput['ComputerTimestamp'] = timedelta(seconds = (float(item[:-1])/1000))
                        else:
                            self.updateEPC(self.xInput['RSSI'], self.xInput['EPC'])
                        i = i + 1 
            else:
                break

if __name__ == '__main__':
    q = queue.Queue()
    stop = threading.Event()
    dataHandler = DataHandler(stop)
    dataHandler.start()