#!/usr/bin/env python
#
# This file is protected by Copyright. Please refer to the COPYRIGHT file distributed with this 
# source distribution.
# 
# This file is part of REDHAWK Basic Components ArbitraryRateResampler.
# 
# REDHAWK Basic Components ArbitraryRateResampler is free software: you can redistribute it and/or modify it under the terms of 
# the GNU Lesser General Public License as published by the Free Software Foundation, either 
# version 3 of the License, or (at your option) any later version.
# 
# REDHAWK Basic Components ArbitraryRateResampler is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; 
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR 
# PURPOSE.  See the GNU Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License along with this 
# program.  If not, see http://www.gnu.org/licenses/.
#
import ossie.utils.testing
from ossie.utils import sb
import os
from omniORB import any

import time
from ossie.cf import CF

ENABLE_PLOTS=False
if ENABLE_PLOTS:
    import matplotlib.pyplot

from ossie.utils.sb.io_helpers import compareSRI
from ossie.utils.bulkio.bulkio_data_helpers import ArraySink 
from bulkio.bulkioInterfaces import BULKIO as _BULKIO
from bulkio.bulkioInterfaces import BULKIO__POA as _BULKIO__POA

from bulkio.bulkioInterfaces import BULKIO, BULKIO__POA

import math

class MyArraySink(ArraySink):
    """Subclas ArraySink to help track data in streams more effectively
    """
    def __init__(self, porttype):
        ArraySink.__init__(self, porttype)
        self.outputs={}
        self.sris={}
        self.dataPackets={}
        self.lastTime=time.time()
    def pushSRI(self, H):
        streamID = H.streamID
        l=self.outputs.setdefault(streamID,[])
        l.append(H)
        self.sris.setdefault(streamID,[]).append(H)
        self.lastTime=time.time()
        return ArraySink.pushSRI(self, H)
    def pushPacket(self, data, ts, EOS, stream_id):
        l=self.outputs[stream_id]
        sri = self.sris[stream_id][-1]
        xdelta = sri.xdelta
        if ts.tcstatus == BULKIO.TCS_VALID:
            tStart = ts.twsec+ts.tfsec+ts.toff*xdelta
        else:
            tStart=None
        cmplx = sri.mode==1
        t=(tStart, xdelta, cmplx, data)
        l.append(t)
        self.dataPackets.setdefault(stream_id,[]).append(t)
        self.lastTime=time.time()
        return ArraySink.pushPacket(self, data, ts, EOS, stream_id)
    def getPackets(self):
        out = self.dataPackets
        self.dataPackets={}
        return out

class MyDataSink(sb.DataSink):
    """subclass sb.DataSink to use MyArraySink
    """
    def getPackets(self):
        return self._sink.getPackets()
    def getPort(self, portName):
        if str(portName) == "xmlIn":
            return sb.DataSink.getPort(self, portName)
        try:
            self._sinkPortType = self.getPortType(portName)

            # Set up output array sink
            self._sink = MyArraySink(eval(self._sinkPortType))

            if self._sink != None:
                self._sinkPortObject = self._sink.getPort()
                return self._sinkPortObject
            else:
                return None
            pass
        except Exception, e:
            print self.className + ":getPort(): failed " + str(e)
        return None

class MyDataSource(sb.DataSource):
    """Subclass sb.DataSource to incremenent currentSampleTime when pushing data
    """
    def pushThread(self):
        self.settingsAcquired = False
        self.threadExited = False
        # Make sure data passed in is within min/max bounds on port type 
        # and is a valid type
        currentSampleTime = self._startTime
        streamSampleTimes={}
        while not self._exitThread:
            exitInputLoop = False
            while not exitInputLoop:
                try:
                    dataset = self._dataQueue.get(timeout=0.1)
                    exitInputLoop = True
                    settingsAcquired = True
                except:
                    if self._exitThread:
                        exitInputLoop = True
            if self._exitThread:
                if self.settingsAcquired:
                    self._pushPacketAllConnectedPorts([], 
                                                      currentSampleTime, 
                                                      EOS,
                                                      streamID)
                    self._packetSent()
                self.threadExited = True
                return

            data        = dataset[0]
            EOS         = dataset[1]
            streamID    = dataset[2]
            sampleRate  = dataset[3]
            complexData = dataset[4]
            SRIKeywords = dataset[5]
            loop        = dataset[6]
            currentSampleTime = streamSampleTimes.setdefault(streamID, self._startTime)

            # If loop is set in method call, override class attribute
            if loop != None:
                self._loop = loop
            try:
                self._sampleRate  = sampleRate
                self._complexData = complexData
                self._SRIKeywords = SRIKeywords
                self._streamID    = streamID
                candidateSri      = None 
                # If any SRI info is set, call pushSRI
                if streamID != None or \
                  sampleRate != None or \
                  complexData != None or \
                  len(SRIKeywords) > 0:
                    keywords = []
                    for key in self._SRIKeywords:
                        keywords.append(_CF.DataType(key._name, _properties.to_tc_value(key._value,str(key._format))))
                    candidateSri = _BULKIO.StreamSRI(1, 0.0, 1, 0, 0, 0.0, 0, 0, 0,
                                                     streamID, self._blocking, keywords)
                
                    if sampleRate > 0.0:
                        candidateSri.xdelta = 1.0/float(sampleRate)
    
                    if complexData == True:
                        candidateSri.mode = 1
                    else:
                        candidateSri.mode = 0

                    if self._startTime >= 0.0:
                        candidateSri.xstart = self._startTime
                else:
                    candidateSri = _BULKIO.StreamSRI(1, 0.0, 1, 0, 0, 0.0, 0, 0, 0,
                                                     "defaultStreamID", self._blocking, [])

                if self._sri==None or not compareSRI(candidateSri, self._sri):
                    self._sri = candidateSri
                    self._pushSRIAllConnectedPorts(sri = self._sri)
    
                # Call pushPacket
                # If necessary, break data into chunks of pktSize for each 
                # pushPacket
                if len(data) > 0:
                    self._pushPacketsAllConnectedPorts(data,
                                                       currentSampleTime, 
                                                       EOS, 
                                                       streamID)
                    # If loop is set to True, continue pushing data until loop 
                    # is set to False or stop() is called
                    while self._loop:
                        self._pushPacketsAllConnectedPorts(data, 
                                                           currentSampleTime, 
                                                           EOS, 
                                                           streamID)
                else:
                    self._pushPacketAllConnectedPorts(data,
                                                      currentSampleTime,
                                                      EOS,
                                                      streamID)
                self._packetSent()
                if self._complexData:
                    currentSampleTime+=len(data)/float(sampleRate)/2
                else:
                    currentSampleTime+=len(data)/float(sampleRate)
                streamSampleTimes[streamID]=currentSampleTime
            except Exception, e:
                print self.className + ":pushData() failed " + str(e)
        self.threadExited = True

#a few utility functions to pack and unpack complex data to send it to REDHAWK appropriately
def cxToPackedReal(sig):
    out=[]
    for x in sig:
        out.append(x.real)
        out.append(x.imag)
    return out

def packedRealtoCx(sig):
    out=[]
    realVal=None
    for x in sig:
        if realVal!=None:
            out.append(complex(realVal,x))
            realVal=None
        else:
            realVal = x
    return out

#define a few functions we will use later
def f(t):
    return math.sin(2*math.pi*112.456*t)+math.cos(2*math.pi*78.4*t)+4+t
  
def g(t):
    return complex(math.sin(2*math.pi*112.456*t), math.cos(2*math.pi*78.4*t)+4+t)

def h(t):
    return t

class FunctionGenerator(object):
    """Class which creates a signal from a function 
    """
    def __init__(self, f):
        self.f = f
    def eval(self, t):
        return self.f(t)
    def makeSig(self,tstart=0,sampleRate=1000,numSamples=1000):
        t=tstart
        delta = 1.0/sampleRate
        out=[]
        time=[]
        for _ in xrange(numSamples):
            out.append(self.f(t))
            time.append(t)
            t+=delta
        return out, time

def cmpSignals(s1,s2):
    """compare two signals to find avg and max differences
    """
    maxDif=0
    totalDif=0
    z = zip(s1,s2)
    for x1,x2 in z:
        d = abs(x1-x2)
        totalDif+=d
        maxDif = max(d,maxDif)
    return maxDif, totalDif/float(len(z))

class ComponentTests(ossie.utils.testing.ScaComponentTestCase):
    """Test for all component implementations in ArbitraryRateResampler"""

    def setUp(self):
        ossie.utils.testing.ScaComponentTestCase.setUp(self)
        self.src = MyDataSource()
        #self.sink = MyFloatSink()
        self.sink = MyDataSink()
        
        self.setupComponent()
        
        self.src.connect(self.comp)
        self.comp.connect(self.sink)
        self.comp.start()
        self.src.start()
        self.sink.start()
        
    def setupComponent(self):
        #######################################################################
        # Launch the component with the default execparams
        execparams = self.getPropertySet(kinds=("execparam",), modes=("readwrite", "writeonly"), includeNil=False)
        execparams = dict([(x.id, any.from_any(x.value)) for x in execparams])
        self.launch(execparams)
        
        #######################################################################
        # Verify the basic state of the component
        self.assertNotEqual(self.comp, None)
        self.assertEqual(self.comp.ref._non_existent(), False)
        self.assertEqual(self.comp.ref._is_a("IDL:CF/Resource:1.0"), True)
        
        #######################################################################
        # Validate that query returns all expected parameters
        # Query of '[]' should return the following set of properties
        expectedProps = []
        expectedProps.extend(self.getPropertySet(kinds=("configure", "execparam"), modes=("readwrite", "readonly"), includeNil=True))
        expectedProps.extend(self.getPropertySet(kinds=("allocate",), action="external", includeNil=True))
        props = self.comp.query([])
        props = dict((x.id, any.from_any(x.value)) for x in props)
        # Query may return more than expected, but not less
        for expectedProp in expectedProps:
            self.assertEquals(props.has_key(expectedProp.id), True)
        
        #######################################################################
        # Verify that all expected ports are available
        for port in self.scd.get_componentfeatures().get_ports().get_uses():
            port_obj = self.comp.getPort(str(port.get_usesname()))
            self.assertNotEqual(port_obj, None)
            self.assertEqual(port_obj._non_existent(), False)
            self.assertEqual(port_obj._is_a("IDL:CF/Port:1.0"),  True)
            
        for port in self.scd.get_componentfeatures().get_ports().get_provides():
            port_obj = self.comp.getPort(str(port.get_providesname()))
            self.assertNotEqual(port_obj, None)
            self.assertEqual(port_obj._non_existent(), False)
            self.assertEqual(port_obj._is_a(port.get_repid()),  True)

    def testScaBasicBehavior(self):          
        #######################################################################
        # Make sure start and stop can be called without throwing exceptions
        self.setupComponent()
        self.comp.start()
        self.comp.stop()
        
        #######################################################################
        # Simulate regular component shutdown
        self.comp.releaseObject()

    def testDownSample(self):
        """downsample real data
        """
        inputRate =16123.45
        self.comp.outputRate=500
        self.comp.a=7
        self.comp.quantization=1e4
        
        gen=FunctionGenerator(f)
        inData = gen.makeSig(0, inputRate, 5000)[0]
        
        streamName = 'myStream'
        
        outData = self.main(inData,inputRate,numPushes=2,cmplx=False, streamID=streamName)
        assert(len(outData)==1)
        outputPackets = outData[streamName]
        self.verifyOutputStream(outputPackets, gen)

    def testUpSample(self):
        """upsample real data
        """
        inputRate =500 
        self.comp.outputRate=16123.45
        self.comp.a=7
        self.comp.quantization=1e4
        
        gen=FunctionGenerator(f)
        inData = gen.makeSig(0, inputRate, 5000)[0]
        
        streamName = 'myStream'
        
        outData = self.main(inData,inputRate,numPushes=2,cmplx=False, streamID=streamName)
        assert(len(outData)==1)
        outputPackets = outData[streamName]
        self.verifyOutputStream(outputPackets, gen)

    def testDownSampleCx(self):
        """down sample complex data
        """
        inputRate =16123.45
        self.comp.outputRate=500
        self.comp.a=7
        self.comp.quantization=1e4
        
        gen=FunctionGenerator(g)
        cxInData = gen.makeSig(0, inputRate, 5000)[0]
        inData = cxToPackedReal(cxInData)
        
        streamName = 'myStream'
        
        outData = self.main(inData,inputRate,numPushes=2,cmplx=True, streamID=streamName)
        assert(len(outData)==1)
        outputPackets = outData[streamName]
        self.verifyOutputStream(outputPackets, gen)

    def testUpSampleCx(self):
        """up sample complex data
        """
        inputRate =500 
        self.comp.outputRate=16123.45
        self.comp.a=7
        self.comp.quantization=1e4
        
        gen=FunctionGenerator(g)
        cxInData = gen.makeSig(0, inputRate, 5000)[0]
        inData = cxToPackedReal(cxInData)
        
        streamName = 'myStream'
        
        outData = self.main(inData,inputRate,numPushes=2,cmplx=True, streamID=streamName)
        assert(len(outData)==1)
        outputPackets = outData[streamName]
        self.verifyOutputStream(outputPackets, gen)

    def testChangeA(self):
        """ change the parameter "a" and verify the componet functions properly
        """
        inputRate =500 
        self.comp.outputRate=16123.45
        self.comp.a=7
        self.comp.quantization=1e4
        
        gen=FunctionGenerator(f)
        inData = gen.makeSig(0, inputRate, 5000)[0]
        
        streamName = 'myStream'
        
        self.src.push(inData[:len(inData)/3],complexData = False, sampleRate=inputRate, streamID=streamName)
        self.comp.a=10
        self.src.push(inData[len(inData)/3:len(inData)/3*2],complexData = False, sampleRate=inputRate, streamID=streamName)
        self.comp.a=5
        self.src.push(inData[len(inData)/3*2:],complexData = False, sampleRate=inputRate, streamID=streamName)
        outData = self.getOutput()
        
        assert(len(outData)==1)
        outputPackets = outData[streamName]
        self.verifyOutputStream(outputPackets, gen)

    def testChangeQuantization(self):
        """ change the parameter "quantization" and verify the componet functions properly
        """
        inputRate =500 
        self.comp.outputRate=16123.45
        self.comp.a=7
        self.comp.quantization=1e4
        
        gen=FunctionGenerator(f)
        inData = gen.makeSig(0, inputRate, 5000)[0]
        
        streamName = 'myStream'
        
        self.src.push(inData[:len(inData)/2],complexData = False, sampleRate=inputRate, streamID=streamName)
        self.comp.quantization=0
        self.src.push(inData[len(inData)/2:],complexData = False, sampleRate=inputRate, streamID=streamName)
        outData = self.getOutput()
        
        assert(len(outData)==1)
        outputPackets = outData[streamName]
        self.verifyOutputStream(outputPackets, gen)

    def testChangeOutputRate(self):
        """ change the parameter "outputRate" and verify the componet functions properly
        """
        inputRate =500 
        self.comp.outputRate=16123.45
        self.comp.a=7
        self.comp.quantization=1e4
        
        gen=FunctionGenerator(f)
        inData = gen.makeSig(0, inputRate, 5000)[0]
        
        streamName = 'myStream'
        
        self.src.push(inData[:len(inData)/2],complexData = False, sampleRate=inputRate, streamID=streamName)
        self.comp.outputRate=9876.543
        self.src.push(inData[len(inData)/2:],complexData = False, sampleRate=inputRate, streamID=streamName)
        outData = self.getOutput()
        
        assert(len(outData)==1)
        outputPackets = outData[streamName]
        self.verifyOutputStream(outputPackets, gen,constOutputRate=False)

    def testChangeInputRate(self):
        """change the input sample rate and ensure the component resamples appropraitely
        """
        inputRateA =500 
        inputRateB =789 
        self.comp.outputRate=16123.45
        self.comp.a=7
        self.comp.quantization=1e4
        
        gen=FunctionGenerator(f)
        inDataA = gen.makeSig(0, inputRateA, 2500)[0]
        inDataB = gen.makeSig(len(inDataA)/float(inputRateA), inputRateB, 2500)[0]
        
        streamName = 'myStream'
        
        self.src.push(inDataA,complexData = False, sampleRate=inputRateA, streamID=streamName)        
        self.src.push(inDataB,complexData = False, sampleRate=inputRateB, streamID=streamName)
        time.sleep(1.0)
        outData = self.getOutput()
        
        assert(len(outData)==1)
        outputPackets = outData[streamName]
        self.verifyOutputStream(outputPackets, gen,constOutputRate=False)

    def testMultiStream(self):
        """send multiple streams and make sure the component resmaples them independently
        """        
        inputRateA =500 
        inputRateB =700 
        self.comp.outputRate=16123.45
        self.comp.a=7
        self.comp.quantization=1e4
        
        genA=FunctionGenerator(f)
        inDataA = genA.makeSig(0, inputRateA, 5000)[0]
        genB = FunctionGenerator(g)
        cxInDataB = genB.makeSig(0, inputRateB, 5000)[0]
        inDataB = cxToPackedReal(cxInDataB)
        
        streamNameA = 'myStreamA'
        streamNameB = 'myStreamB'
        
        #push some from stream A and some from stream B
        
        self.src.push(inDataA[:len(inDataA)/2],complexData = False, sampleRate=inputRateA, streamID=streamNameA)
        self.src.push(inDataB[:len(inDataB)/2],complexData = True, sampleRate=inputRateB, streamID=streamNameB)
        self.src.push(inDataA[len(inDataA)/2:],complexData = False, sampleRate=inputRateA, streamID=streamNameA)
        self.src.push(inDataB[len(inDataB)/2:],complexData = True, sampleRate=inputRateB, streamID=streamNameB)

        
        outData = self.getOutput()
        assert(len(outData)==2)
        outputPacketsA = outData[streamNameA]
        outputPacketsB = outData[streamNameB]
        self.verifyOutputStream(outputPacketsA, genA)
        self.verifyOutputStream(outputPacketsB, genB)

    def testRealCxInput(self):
        """send real data followed by complex data and make sure the component works appropriately
        """
        inputRate =500 
        self.comp.outputRate=16123.45
        self.comp.a=7
        self.comp.quantization=1e4
        
        genA=FunctionGenerator(f)
        inDataA = genA.makeSig(0, inputRate, 5000)[0]
        genB = FunctionGenerator(g)
        cxInDataB = genB.makeSig(len(inDataA)/float(inputRate), inputRate, 5000)[0]
        inDataB = cxToPackedReal(cxInDataB)
        
        streamName = 'myStream'
        
        #push some from stream A and some from stream B
        
        self.src.push(inDataA,complexData = False, sampleRate=inputRate, streamID=streamName)
        self.src.push(inDataB,complexData = True, sampleRate=inputRate, streamID=streamName)
        
        outData = self.getOutput()
        assert(len(outData)==1)
        outputPackets = outData[streamName]
        assert(len(outputPackets)==2)

        start, delta, isCmplx, dataSamples=outputPackets[0]
        assert(isCmplx==False)
        nextStart = self.verifyOutputPacket(start, delta, isCmplx, dataSamples, genA)
        start, delta, isCmplx, dataSamples=outputPackets[1]
        assert(isCmplx==True)
        self.verifyOutputPacket(start, delta, isCmplx, dataSamples, genB,nextStart)

    def testCxRealInput(self):
        """send complex data followed by real data and make sure the component works appropriately
        """
        inputRate =500 
        self.comp.outputRate=16123.45
        self.comp.a=7
        self.comp.quantization=1e4
        
        genA=FunctionGenerator(g)
        cxInDataA = genA.makeSig(0, inputRate, 5000)[0]
        inDataA = cxToPackedReal(cxInDataA)
        genB = FunctionGenerator(f)
        inDataB = genB.makeSig(len(cxInDataA)/float(inputRate), inputRate, 5000)[0]
        
        streamName = 'myStream'
        
        #push some from stream A and some from stream B
        
        self.src.push(inDataA,complexData = True, sampleRate=inputRate, streamID=streamName)
        self.src.push(inDataB,complexData = False, sampleRate=inputRate, streamID=streamName)
        
        outData = self.getOutput()
        assert(len(outData)==1)
        outputPackets = outData[streamName]
        #note - we get three pushes here - the first complex one, 
        #a transcient complex one where the filter is working all the complex samples out of its history
        #and the real one
        assert(len(outputPackets)==3)

        start, delta, isCmplx, dataSamples=outputPackets[0]
        assert(isCmplx==True)
        nextStart = self.verifyOutputPacket(start, delta, isCmplx, dataSamples, genA)
  
        #don't validate these samples against their nominal values because its all transcient and we don't expect this to perform super well over a few samples
        start, delta, isCmplx, dataSamples=outputPackets[1]
        assert(abs(start-nextStart)<delta)
        assert(isCmplx==True)
        nextStart=start+delta*len(dataSamples)/2
        
        start, delta, isCmplx, dataSamples=outputPackets[2]
        assert(isCmplx==False)
        assert(start==None)
        self.verifyOutputPacket(start, delta, isCmplx, dataSamples, genB,nextStart)

    def verifyOutputStream(self, outputPackets, generator,constOutputRate=True):        
        """Do validation on an ouptut stream
        """
        nextStart=None
        for start, delta, isCmplx, dataSamples in outputPackets:
            nextStart = self.verifyOutputPacket(start, delta, isCmplx, dataSamples, generator, nextStart,constOutputRate)
    
    def verifyOutputPacket(self, start, delta, isCmplx, dataSamples, generator, nextStart=None, constOutputRate=True):
        """do validation on a single data packet
        """
        if isCmplx:
            dataSamples = packedRealtoCx(dataSamples)

        #make sure the data rate is as expected
        thisRate = 1.0/delta
        if constOutputRate:
            assert(abs(thisRate-self.comp.outputRate)<.01)
        
        #make sure the packet start time is as expected
        if nextStart:
            if start:
                assert(abs(start-nextStart)<delta)
            else:
                start= nextStart        
        #use the signal generator to generate "ideal" data and compare it to the resampler output
        fakeData, t = generator.makeSig(start, thisRate, len(dataSamples))
        maxDif, avgDif = cmpSignals(dataSamples,fakeData)
        if ENABLE_PLOTS:
            if isCmplx:
                matplotlib.pyplot.plot(t,[x.real for x in dataSamples], t,[x.real for x in fakeData])
                matplotlib.pyplot.show()
                matplotlib.pyplot.plot(t,[x.imag for x in dataSamples], t,[x.imag for x in fakeData])
            else:
                matplotlib.pyplot.plot(t,dataSamples, t,fakeData)
            matplotlib.pyplot.show()
        self.assertTrue(avgDif<.1)
        #compute the expected start for the next packet
        nextStart=start+delta*len(dataSamples)
        return nextStart             
    
    def main(self,inData,sampleRate,streamID = "myStream", cmplx = False,numPushes=2):
        """The main engine for all the test cases - push data, and get output
           As applicable
        """
        inSample=0
        samplesPerPush = len(inData)/numPushes
        for i in xrange(numPushes):
            outSample = inSample+samplesPerPush
            self.src.push(inData[inSample:outSample],complexData = cmplx, sampleRate=sampleRate, streamID=streamID)
            inSample=outSample
        return self.getOutput()
    def getOutput(self):
        """Grab the output from the sink
        """
        output={}
        self.sink._sink.lastTime=time.time()
        while True:
            packets = self.sink.getPackets()
            if packets:
                for key, value in packets.items():
                    l = output.setdefault(key,[])
                    l.extend(value)
            elif time.time() - self.sink._sink.lastTime > 1.0:
                break
            time.sleep(.1)
        return output
        
    # TODO Add additional tests here
    #
    # See:
    #   ossie.utils.bulkio.bulkio_helpers,
    #   ossie.utils.bluefile.bluefile_helpers
    # for modules that will assist with testing components with BULKIO ports
    
if __name__ == "__main__":
    ossie.utils.testing.main("../ArbitraryRateResampler.spd.xml") # By default tests all implementations
