"""
Conversion utilities.
"""
# Author: Gael Varoquaux, Alexandre Abraham, Philippe Gervais
# License: simplified BSD
import warnings

import numpy as np
import itertools
from sklearn.externals.joblib import Memory

from .cache_mixin import cache
from .niimg import _safe_get_data, load_niimg, new_img_like
from .compat import _basestring, izip
from .exceptions import DimensionError


def _check_fov(img, affine, shape):
    """ Return True if img's field of view correspond to given
        shape and affine, False elsewhere.
    """
    img = check_niimg(img)
    return (img.shape[:3] == shape and
            np.allclose(img.get_affine(), affine))


def _check_same_fov(img1, img2):
    """ Return True if img1 and img2 have the same field of view
        (shape and affine), False elsewhere.
    """
    img1 = check_niimg(img1)
    img2 = check_niimg(img2)
    return (img1.shape[:3] == img2.shape[:3]
            and np.allclose(img1.get_affine(), img2.get_affine()))


def _index_img(img, index):
    """Helper function for check_niimg_4d."""
    return new_img_like(
        img, img.get_data()[:, :, :, index], img.get_affine(),
        copy_header=True)


def _iter_check_niimg(niimgs, ensure_ndim=None, atleast_4d=False,
                      target_fov=None,
                      memory=Memory(cachedir=None),
                      memory_level=0, verbose=0):
    """Iterate over a list of niimgs and do sanity checks and resampling

    Parameters
    ----------

    niimgs: list of niimg
        Image to iterate over

    ensure_ndim: integer, optional
        If specified, an error is raised if the data does not have the
        required dimension.

    atleast_4d: boolean, optional
        If True, any 3D image is converted to a 4D single scan.

    target_fov: tuple of affine and shape
       If specified, images are resampled to this field of view
    """
    ref_fov = None
    resample_to_first_img = False
    ndim_minus_one = ensure_ndim - 1 if ensure_ndim is not None else None
    if target_fov is not None and target_fov != "first":
        ref_fov = target_fov
    for i, niimg in enumerate(niimgs):
        try:
            niimg = check_niimg(
                niimg, ensure_ndim=ndim_minus_one, atleast_4d=atleast_4d)
            if i == 0:
                ndim_minus_one = len(niimg.shape)
                if ref_fov is None:
                    ref_fov = (niimg.get_affine(), niimg.shape[:3])
                    resample_to_first_img = True

            if not _check_fov(niimg, ref_fov[0], ref_fov[1]):
                if target_fov is not None:
                    from nilearn import image  # we avoid a circular import
                    if resample_to_first_img:
                        warnings.warn('Affine is different across subjects.'
                                      ' Realignement on first subject '
                                      'affine forced')
                    niimg = cache(
                        image.resample_img, memory, func_memory_level=2,
                        memory_level=memory_level)(
                            niimg, target_affine=ref_fov[0],
                            target_shape=ref_fov[1])
                else:
                    raise ValueError(
                        "Field of view of image #%d is different from "
                        "reference FOV.\n"
                        "Reference affine:\n%r\nImage affine:\n%r\n"
                        "Reference shape:\n%r\nImage shape:\n%r\n"
                        % (i, ref_fov[0], niimg.get_affine(), ref_fov[1],
                           niimg.shape))
            yield niimg
        except TypeError as exc:
            img_name = ''
            if isinstance(niimg, _basestring):
                img_name = " (%s) " % niimg

            exc.args = (('Error encountered while loading image #%d%s'
                         % (i, img_name),) + exc.args)
            raise
        except DimensionError as exc:
            # Keep track of the additional dimension in the error
            exc.increment_stack_counter()
            raise


def check_niimg(niimg, ensure_ndim=None, atleast_4d=False,
                return_iterator=False):
    """Check that niimg is a proper 3D/4D niimg. Turn filenames into objects.

    Parameters
    ----------
    niimg: Niimg-like object
        See http://nilearn.github.io/building_blocks/manipulating_mr_images.html#niimg.
        If niimg is a string, consider it as a path to Nifti image and
        call nibabel.load on it. If it is an object, check if get_data()
        and get_affine() methods are present, raise TypeError otherwise.

    ensure_ndim: integer {3, 4}, optional
        Indicate the dimensionality of the expected niimg. An
        error is raised if the niimg is of another dimensionality.

    atleast_4d: boolean, optional
        Indicates if a 3d image should be turned into a single-scan 4d niimg.

    Returns
    -------
    result: 3D/4D Niimg-like object
        Result can be nibabel.Nifti1Image or the input, as-is. It is guaranteed
        that the returned object has get_data() and get_affine() methods.

    Notes
    -----
    In nilearn, special care has been taken to make image manipulation easy.
    This method is a kind of pre-requisite for any data processing method in
    nilearn because it checks if data have a correct format and loads them if
    necessary.

    Its application is idempotent.
    """

    # in case of an iterable
    if hasattr(niimg, "__iter__") and not isinstance(niimg, _basestring):
        if return_iterator:
            return _iter_check_niimg(niimg, ensure_ndim=ensure_ndim)
        return concat_niimgs(niimg, ensure_ndim=ensure_ndim)

    # Otherwise, it should be a filename or a SpatialImage, we load it
    niimg = load_niimg(niimg)

    if ensure_ndim == 3 and len(niimg.shape) == 4 and niimg.shape[3] == 1:
        # "squeeze" the image.
        data = _safe_get_data(niimg)
        affine = niimg.get_affine()
        niimg = new_img_like(niimg, data[:, :, :, 0], affine)
    if atleast_4d and len(niimg.shape) == 3:
        data = niimg.get_data().view()
        data.shape = data.shape + (1, )
        niimg = new_img_like(niimg, data, niimg.get_affine())

    if ensure_ndim is not None and len(niimg.shape) != ensure_ndim:
        raise DimensionError(len(niimg.shape), ensure_ndim)

    if return_iterator:
        return (_index_img(niimg, i) for i in range(niimg.shape[3]))

    return niimg


def check_niimg_3d(niimg):
    """Check that niimg is a proper 3D niimg-like object and load it.
    Parameters
    ----------
    niimg: Niimg-like object
        See http://nilearn.github.io/building_blocks/manipulating_mr_images.html#niimg.
        If niimg is a string, consider it as a path to Nifti image and
        call nibabel.load on it. If it is an object, check if get_data()
        and get_affine() methods are present, raise TypeError otherwise.

    Returns
    -------
    result: 3D Niimg-like object
        Result can be nibabel.Nifti1Image or the input, as-is. It is guaranteed
        that the returned object has get_data() and get_affine() methods.

    Notes
    -----
    In nilearn, special care has been taken to make image manipulation easy.
    This method is a kind of pre-requisite for any data processing method in
    nilearn because it checks if data have a correct format and loads them if
    necessary.

    Its application is idempotent.
    """
    return check_niimg(niimg, ensure_ndim=3)


def check_niimg_4d(niimg, return_iterator=False):
    """Check that niimg is a proper 4D niimg-like object and load it.

    Parameters
    ----------
    niimg: 4D Niimg-like object
        See http://nilearn.github.io/building_blocks/manipulating_mr_images.html#niimg.
        If niimgs is an iterable, checks if data is really 4D. Then,
        considering that it is a list of niimg and load them one by one.
        If niimg is a string, consider it as a path to Nifti image and
        call nibabel.load on it. If it is an object, check if get_data
        and get_affine methods are present, raise an Exception otherwise.

    return_iterator: boolean
        If True, an iterator of 3D images is returned. This reduces the memory
        usage when `niimgs` contains 3D images.
        If False, a single 4D image is returned. When `niimgs` contains 3D
        images they are concatenated together.

    Returns
    -------
    niimg: 4D nibabel.Nifti1Image or iterator of 3D nibabel.Nifti1Image

    Notes
    -----
    This function is the equivalent to check_niimg_3d() for Niimg-like objects
    with a session level.

    Its application is idempotent.
    """
    return check_niimg(niimg, ensure_ndim=4, return_iterator=return_iterator)


def concat_niimgs(niimgs, dtype=np.float32, ensure_ndim=None,
                  memory=Memory(cachedir=None), memory_level=0,
                  auto_resample=False, verbose=0):
    """Concatenate a list of 3D/4D niimgs of varying lengths.

    The niimgs list can contain niftis/paths to images of varying dimensions
    (i.e., 3D or 4D) as well as different 3D shapes and affines, as they
    will be matched to the first image in the list if auto_resample=True.

    Parameters
    ----------
    niimgs: iterable of Niimg-like objects
        See http://nilearn.github.io/building_blocks/manipulating_mr_images.html#niimg.
        Niimgs to concatenate.

    dtype: numpy dtype, optional
        the dtype of the returned image

    ensure_ndim: integer, optional
        Indicate the dimensionality of the expected niimg. An
        error is raised if the niimg is of another dimensionality.

    auto_resample: boolean
        Converts all images to the space of the first one.

    verbose: int
        Controls the amount of verbosity (0 means no messages).

    memory : instance of joblib.Memory or string
        Used to cache the resampling process.
        By default, no caching is done. If a string is given, it is the
        path to the caching directory.

    memory_level : integer, optional
        Rough estimator of the amount of memory used by caching. Higher value
        means more memory for caching.

    Returns
    -------
    concatenated: nibabel.Nifti1Image
        A single image.
    """

    target_fov = 'first' if auto_resample else None

    # We remove one to the dimensionality because of the list is one dimension.
    ndim = None
    if ensure_ndim is not None:
        ndim = ensure_ndim - 1

    # First niimg is extracted to get information and for new_img_like
    first_niimg = None

    iterator, literator = itertools.tee(iter(niimgs))
    try:
        first_niimg = check_niimg(next(literator), ensure_ndim=ndim)
    except StopIteration:
        raise TypeError('Cannot concatenate empty objects')
    except DimensionError as exc:
        # Keep track of the additional dimension in the error
        exc.increment_stack_counter()
        raise

    # If no particular dimensionality is asked, we force consistency wrt the
    # first image
    if ndim is None:
        ndim = len(first_niimg.shape)

    lengths = [first_niimg.shape[-1] if ndim == 4 else 1]
    for niimg in literator:
        # We check the dimensionality of the niimg
        try:
            niimg = check_niimg(niimg, ensure_ndim=ndim)
        except DimensionError as exc:
            # Keep track of the additional dimension in the error
            exc.increment_stack_counter()
            raise
        lengths.append(niimg.shape[-1] if ndim == 4 else 1)

    target_shape = first_niimg.shape[:3]
    data = np.ndarray(target_shape + (sum(lengths), ),
                      order="F", dtype=dtype)
    cur_4d_index = 0
    for index, (size, niimg) in enumerate(izip(lengths, _iter_check_niimg(
            iterator, atleast_4d=True, target_fov=target_fov,
            memory=memory, memory_level=memory_level))):

        if verbose > 0:
            if isinstance(niimg, _basestring):
                nii_str = "image " + niimg
            else:
                nii_str = "image #" + str(index)
            print("Concatenating {0}: {1}".format(index + 1, nii_str))

        data[..., cur_4d_index:cur_4d_index + size] = niimg.get_data()
        cur_4d_index += size

    return new_img_like(first_niimg, data, first_niimg.get_affine())
