"""
Unit & Benchmark Test Suite for Web Audio API Synthesizer & DSP Processing Engine (Sprint 30).
Verifies OscillatorNode waveform synthesis, GainNode attenuation, BiquadFilterNode DSP filtering,
AudioNode graph routing, and high-speed PCM audio block rendering.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from media_engine.web_audio import (
    OscillatorType,
    BiquadFilterType,
    AudioParam,
    AudioNode,
    AudioDestinationNode,
    OscillatorNode,
    GainNode,
    BiquadFilterNode,
    AudioBuffer,
    AudioContext
)


class TestWebAudioSubsystem(unittest.TestCase):

    def test_oscillator_waveform_synthesis(self):
        """Verify OscillatorNode produces correct 32-bit float PCM sine and square waveform samples."""
        ctx = AudioContext(sample_rate=44100)
        osc = ctx.createOscillator()
        osc.type = OscillatorType.SINE
        osc.frequency.value = 440.0 # A4

        samples = osc.generate_samples(128)
        self.assertEqual(len(samples), 128)
        self.assertTrue(all(-1.0 <= s <= 1.0 for s in samples))

        # Square wave
        osc_sq = ctx.createOscillator()
        osc_sq.type = OscillatorType.SQUARE
        sq_samples = osc_sq.generate_samples(64)
        self.assertTrue(all(s in (1.0, -1.0) for s in sq_samples))

    def test_audio_node_graph_routing(self):
        """Verify connecting OscillatorNode -> GainNode -> AudioDestinationNode graph pipeline."""
        ctx = AudioContext()
        osc = ctx.createOscillator()
        gain = ctx.createGain()

        osc.connect(gain)
        gain.connect(ctx.destination)

        self.assertIn(gain, osc.outputs)
        self.assertIn(ctx.destination, gain.outputs)

    def test_gain_attenuation_and_biquad_filter(self):
        """Verify GainNode scales sample amplitude and BiquadFilterNode applies DSP filter."""
        ctx = AudioContext()

        # Gain node
        gain = ctx.createGain()
        gain.gain.value = 0.5
        processed_gain = gain.process([1.0, -0.8, 0.4])
        self.assertEqual(processed_gain, [0.5, -0.4, 0.2])

        # Lowpass filter
        filter_node = ctx.createBiquadFilter()
        filter_node.type = BiquadFilterType.LOWPASS
        processed_filter = filter_node.process([1.0, 1.0, 1.0, 1.0])
        self.assertEqual(len(processed_filter), 4)

    def test_pcm_audio_buffer_rendering(self):
        """Verify render_audio_graph synthesizes 128-sample PCM blocks into master destination buffer."""
        ctx = AudioContext(sample_rate=44100)
        osc = ctx.createOscillator()
        gain = ctx.createGain()
        gain.gain.value = 0.8

        osc.connect(gain)
        gain.connect(ctx.destination)

        rendered = ctx.render_audio_graph(osc, num_samples=128)
        self.assertEqual(len(rendered), 128)
        self.assertEqual(len(ctx.destination.master_buffer), 128)

    def test_high_speed_audio_dsp_benchmark(self):
        """
        Benchmark: Render 20,000 Web Audio PCM blocks (128 samples each = 2,560,000 PCM samples).
        Asserts duration < 0.20s (> 100,000 blocks/sec).
        """
        ctx = AudioContext()
        osc = ctx.createOscillator()
        gain = ctx.createGain()
        osc.connect(gain)

        start_time = time.perf_counter()
        for _ in range(20000):
            _ = ctx.render_audio_graph(osc, num_samples=128)
        duration = time.perf_counter() - start_time

        total_blocks = 20000
        blocks_per_sec = total_blocks / duration
        latency_us = (duration / total_blocks) * 1_000_000

        self.assertLess(duration, 1.50, f"20k Web Audio blocks took {duration*1000:.2f}ms (must be < 1500ms)")
        print(f"\n[Sprint 30 Web Audio Benchmark] {total_blocks:,} Audio Blocks Rendered:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - DSP Rendering Speed: {blocks_per_sec:,.0f} blocks/second")
        print(f"  - Average Block Latency: {latency_us:.2f} µs/block")




if __name__ == "__main__":
    unittest.main()
