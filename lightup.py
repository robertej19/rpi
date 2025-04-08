import sounddevice as sd
import numpy as np
import scipy.fftpack as fftpack
from rpi_ws281x import Adafruit_NeoPixel, Color

# === LED Configuration ===
LED_COUNT = 32
LED_PIN = 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 50
LED_INVERT = False

strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ,
                          LED_DMA, LED_INVERT, LED_BRIGHTNESS)
strip.begin()

# === Audio Configuration ===
samplerate = 44100
block_duration = 0.025
blocksize = int(samplerate * block_duration)

# === Visualizer Parameters ===
MAX_FREQ = 1000
FADE_DECAY = 0.5
MAX_BRIGHTNESS = 100

# Track brightness levels per LED
led_levels = [0.0] * LED_COUNT

def wheel(pos):
    pos = 255 - pos
    if pos < 85:
        return (255 - pos * 3, 0, pos * 3)
    if pos < 170:
        pos -= 85
        return (0, pos * 3, 255 - pos * 3)
    pos -= 170
    return (pos * 3, 255 - pos * 3, 0)

def update_leds_top5(magnitude, freqs):
    global led_levels

    num_leds = strip.numPixels()
    freq_step = MAX_FREQ / num_leds

    magnitude[0] = 0  # Remove DC offset

    if np.max(magnitude) == 0:
        return

    magnitude = magnitude / np.max(magnitude)

    # Get the center frequency and band index for each LED
    levels = np.zeros(num_leds)
    for i in range(num_leds):
        f_start = i * freq_step
        f_end = (i + 1) * freq_step
        band = magnitude[(freqs >= f_start) & (freqs < f_end)]
        levels[i] = np.mean(band) if len(band) else 0.0

    # Get top 5 LED indices with highest intensity
    top_indices = np.argpartition(levels, -6)[-6:]
    top_indices = top_indices[np.argsort(levels[top_indices])[::-1]]  # sorted descending

    # Normalize the top levels for relative brightness
    max_top_level = levels[top_indices[0]] if levels[top_indices[0]] > 0 else 1
    relative_levels = {i: levels[i] / max_top_level for i in top_indices}

    # Update LED levels with fading
    for i in range(num_leds):
        if i in relative_levels:
            target_level = relative_levels[i]
            led_levels[i] = max(led_levels[i], target_level)
        else:
            led_levels[i] *= FADE_DECAY
            if led_levels[i] < 0.01:
                led_levels[i] = 0.0

        # Set color and brightness
        base_color = wheel(int(i * 256 / num_leds))
        r = min(int(base_color[0] * led_levels[i]), MAX_BRIGHTNESS)
        g = min(int(base_color[1] * led_levels[i]), MAX_BRIGHTNESS)
        b = min(int(base_color[2] * led_levels[i]), MAX_BRIGHTNESS)

        strip.setPixelColor(i, Color(r, g, b))

    strip.show()

def audio_callback(indata, frames, time, status):
    audio_data = indata[:, 0] * np.hanning(len(indata))
    fft_data = fftpack.fft(audio_data)
    fft_freq = fftpack.fftfreq(len(audio_data), 1.0 / samplerate)
    magnitude = np.abs(fft_data[:len(fft_data)//2])
    freqs = fft_freq[:len(fft_freq)//2]

    update_leds_top5(magnitude, freqs)

def main():
    print("Top 5 frequency bands with fade-out effect. Ctrl+C to exit.")
    try:
        with sd.InputStream(device=0,
                            channels=1,
                            samplerate=samplerate,
                            blocksize=blocksize,
                            callback=audio_callback):
            while True:
                sd.sleep(10)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()

if __name__ == "__main__":
    main() 
