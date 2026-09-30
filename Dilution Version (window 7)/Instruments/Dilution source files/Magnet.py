from tkinter import *
import time
import re


class Magnet:
    """GUI widget to control the dilution fridge magnet using
    :class:`DilutionInstrument`.
    """

    def __init__(self, win, createDefaultValue, instrument):
        # expect an instance of DilutionInstrument
        self.inst = instrument
        self.dilution_socket = instrument.dilution_socket

        xLim = 680
        xSifh = 90
        yLim = 2
        c = 2
        yLocShift = 30
        yLocShift = yLocShift+30
        self.Magflag = False
        ymag = yLim + 2 * yLocShift
        xmag = 500
        ymagShif = 30
        # turn-on magnet control button
        self.b8 = Button(win, text='Magnet ON', height=1, width=8,
                         command=self.startMagnet, fg='green')
        self.b8.place(x=500, y=272)
        # choose magnet sweep rate
        self.t57 = createDefaultValue(win, '0.1')
        self.t57.place(x=xmag, y=ymag+ymagShif)
        self.lbl57 = Label(win, text='Rate (T/min)')
        self.lbl57.place(x=xmag-xSifh, y=ymag+ymagShif)
        # choose magnet set point x
        self.t58 = createDefaultValue(win, '0')
        self.t58.place(x=xmag, y=ymag+2*ymagShif)
        self.lbl58 = Label(win, text='Bx (T)')
        self.lbl58.place(x=xmag-xSifh, y=ymag+2*ymagShif)
        # choose magnet set point y
        self.t59 = createDefaultValue(win, '0')
        self.t59.place(x=xmag, y=ymag+3*ymagShif)
        self.lbl59 = Label(win, text='By (T)')
        self.lbl59.place(x=xmag-xSifh, y=ymag+3*ymagShif)
        # choose magnet set point z
        self.t60 = createDefaultValue(win, '0')
        self.t60.place(x=xmag, y=ymag+4*ymagShif)
        self.lbl60 = Label(win, text='Bz (T)')
        self.lbl60.place(x=xmag-xSifh, y=ymag+4*ymagShif)

    def startMagnet(self):
        self.Magflag = True
        self.b8.config(text='Magnet OFF', command=self.interStop, fg='red')
        self.magnetRate = float(self.t57.get())
        self.magnetX = float(self.t58.get())
        self.magnetY = float(self.t59.get())
        self.magnetZ = float(self.t60.get())
        self.inst.ramp_magnet_to(self.magnetRate,
                                 self.magnetX,
                                 self.magnetY,
                                 self.magnetZ)
        self.Indicator()

    def readMagnet(self):
        # forward to instrument
        return self.inst.read_magnet()

    def setFieldStep(self, parameters):
        self.Magflag = True
        self.b8.config(text='Magnet OFF', command=self.interStop, fg='red')
        self.magnetRate = float(parameters[0])
        self.magnetX = float(parameters[1])
        self.magnetY = float(parameters[2])
        self.magnetZ = float(parameters[3])
        self.inst.ramp_magnet_to(self.magnetRate,
                                 self.magnetX,
                                 self.magnetY,
                                 self.magnetZ)
        time.sleep(2)
        self.Indicator()

    def Indicator(self):
        FieldX, FieldY, FieldZ = self.inst.read_magnet()
        self.magnetIndicator = f'_{FieldX:.6f}T_{FieldY:.6f}T_{FieldZ:.6f}T'

    def interStop(self):
        self.inst.ramp_magnet_zero()
        self.Magflag = False
        self.b8.config(text='Magnet ON', command=self.startMagnet, fg='green')
