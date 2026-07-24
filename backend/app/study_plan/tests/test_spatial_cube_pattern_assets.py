#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import Counter
from xml.etree import ElementTree as ET

from backend.scripts.generate_spatial_cube_patterns import (
    build_assets,
    canonical_mask,
    canonical_masks,
    radial_svg,
    rotation_period,
)


def test_radial_masks_cover_all_non_empty_patterns() -> None:
    """米字组合代表应覆盖全部非空掩码。"""
    masks = canonical_masks()

    assert len(masks) == 69
    assert len(set(masks)) == 69
    assert all(canonical_mask(mask) in masks for mask in range(1, 256))
    assert all(rotation_period(mask) in {90, 180, 360} for mask in masks)


def test_generated_pattern_catalog_counts() -> None:
    """生成素材数量和编码应保持稳定。"""
    assets = [asset for asset, _ in build_assets()]
    category_counts = Counter(asset.category for asset in assets)

    assert len(assets) == 137
    assert len({asset.code for asset in assets}) == 137
    assert category_counts == {
        'digit': 10,
        'letter': 52,
        'radial': 69,
        'shape': 6,
    }


def test_radial_segments_reach_the_frame() -> None:
    """米字组合的八个线段应分别抵达边中点或四角。"""
    root = ET.fromstring(radial_svg(0xFF))
    endpoints = {
        (element.attrib['x2'], element.attrib['y2'])
        for element in root
        if element.tag.endswith('line')
    }

    assert endpoints == {
        ('128.000', '0.000'),
        ('256.000', '0.000'),
        ('256.000', '128.000'),
        ('256.000', '256.000'),
        ('128.000', '256.000'),
        ('0.000', '256.000'),
        ('0.000', '128.000'),
        ('0.000', '0.000'),
    }
