import struct
import math

class EnergyEngine:
    """
    An adaptive energy-based Voice Activity Detection class in pure Python.
    It tracks the noise floor, confirms speech over consecutive frames, 
    and detects speech ends through silence. 
    It runs without PyTorch for the Lite profile.
    """
    SAMPLE_RATE = 16000
    FRAME_SAMPLES = 512
    FRAME_BYTES = FRAME_SAMPLES * 2
    
    def __init__(self, min_speech_frames=3, min_silence_frames=20):
        # min_silence_frames=20 means 20 * 32ms = 640ms of silence to trigger end
        # min_speech_frames=3 means 3 * 32ms = 96ms of speech to trigger start
        self.min_speech_frames = min_speech_frames
        self.min_silence_frames = min_silence_frames
        
        # Adaptive noise floor settings
        self.noise_floor = 100.0
        self.speech_threshold_ratio = 2.5
        self.max_noise_floor = 1500.0
        self.min_noise_floor = 20.0
        
        self.reset()
        
    def reset(self):
        self.speech_frames = 0
        self.silence_frames = 0
        self.is_speaking = False
        
    def process(self, pcm16: bytes) -> dict | None:
        count = len(pcm16) // 2
        if count == 0:
            return None
            
        samples = struct.unpack(f'<{count}h', pcm16)
        
        # Use abs sum instead of squares to avoid overflow and for speed, 
        # or stick to RMS for standard energy. We'll use RMS for better accuracy.
        sum_squares = sum(float(s * s) for s in samples)
        rms = math.sqrt(sum_squares / count)
        
        # Adaptive noise floor tracking - only update when not speaking
        if not self.is_speaking:
            if rms < self.noise_floor:
                # Track downwards fast
                self.noise_floor = (self.noise_floor * 0.9) + (rms * 0.1)
            else:
                # Track upwards slow
                self.noise_floor = (self.noise_floor * 0.99) + (rms * 0.01)
                
            self.noise_floor = max(self.min_noise_floor, min(self.max_noise_floor, self.noise_floor))
        
        # Absolute minimum threshold to prevent breathing triggering it in total silence
        threshold = max(300.0, self.noise_floor * self.speech_threshold_ratio)
        frame_is_speech = rms > threshold
        
        if frame_is_speech:
            self.speech_frames += 1
            self.silence_frames = 0
        else:
            self.silence_frames += 1
            self.speech_frames = 0
            
        if not self.is_speaking:
            if self.speech_frames >= self.min_speech_frames:
                self.is_speaking = True
                return {"start": True}
        else:
            if self.silence_frames >= self.min_silence_frames:
                self.is_speaking = False
                # reset frames but keep the noise_floor state for continuous adaptation
                self.speech_frames = 0
                self.silence_frames = 0
                return {"end": True}
                
        return None
