import numpy as np
import pytest

from spiny.overlays.mask.extractor import load_mask, mask_image


def save(tmp_path, array, **kwargs):
    filename = tmp_path / "mask.npy"
    np.save(filename, array, **kwargs)
    return filename


@pytest.mark.parametrize(
    "array, message",
    [
        (np.ones(10), "matrix"),
        (np.ones((2, 2, 2)), "matrix"),
        (np.zeros((0, 3)), "empty"),
        (np.array([["a", "b"]]), "numbers"),
        (np.ones((2, 2)) * 1.5, "between 0 and 1"),
        (-np.ones((2, 2)), "between 0 and 1"),
        (np.full((2, 2), np.nan), "between 0 and 1"),
    ],
)
def test_invalid_masks_are_refused(tmp_path, array, message):
    with pytest.raises(ValueError, match=message):
        load_mask(save(tmp_path, array))


def test_pickled_data_is_never_read(tmp_path):
    filename = save(tmp_path, np.array([[object()]], dtype=object), allow_pickle=True)
    with pytest.raises(ValueError):
        load_mask(filename)


def test_a_file_which_is_not_numpy_is_refused(tmp_path):
    filename = tmp_path / "mask.npy"
    filename.write_bytes(b"not numpy at all")
    with pytest.raises((ValueError, OSError)):
        load_mask(filename)


def test_mask_is_memory_mapped(tmp_path):
    assert isinstance(load_mask(save(tmp_path, np.zeros((4, 5), dtype=np.float32))), np.memmap)


@pytest.mark.parametrize(
    "array", [np.array([[0.0, 1.0]]), np.array([[0, 1]], dtype=np.uint8), np.array([[False, True]])]
)
def test_every_kind_of_number_can_be_used(tmp_path, array):
    assert load_mask(save(tmp_path, array)).shape == (1, 2)


@pytest.mark.core
def test_image_hides_according_to_the_opacity():
    mask = np.array([[1.0, 0.0], [0.5, 0.25]], dtype=np.float32)
    image = mask_image(mask, 0, 2, 1, 1, (10, 20, 30), 1.0)
    assert image.shape == (2, 2, 4) and image.dtype == np.uint8
    assert image[0, 0].tolist() == [10, 20, 30, 0]  # fully visible
    assert image[0, 1].tolist() == [10, 20, 30, 255]  # hidden
    assert image[1, 0, 3] == 128 and image[1, 1, 3] == 191


def test_image_strength_invert_and_strides():
    mask = np.zeros((8, 6), dtype=np.float32)
    assert (mask_image(mask, 0, 8, 1, 1, (0, 0, 0), 0.5)[..., 3] == 128).all()
    assert (mask_image(mask, 0, 8, 1, 1, (0, 0, 0), 1.0, invert=True)[..., 3] == 0).all()
    assert mask_image(mask, 2, 8, 2, 3, (0, 0, 0), 1.0).shape == (3, 2, 4)
