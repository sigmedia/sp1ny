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


def test_stop_returns_to_the_cursor(fake_audio):
    player = fake_audio
    player.seek(2.0)
    assert player.position == 2.0
    player.play()
    assert wait_until(lambda: player.position > 2.0)
    player.stop()
    assert player.position == 2.0


def test_seek_during_playback_jumps(fake_audio):
    player = fake_audio
    player.play()
    player.seek(4.0)
    assert wait_until(lambda: player.position >= 4.0)
    player.stop()
    assert player.position == 4.0


def test_seek_is_clipped_and_play_from_the_end_starts_over(fake_audio):
    player = fake_audio
    player.seek(-1.0)
    assert player.position == 0
    player.seek(100.0)
    assert player.position == player.duration
    player.play()
    assert player._position < 16000


def test_play_right_after_stop_keeps_playing(fake_audio):
    player = fake_audio
    player.play()
    player.stop()
    player.play()
    time.sleep(0.05)
    assert player.is_playing
    assert sum(thread.name == "spiny-player" for thread in threading.enumerate()) == 1


def test_loop_of_a_part_restarts_at_its_start(fake_audio):
    player = fake_audio
    player.toggleLoop()
    try:
        player.play(start=1.0, end=1.1)
        positions = [player.position for _ in range(200) if not time.sleep(0.001)]
    finally:
        player.toggleLoop()
    assert min(positions) >= 1.0 and max(positions) <= 1.1
    assert any(after < before for before, after in zip(positions, positions[1:]))


def test_speed_changes_how_fast_the_position_moves(fake_audio, monkeypatch):
    player = fake_audio
    streams = []

    class ManualStream:
        """A stream whose callback is only called by the test"""

        def __init__(self, callback, finished_callback, **kwargs):
            self.callback, self.finished = callback, finished_callback
            streams.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(sd, "OutputStream", ManualStream)
    out = np.zeros((256, 1), dtype=np.float32)
    player.play()
    assert wait_until(lambda: streams)
    streams[0].callback(out, 256, None, None)
    assert player.position == 256 / player.sampling_rate
    player.speed = 2.0
    try:
        streams[0].callback(out, 256, None, None)
        assert player.position == (256 + 512) / player.sampling_rate
    finally:
        player.speed = 1.0
        player.stop()
        streams[0].finished()


def test_playback_at_double_speed_reads_every_other_sample():
    from spiny.core.wav.player import Player

    source = np.arange(8, dtype=np.float32)[:, None]
    out = np.zeros((4, 1), dtype=np.float32)
    Player._fillBlock(out, source, 0.0, 2.0, 4)
    assert out[:, 0].tolist() == [0, 2, 4, 6]


def test_mute_silences_without_touching_the_volume(fake_audio, monkeypatch):
    player = fake_audio
    player.setWavData(np.ones(16000, dtype=np.float32))
    played = []

    class Recording(FakeStream):
        def __init__(self, samplerate, device, channels, callback, finished_callback, **kwargs):
            def recording(out, frames, time_info, status):
                callback(out, frames, time_info, status)
                played.append(float(np.abs(out).max()))

            super().__init__(samplerate, device, channels, recording, finished_callback, **kwargs)

    monkeypatch.setattr(sd, "OutputStream", Recording)
    player.muted = True
    try:
        player.play()
        assert wait_until(lambda: len(played) > 5)
        assert max(played) == 0.0 and player.volume == 1.0
    finally:
        player.muted = False


def test_speed_buttons_stop_at_the_ends(fake_audio, qapp, monkeypatch):
    from spiny.core.wav import TransportWidget

    monkeypatch.setattr(sd, "query_devices", lambda *a, **k: [{"name": "fake", "max_output_channels": 2}])
    monkeypatch.setattr(sd.default, "device", (-1, 0))
    widget = TransportWidget()
    try:
        for _ in range(20):
            widget._bFaster.click()
        assert fake_audio.speed == TransportWidget.SPEEDS[-1]
        for _ in range(20):
            widget._bSlower.click()
        assert fake_audio.speed == TransportWidget.SPEEDS[0]
    finally:
        fake_audio.speed = 1.0


def test_skip_buttons_move_the_cursor(fake_audio, qapp, monkeypatch):
    from spiny.core.wav import TransportWidget

    monkeypatch.setattr(sd, "query_devices", lambda *a, **k: [{"name": "fake", "max_output_channels": 2}])
    monkeypatch.setattr(sd.default, "device", (-1, 0))
    widget = TransportWidget()
    fake_audio.seek(0.0)
    widget._bForward.click()
    assert fake_audio.position == TransportWidget.SKIP_SECONDS
    widget._bRewind.click()
    assert fake_audio.position == 0
    widget._bEnd.click()
    assert fake_audio.position == fake_audio.duration


def test_format_time():
    from spiny.core.wav.control import format_time

    assert format_time(0) == "00:00.000"
    assert format_time(83.4567) == "01:23.457"


def test_toolbar_play_button_toggles(fake_audio, qapp, monkeypatch):
    from spiny.core.wav import TransportWidget

    monkeypatch.setattr(sd, "query_devices", lambda *a, **k: [{"name": "fake", "max_output_channels": 2}])
    monkeypatch.setattr(sd.default, "device", (-1, 0))
    widget = TransportWidget()
    widget._bPlay.click()
    assert fake_audio.is_playing and not fake_audio.is_paused
    widget._bPlay.click()
    assert fake_audio.is_playing and fake_audio.is_paused
    widget._bPlay.click()
    assert not fake_audio.is_paused
    widget._bStop.click()
    assert not fake_audio.is_playing


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
    Player._fillBlock(out, source, 1.0, 0.5, 6)  # x2 upsampling, from source sample 1
    assert out[:, 0].tolist() == [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    Player._fillBlock(out, source, 4.0, 1.0, 6)
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
    from spiny.core.wav import OutputWidget, TransportWidget

    monkeypatch.setattr(sd, "query_devices", lambda *a, **k: [])
    monkeypatch.setattr(sd.default, "device", (-1, -1))
    assert not TransportWidget()._bPlay.isEnabled()
    assert not OutputWidget()._boxDevices.isEnabled()
