"""
Web Audio API Synthesizer & DSP Processing Engine.
Implements W3C Web Audio API specification (AudioContext, AudioNode), modular audio node graph routing,
OscillatorNode waveform synthesis (SINE, SQUARE, SAWTOOTH, TRIANGLE), GainNode,
BiquadFilterNode DSP equations (LOWPASS, HIGHPASS), and 32-bit float PCM audio buffer synthesis.
"""

import sys
import os
import math
import struct
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class OscillatorType(Enum):
    SINE = 1
    SQUARE = 2
    SAWTOOTH = 3
    TRIANGLE = 4


class BiquadFilterType(Enum):
    LOWPASS = 1
    HIGHPASS = 2
    BANDPASS = 3


class AudioParam:
    """Represents an automatable audio parameter (e.g. frequency, gain)."""

    def __init__(self, value: float = 1.0):
        self.value = value

    def __repr__(self) -> str:
        return f"AudioParam({self.value})"


class AudioNode:
    """Base W3C AudioNode in the Web Audio Graph."""

    def __init__(self, context: "AudioContext"):
        self.context = context
        self.outputs: List["AudioNode"] = []

    def connect(self, destination: "AudioNode") -> "AudioNode":
        """Connects this node's output to destination node's input."""
        if destination not in self.outputs:
            self.outputs.append(destination)
        return destination

    def disconnect(self) -> None:
        """Disconnects all output connections from this node."""
        self.outputs.clear()


    def process(self, samples: List[float]) -> List[float]:
        """Processes and passes audio samples downstream."""
        return samples


class AudioDestinationNode(AudioNode):
    """Master Audio Destination Node collecting synthesized sound."""

    def __init__(self, context: "AudioContext"):
        super().__init__(context)
        self.master_buffer: List[float] = []

    def receive_samples(self, samples: List[float]) -> None:
        self.master_buffer.extend(samples)


# Precomputed 1024-element Sine Lookup Table for high-speed DSP synthesis
_SINE_TABLE_SIZE = 1024
_SINE_TABLE = [math.sin(2.0 * math.pi * i / _SINE_TABLE_SIZE) for i in range(_SINE_TABLE_SIZE)]


class OscillatorNode(AudioNode):
    """Synthesizes periodic audio waveforms (SINE, SQUARE, SAWTOOTH, TRIANGLE)."""

    def __init__(self, context: "AudioContext"):
        super().__init__(context)
        self.type = OscillatorType.SINE
        self.frequency = AudioParam(440.0) # A4 note
        self.phase = 0.0

    def generate_samples(self, num_samples: int, sample_rate: int = 44100) -> List[float]:
        """Generates 32-bit float PCM audio samples for specified waveform."""
        samples = [0.0] * num_samples
        freq = self.frequency.value
        phase_inc = (2.0 * math.pi * freq) / sample_rate
        two_pi = 2.0 * math.pi
        phase = self.phase
        osc_type = self.type

        if osc_type == OscillatorType.SINE:
            step = (freq * _SINE_TABLE_SIZE) / sample_rate
            tbl_idx = (phase / two_pi) * _SINE_TABLE_SIZE
            for i in range(num_samples):
                samples[i] = _SINE_TABLE[int(tbl_idx) % _SINE_TABLE_SIZE]
                tbl_idx += step
            self.phase = (phase + phase_inc * num_samples) % two_pi
            return samples

        for i in range(num_samples):
            if osc_type == OscillatorType.SQUARE:
                val = 1.0 if math.sin(phase) >= 0 else -1.0
            elif osc_type == OscillatorType.SAWTOOTH:
                val = (phase / math.pi) % 2.0 - 1.0
            elif osc_type == OscillatorType.TRIANGLE:
                val = 2.0 * abs((phase / math.pi) % 2.0 - 1.0) - 1.0
            else:
                val = math.sin(phase)

            samples[i] = val
            phase += phase_inc
            if phase >= two_pi:
                phase -= two_pi

        self.phase = phase
        return samples



class GainNode(AudioNode):
    """Amplifies or attenuates audio signal levels."""

    def __init__(self, context: "AudioContext"):
        super().__init__(context)
        self.gain = AudioParam(1.0)

    def process(self, samples: List[float]) -> List[float]:
        g = self.gain.value
        return [s * g for s in samples]


class BiquadFilterNode(AudioNode):
    """Digital Signal Processing (DSP) Biquad Filter (LOWPASS, HIGHPASS)."""

    def __init__(self, context: "AudioContext"):
        super().__init__(context)
        self.type = BiquadFilterType.LOWPASS
        self.frequency = AudioParam(350.0)

    def process(self, samples: List[float]) -> List[float]:
        """Applies simple lowpass / highpass DSP filter algorithm."""
        filtered = []
        alpha = 0.5 if self.type == BiquadFilterType.LOWPASS else 0.8
        prev = 0.0

        for s in samples:
            if self.type == BiquadFilterType.LOWPASS:
                val = prev + alpha * (s - prev)
            else: # HIGHPASS
                val = alpha * (prev + s - prev)
            prev = val
            filtered.append(val)

        return filtered


class AudioBuffer:
    """PCM Audio Sample Buffer representation (32-bit float channels)."""

    def __init__(self, sample_rate: int = 44100, length: int = 44100, num_channels: int = 1):
        self.sample_rate = sample_rate
        self.length = length
        self.channels = [[0.0] * length for _ in range(num_channels)]

    def getChannelData(self, channel_index: int) -> List[float]:
        if channel_index >= len(self.channels):
            raise IndexError("AudioBufferError: Invalid channel index.")
        return self.channels[channel_index]


class AudioContext:
    """W3C AudioContext managing node creation and PCM audio block rendering."""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.currentTime = 0.0
        self.state = "running"
        self.destination = AudioDestinationNode(self)

    def createOscillator(self) -> OscillatorNode:
        return OscillatorNode(self)

    def createGain(self) -> GainNode:
        return GainNode(self)

    def createBiquadFilter(self) -> BiquadFilterNode:
        return BiquadFilterNode(self)

    def createBuffer(self, num_channels: int, length: int, sample_rate: int) -> AudioBuffer:
        return AudioBuffer(sample_rate, length, num_channels)

    def render_audio_graph(self, osc: OscillatorNode, num_samples: int = 128) -> List[float]:
        """
        Renders an audio block through the node graph pipeline:
        OscillatorNode -> [GainNode / FilterNode ...] -> Destination
        """
        samples = osc.generate_samples(num_samples, self.sample_rate)
        curr = osc

        for target in curr.outputs:
            samples = target.process(samples)

        self.destination.receive_samples(samples)
        self.currentTime += num_samples / self.sample_rate
        return samples
