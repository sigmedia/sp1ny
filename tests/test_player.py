import threading
import time

import numpy as np
import pytest
import sounddevice as sd


class FakeStream:
    """Drive the player callback from a thread, as PortAudio would (without any audio device)"""

    def __init__(self, samplerate, device, channels, callback, finished_callback, **kwargs):
        self.callback, self.finished = callback, finished_callback

    def __enter__(self):
        def run():
            out = np.zeros((256, 1), dtype=np.float32)
            try:
                while True:
                    self.callback(out, 256, None, None)
                    time.sleep(0.0005)
            except sd.CallbackStop:
                pass
            self.finished()

        threading.Thread(target=run, daemon=True).start()
        return self

    def __exit__(self, *args):
        pass


def wait_until(condition, timeout=2.0):
    end = time.time() + timeout
    while not condition() and time.time() < end:
        time.sleep(0.005)
    return condition()


@pytest.fixture
def fake_audio(player, monkeypatch):
    monkeypatch.setattr(sd, "OutputStream", FakeStream)
    monkeypatch.setattr(sd, "check_output_settings", lambda **k: None)
    player.setWavData(np.zeros(16000 * 5, dtype=np.float32))
    yield player
    player.stop()
    wait_until(lambda: not player._is_playing)


def test_stop_while_paused(fake_audio):
    player = fake_audio
    player.play()
    assert wait_until(lambda: player.position > 0)
    player.pauseResume()
    time.sleep(0.02)
    paused_at = player.position
    time.sleep(0.03)
    assert player.position == paused_at
    player.stop()
    assert wait_until(lambda: not player._is_playing)
    assert player.position == 0


def test_playback_is_resampled_only_when_needed(fake_audio, monkeypatch):
    player = fake_audio

    def only_48k(samplerate=None, **kwargs):
        if samplerate != 48000:
            raise sd.PortAudioError("unsupported rate")

    monkeypatch.setattr(sd, "check_output_settings", only_48k)
    monkeypatch.setattr(sd, "query_devices", lambda *a, **k: {"default_samplerate": 48000.0, "name": "fake"})
    player.play()
    assert player._play_rate == 48000 and player.sampling_rate == 16000
    assert wait_until(lambda: player.position > 0)


def test_fill_block_interpolates_linearly():
    from spiny.core.wav.player import Player

    source = np.arange(10, dtype=np.float32)[:, None]
    out = np.zeros((6, 1), dtype=np.float32)
    Player._fillBlock(out, source, 0.5, 2, 6)  # x2 upsampling, from played sample 2 (= source sample 1)
    assert out[:, 0].tolist() == [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    Player._fillBlock(out, source, 1.0, 4, 6)
    assert out[:, 0].tolist() == [4, 5, 6, 7, 8, 9]


def test_load_audio_mixes_down_to_mono(tmp_path):
    import soundfile as sf

    from spiny.core.wav.player import load_audio

    stereo = np.stack([np.ones(100), -np.ones(100) * 0.5], axis=1).astype(np.float32)
    sf.write(tmp_path / "s.wav", stereo, 8000, subtype="FLOAT")
    signal, rate = load_audio(tmp_path / "s.wav")
    assert rate == 8000 and signal.shape == (100, 1) and signal.dtype == np.float32
    assert np.allclose(signal, 0.25)


def test_unplayable_device_raises_and_resets(fake_audio, monkeypatch):
    def refuse(**kwargs):
        raise sd.PortAudioError("unsupported")

    monkeypatch.setattr(sd, "check_output_settings", refuse)
    monkeypatch.setattr(sd, "query_devices", lambda *a, **k: {"default_samplerate": 48000.0, "name": "fake"})
    with pytest.raises(sd.PortAudioError):
        fake_audio.play()
    assert not fake_audio._is_playing


def test_toolbar_without_output_device(qapp, monkeypatch):
    from spiny.core.wav import PlayerControllerWidget

    monkeypatch.setattr(sd, "query_devices", lambda *a, **k: [])
    monkeypatch.setattr(sd.default, "device", (-1, -1))
    widget = PlayerControllerWidget()
    assert not widget._bPlay.isEnabled()
