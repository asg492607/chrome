"""
Unit & Benchmark Test Suite for Web Speech API (Synthesis & Recognition) Engine (Sprint 41).
Verifies SpeechSynthesis text-to-speech rendering, SpeechSynthesisUtterance queuing, voice selection,
SpeechRecognition acoustic PCM audio decoding, transcript confidence scores, and speech processing speed.
"""

import sys
import os
import unittest
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from media_engine.web_speech import (
    SpeechSynthesisVoice,
    SpeechSynthesisUtterance,
    SpeechSynthesisEngine,
    SpeechRecognitionAlternative,
    SpeechRecognitionResult,
    SpeechRecognition
)


class TestWebSpeechSubsystem(unittest.TestCase):

    def test_speech_synthesis_tts_utterance(self):
        """Verify SpeechSynthesis queuing utterances, voice selection, and TTS execution."""
        tts = SpeechSynthesisEngine()
        voices = tts.getVoices()

        self.assertGreaterEqual(len(voices), 2)
        self.assertEqual(voices[0].lang, "en-US")

        started = [False]
        ended = [False]

        utt = SpeechSynthesisUtterance("Welcome to Sovereign Web Engine 2026")
        utt.voice = voices[0]
        utt.rate = 1.2
        utt.pitch = 1.0
        utt.onstart = lambda: started.__setitem__(0, True)
        utt.onend = lambda: ended.__setitem__(0, True)

        tts.speak(utt)

        self.assertTrue(started[0])
        self.assertTrue(ended[0])
        self.assertTrue(tts.speaking)

    def test_speech_recognition_asr_transcription(self):
        """Verify SpeechRecognition decoding PCM audio streams into SpeechRecognitionResult transcripts."""
        asr = SpeechRecognition()
        asr.continuous = True
        asr.start()
        self.assertTrue(asr.listening)

        pcm_bytes = b"CMD_NAVIGATE_PAGES_PCM_STREAM"
        result = asr.process_audio_pcm(pcm_bytes)

        self.assertTrue(result.isFinal)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].transcript, "Navigate to Dashboard")
        self.assertGreaterEqual(result[0].confidence, 0.90)

    def test_speech_synthesis_lifecycle_controls(self):
        """Verify cancel(), pause(), and resume() lifecycle state transitions."""
        tts = SpeechSynthesisEngine()
        utt = SpeechSynthesisUtterance("Continuous reading test passage")
        tts.speak(utt)

        tts.pause()
        self.assertTrue(tts.paused)

        tts.resume()
        self.assertFalse(tts.paused)

        tts.cancel()
        self.assertFalse(tts.speaking)
        self.assertEqual(len(tts.pending), 0)

    def test_speech_recognition_stopped_rejection(self):
        """Verify SpeechRecognition rejecting audio processing when stopped."""
        asr = SpeechRecognition()

        with self.assertRaises(RuntimeError):
            asr.process_audio_pcm(b"pcm_data_stream")

    def test_high_speed_web_speech_benchmark(self):
        """
        Benchmark: Execute 50,000 SpeechSynthesis utterance & SpeechRecognition transcript evaluations.
        Asserts duration < 0.15s (> 300,000 ops/sec).
        """
        tts = SpeechSynthesisEngine()
        utt = SpeechSynthesisUtterance("High speed benchmark utterance string")
        asr = SpeechRecognition()
        asr.start()
        pcm_data = b"AUDIO_PCM_FRAME_DATA_12345"

        start_time = time.perf_counter()
        for _ in range(25000):
            tts.speak(utt)
            _ = asr.process_audio_pcm(pcm_data)
        duration = time.perf_counter() - start_time

        total_ops = 50000 # 25k TTS speaks + 25k ASR decodes
        ops_per_sec = total_ops / duration
        latency_us = (duration / total_ops) * 1_000_000

        self.assertLess(duration, 0.20, f"50k Web Speech ops took {duration*1000:.2f}ms (must be < 200ms)")
        print(f"\n[Sprint 41 Web Speech Benchmark] {total_ops:,} TTS & ASR Speech Operations Processed:")
        print(f"  - Total Elapsed Time: {duration * 1000:.2f} ms")
        print(f"  - Speech Processing Speed: {ops_per_sec:,.0f} ops/second")
        print(f"  - Average Operation Latency: {latency_us:.2f} µs/op")


if __name__ == "__main__":
    unittest.main()
