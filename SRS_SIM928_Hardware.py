### written on python 2.7

PARITY = 'N'
STOPBITS = 1
BYTESIZE = 8
XONXOFF  = False
RTSCTS   = True
TIMEOUT = 0.1 # in seconds when reading from the device
SENDTERMSTR = '\r\n'
RESPONSETERMSTR = '\r\n'  # used to distinguish whether the received characters form a complete response
WAIT_TIME_UNIT=0.01
import socket
import time
from threading import RLock

class SRS_SIM928_Hardware:
    def __init__(self,host,port):
        self.port = int(port)
        self.host = host
        self.devfile  = None
        self.connected = False
        self.conn_callbacks = []
        self.busy = False
        self.info_ident = ""
        self.battery_state = (-1,-1,-1)
        self.battery_state_str = ("unknown", "unknown", "unknown")
        self.battery_state_desc = {-1: "unknown", 0 : "", 1 : "in use", 2 : "charging", 3 : "ready/standby"}
        self.commlock = RLock()     
        
    def reconnect(self):
        try:
            self.sock.close()
            self.connected = False
        except socket.error:
            pass
        self.connect()
        
    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.last_comm_timeout = False
        print "Connecting to Host", self.host, ", Port", self.port
        try:
            self.sock.setblocking(1)
        except:
            pass
        try:
            self.sock.connect((self.host, self.port))
        except Exception as e:
            print "Exception occured while connecting"
            print e.__class__
            print e
            self.connected = False
        else:
            try:
                self.info_ident = self.communicate("*IDN?")
            except:
                print self.info_ident
                pass
            print "Success."
            self.connected = True
            for c in self.conn_callbacks:
                c(True)
        self.sock.setblocking(0)

    def disconnect(self):
        if not self.serial.isOpen():
            return
        self.serial.close()
        self.connected = False
        for c in self.conn_callbacks:
            c(False)
        
    def communicate(self, command, timeout=1.0):
        # send command
        with self.commlock:
            print "communicate called"
            print "command", command
            try:
                command=command.strip('\n\r')+SENDTERMSTR
                self.sock.send(command.encode('utf-8'))
            except socket.error:
                self.connected = False
            # get an answer
            time.sleep(0.2)
            resp = ""
            try:
                resp += self.sock.recv(10000)
            except socket.error:
                pass
            tstart = time.time()
            tend = tstart
            # really wait (block!) until end-of-line character is reached
            while( (len(resp)==0 or resp[-1]!='\n') and tend-tstart<timeout):
                #print "Delay!"
                try:
                    resp += self.sock.recv(10000)
                except socket.error:
                    pass
                time.sleep(WAIT_TIME_UNIT)
                tend = time.time()
            self.last_comm_timeout = (tend-tstart>=timeout)
            print resp
            return resp.decode('utf-8')

    def read_ident(self):
        self.info_ident = self.communicate("*IDN?")
        return str(self.info_ident).strip()

        
    def read_battery_state(self):
        answer = self.communicate("BATS?")
        tokens = answer.split(',')
        try:
            self.battery_state = (int(tokens[0]), int(tokens[1]), int(tokens[2]))
            self.battery_state_str = (self.battery_state_desc[self.battery_state[0]],
                                      self.battery_state_desc[self.battery_state[1]],
                                      "ok" if self.battery_state[2]==0 else "battery service needed")
            return self.battery_state
        except:
            return (-1,-1,-1)

    def read_output_on(self):
        answer = self.communicate("EXON?")
        try:
            output_state = int(answer)
            return output_state
        except:
            return -1
        
    def write_output_on(self, on_state=True):
        if on_state:
            self.communicate("OPON")
        else:
            self.communicate("OPOF")
    
    def read_volt(self):
        answer = self.communicate("VOLT?")
        try:
            return float(answer)
        except ValueError:
            print("Got non-float voltage value from device: ", answer)
            return None
    
    def write_volt(self, volt):
        try:
            volt = float(volt)
        except:
            return
        if volt>20.0:
            volt = 20.0
        if volt<-20.0:
            volt = -20.0
        self.communicate("VOLT {v:5.3f}".format(v=volt))
        
    def clear_status(self):
        self.communicate("*CLS")
    
    def write_bat_charge_override(self):
        self.communicate("BCOR")
    
    def read_battery_info(self, parameter=0):
        """ allowed parameter values are 0 = PNUM (Battery pack part number)
                                         1 = SERIAL (Battery pack serial number)
                                         2 = MAXCY (Design life, number of charge cycles)
                                         3 = CYCLES (number of charge cycles used)
                                         4 = PDATE (Battery pack production date (YYYY-MM-DD))
        """
        try:
            parameter = int(parameter)
        except:
            return
        if parameter < 0 or parameter > 4:
            return
        answer = self.communicate("BIDN? " + str(parameter))
        return str(answer).strip()
    
    def add_connection_listener(self, callback):
        print "callback"
        self.conn_callbacks.append(callback)

    def send(self, sendstr):
        self.communicate(sendstr, receive=False)

    def send_and_receive(self, sendstr, receive=True, maxtries=20):
        if not self.serial or not self.serial.isOpen():
            return ""
        while (self.busy):
            time.sleep(0.02)
        self.busy = True
        try:
            #print("sending ", sendstr)
            s=sendstr.strip('\n\r')+SENDTERMSTR
            #s = bytes(s, 'utf-8')   # needed only in python3 (?)
            s=s.encode('utf-8')            
            self.serial.write(s)
            if not receive:
                return None
            time.sleep(0.1)
            responsebuf = ""
            loops = 0
            while not responsebuf.endswith(RESPONSETERMSTR) and loops < maxtries:
                buf = self.serial.read(10000) # insecure, should receive until line ending!
                try:
                    responsebuf += buf.decode('utf-8')
                except:
                    pass
                #print("received " + str(len(buf)) + " bytes.")
                loops = loops + 1
            #print("received ", responsebuf)
            return responsebuf
        except:
            self.busy = False
            raise
        finally:
            self.busy = False
        
