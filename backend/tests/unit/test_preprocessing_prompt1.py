from __future__ import annotations

import hashlib
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image

from app.documents.preprocessing import (
    PROFILES,
    _rotation,
    map_bbox,
    photometric,
    preprocess_image,
    safe_crop,
    safe_perspective,
)


class OCRDouble:
    """Selection tests only: confidence doubles are NOT accuracy measurements."""
    def __init__(self, confidences=None, lengths=None):
        self.confidences = confidences or [.8]
        self.lengths = lengths or [100]
        self.calls = 0

    def image_to_blocks(self, image):
        index = min(self.calls,len(self.confidences)-1)
        length = self.lengths[min(self.calls,len(self.lengths)-1)]
        self.calls += 1
        return SimpleNamespace(blocks=[{"text":"X"*length,"bbox":[5,5,30,20],"confidence":self.confidences[index]}],
                               text="X"*length, backend="test-double",warnings=[],used_languages=["eng"])


def _page():
    # Deterministic source-content fixture, no generated characters/altered original.
    rgb = np.full((300,400,3),255,np.uint8)
    rgb[40:45,40:300] = 40
    rgb[90:95,40:300] = 40
    rgb[240:265,330:360] = [30,50,170]
    return Image.fromarray(rgb)


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_profiles_keep_original_and_candidate_pixels(profile,tmp_path):
    source = _page()
    original = source.tobytes()
    result = preprocess_image(source,OCRDouble(),tmp_path,profile=profile,orientation=False)
    assert source.tobytes() == original
    assert result.metadata["source_pixel_sha256"] == hashlib.sha256(original).hexdigest()
    assert result.metadata["PreprocessingQualityScore"]["cer"] is None
    assert result.metadata["PreprocessingQualityScore"]["wer"] is None
    assert result.metadata["PreprocessingQualityScore"]["validated"] is False
    assert all(r["authenticated"] is False for r in result.protected_visual_regions)
    assert (tmp_path/"selected.png").exists()


def test_score_drop_or_lost_text_reverts_to_original(tmp_path):
    result = preprocess_image(_page(),OCRDouble([.8,.5,.99],[100,100,60]),tmp_path,
                              profile="noisy_scan",orientation=False)
    assert result.metadata["selected_variant"] == "original"
    assert result.image.tobytes() == _page().tobytes()


def test_better_confidence_selects_version_without_claiming_accuracy(tmp_path):
    result = preprocess_image(_page(),OCRDouble([.8,.9,.85]),tmp_path,
                              profile="noisy_scan",orientation=False)
    assert result.metadata["selected_variant"] == "v01"
    assert result.metadata["PreprocessingQualityScore"]["improvement"] == pytest.approx(.1)
    actual = np.asarray(result.image)
    assert np.array_equal(actual[240:265,330:360],np.asarray(_page())[240:265,330:360])


@pytest.mark.parametrize("angle", [90,180,270,5,10,-3,1.8])
def test_rotation_expands_canvas_and_has_exact_inverse(angle):
    rgb = np.asarray(_page())
    rotated,matrix = _rotation(rgb,angle)
    assert abs(np.linalg.det(matrix)) > .99
    points = np.array([[0,0,1],[400,300,1],[40,50,1]])
    assert np.allclose((points @ matrix.T) @ np.linalg.inv(matrix).T,points)
    assert rotated.size >= rgb.size*.99


def test_bbox_uses_all_four_corners():
    _,matrix = _rotation(np.asarray(_page()),7)
    bbox = map_bbox([20,30,100,80],matrix,500,500)
    assert bbox[2]-bbox[0] > 80
    assert bbox[3]-bbox[1] > 50


def test_crop_keeps_text_and_edge_protected_signature():
    image = np.asarray(_page())
    protected = [{"bbox":[0,270,10,299]}]
    cropped,matrix = safe_crop(image,protected)
    inverse = np.linalg.inv(matrix)
    bbox = map_bbox([0,0,cropped.shape[1],cropped.shape[0]],inverse,400,300)
    assert bbox[0] == 0
    assert bbox[3] == 300
    assert bbox[2] >= 360


@pytest.mark.parametrize("method", ["median","gaussian","bilateral","non_local_means","morphological",
    "background_normalization","clahe","histogram_equalization","sharpen","otsu","adaptive_gaussian","adaptive_mean"])
def test_photometric_methods_are_copies_and_bounded(method):
    source = np.array(_page())
    before = source.copy()
    candidate = photometric(source,method)
    assert np.array_equal(source,before)
    assert candidate.shape == source.shape
    assert candidate.dtype == np.uint8


def test_perspective_refuses_content_outside_document():
    rgb = np.full((500,500,3),255,np.uint8)
    cv2.polylines(rgb,[np.array([[70,30],[410,70],[390,470],[50,450]])],True,(0,0,0),2)
    rgb[10:20,10:20] = 0
    assert safe_perspective(rgb,[]) is None


def test_perspective_four_corners_when_safe():
    rgb = np.full((500,500,3),255,np.uint8)
    cv2.polylines(rgb,[np.array([[70,30],[410,70],[390,470],[50,450]])],True,(0,0,0),2)
    result = safe_perspective(rgb,[])
    assert result is not None
    corrected,matrix = result
    assert corrected.shape[0] > 350
    assert np.allclose(matrix @ np.linalg.inv(matrix),np.eye(3))


def test_pixel_limit_and_invalid_profile_fail_closed(tmp_path):
    with pytest.raises(ValueError,match="profile"):
        preprocess_image(_page(),OCRDouble(),tmp_path,profile="random")
    with pytest.raises(ValueError,match="PIXEL_LIMIT"):
        preprocess_image(Image.new("L",(5000,5000)),OCRDouble(),tmp_path)


def test_protected_region_outside_source_rejected(tmp_path):
    with pytest.raises(ValueError,match="outside"):
        preprocess_image(_page(),OCRDouble(),tmp_path,protected_regions=[{"page":1,"bbox":[0,0,999,999]}])
