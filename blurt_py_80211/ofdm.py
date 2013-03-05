#!/usr/bin/env python
import numpy as np
import scrambler, util

def trainingSequenceFromFreq(ts_freq):
    ts = np.fft.ifft(ts_freq)
    return np.tile(ts, 4)[ts_freq.size/2:][:5*ts_freq.size/2+1]

def rangesInclusive(ranges):
    return np.hstack([np.arange(a,b+1) for a,b in ranges])

# sts = short training sequence
# lts = long training sequence

# Low Throughput (802.11a legacy) mode
class LT:
    nfft = 64
    ncp = 16
    sts_freq = np.zeros(64, np.complex128)
    sts_freq.put([4, 8, 12, 16, 20, 24, -24, -20, -16, -12, -8, -4],
                 (13./6.)**.5 * (1+1j) * np.array([-1, -1, 1, 1, 1, 1, 1, -1, 1, -1, -1, 1]))
    sts_time = trainingSequenceFromFreq(sts_freq)
    lts_freq = np.array([
        0, 1,-1,-1, 1, 1,-1, 1,-1, 1,-1,-1,-1,-1,-1, 1,
        1,-1,-1, 1,-1, 1,-1, 1, 1, 1, 1, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 1, 1,-1,-1, 1, 1,-1, 1,-1, 1,
        1, 1, 1, 1, 1,-1,-1, 1, 1,-1, 1,-1, 1, 1, 1, 1])
    lts_time = trainingSequenceFromFreq(lts_freq)
    dataSubcarriers = rangesInclusive(((-26,-22),(-20,-8),(-6,-1),(1,6),(8,20),(22,26)))
    pilotSubcarriers = np.array([-21,-7,7,21])
    pilotTemplate = np.array([1,1,1,-1])
    Nsc = dataSubcarriers.size

# specialized for long acoustic echos
class LT_audio(LT):
    ncp = 64

# High Throughput 20 MHz bandwidth
class HT20(LT):
    lts_freq = LT.lts_freq.copy()
    lts_freq.put([27, 28, -28, -27], [-1, -1, 1, 1])
    lts_time = trainingSequenceFromFreq(lts_freq)
    dataSubcarriers = rangesInclusive(((-28,-22),(-20,-8),(-6,-1),(1,6),(8,20),(22,28)))
    Nsc = dataSubcarriers.size

# High Throughput 40 MHz bandwidth
class HT40:
    nfft = 128
    ncp = 32
    sts_freq = np.r_[np.fft.fftshift(LT.sts_freq), 1j*np.fft.fftshift(LT.sts_freq)]
    sts_time = trainingSequenceFromFreq(sts_freq)
    lts_freq = np.r_[np.fft.fftshift(LT.lts_freq), 1j*np.fft.fftshift(LT.lts_freq)]
    lts_freq.put([-32, -5, -4, -3, -2, 2, 3, 4, 5, 32], [1, -1, -1, -1, 1, -1, 1, 1, -1, 1])
    lts_time = trainingSequenceFromFreq(lts_freq)
    dataSubcarriers = rangesInclusive(((-58,-54),(-52,-26),(-24,-12),(-10,-2),(2,10),(12,24),(26,52),(54,58)))
    pilotSubcarriers = np.array([-53,-25,-11,11,25,53])
    pilotTemplate = np.array([1,1,1,-1,0,0,0,0])
    Nsc = dataSubcarriers.size

def stitch(*x):
    output = np.zeros(sum(len(xx)-1 for xx in x)+1,np.complex)
    i = 0
    for xx in x:
        yy = xx[:]
        yy[0] *= .5
        yy[-1] *= .5
        output[i:i+len(yy)] += yy
        i += len(yy)-1
    return output

class OFDM:
    def __init__(self, format=LT):
        self.format = format
    def pilotPolarity(self):
        return (1 - 2 * x for x in scrambler.scrambler(0x7F))
    def encodeSymbols(self, dataSubcarriers, pilotPolarity):
        Ns = dataSubcarriers.shape[0]
        symbols = np.zeros((Ns,self.format.nfft), np.complex)
        symbols[:,self.format.dataSubcarriers] = dataSubcarriers
        symbols[:,self.format.pilotSubcarriers] = self.format.pilotTemplate * np.array(list(util.truncate(pilotPolarity, Ns)))[:,np.newaxis]
        return np.tile(np.fft.ifft(symbols), (1,3))[:,self.format.nfft-self.format.ncp:2*self.format.nfft+1]
    def encode(self, signal_subcarriers, data_subcarriers):
        pilotPolarity = self.pilotPolarity()
        signal_output = self.encodeSymbols(signal_subcarriers[np.newaxis,:], pilotPolarity)
        data_output = self.encodeSymbols(data_subcarriers, pilotPolarity)
        return stitch(self.format.sts_time, self.format.lts_time, signal_output[0], *data_output)
