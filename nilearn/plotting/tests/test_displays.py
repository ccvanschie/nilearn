# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
import tempfile

import numpy as np
import matplotlib.pyplot as plt

from nilearn.plotting.displays import OrthoSlicer, XSlicer, OrthoProjector
from nilearn.plotting.displays import check_threshold
from nilearn.datasets import load_mni152_template
from nilearn._utils.testing import assert_raises_regex


###############################################################################
# Some smoke testing for graphics-related code

def test_demo_ortho_slicer():
    # This is only a smoke test
    oslicer = OrthoSlicer(cut_coords=(0, 0, 0))
    img = load_mni152_template()
    oslicer.add_overlay(img, cmap=plt.cm.gray)
    oslicer.close()


def test_stacked_slicer():
    # Test stacked slicers, like the XSlicer
    img = load_mni152_template()
    slicer = XSlicer.init_with_figure(img=img, cut_coords=3)
    slicer.add_overlay(img, cmap=plt.cm.gray)
    # Forcing a layout here, to test the locator code
    with tempfile.TemporaryFile() as fp:
        slicer.savefig(fp)
    slicer.close()


def test_demo_ortho_projector():
    # This is only a smoke test
    img = load_mni152_template()
    oprojector = OrthoProjector.init_with_figure(img=img)
    oprojector.add_overlay(img, cmap=plt.cm.gray)
    with tempfile.TemporaryFile() as fp:
        oprojector.savefig(fp)
    oprojector.close()


# Smoke test to check threshold function for plot connectome
def test_threshold_plot_connectome():
    adjacency_matrix = np.array([[1., 2.],
                                 [2., 1.]])
    name = 'edge_threshold'
    calculate = 'fast_abs_percentile'
    # a few not correctly formatted strings for 'edge_threshold'
    wrong_edge_thresholds = ['0.1', '10', '10.2.3%', 'asdf%']
    for wrong_edge_threshold in wrong_edge_thresholds:
        assert_raises_regex(ValueError,
                            'should be a number followed by the percent sign',
                            check_threshold,
                            wrong_edge_threshold, adjacency_matrix,
                            calculate, name)

    threshold = object()
    assert_raises_regex(TypeError,
                        'should be either a number or a string',
                        check_threshold,
                        threshold, adjacency_matrix,
                        calculate, name)
