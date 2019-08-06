import numpy as np
import logging
from scipy.spatial.distance import mahalanobis, cdist

import nibabel as nib

import dipy.data as dpd
import dipy.tracking.streamline as dts
import dipy.tracking.streamlinespeed as dps
from dipy.segment.bundles import RecoBundles
from dipy.align.streamlinear import whole_brain_slr
import dipy.core.gradients as dpg

import AFQ.registration as reg
import AFQ.utils.models as ut
import AFQ.utils.volume as auv

__all__ = ["Segment"]


def _resample_bundle(streamlines, n_points):
    return np.array(dps.set_number_of_points(streamlines, n_points))


def calculate_tract_profile(img, streamlines, affine=None, n_points=100,
                            weights=None):
    """

    Parameters
    ----------
    img : 3D volume

    streamlines : list of arrays, or array

    weights : 1D array or 2D array (optional)
        Weight each streamline (1D) or each node (2D) when calculating the
        tract-profiles. Must sum to 1 across streamlines (in each node if
        relevant).

    """
    if affine is None:
        affine = np.eye(4)
    # It's already an array
    if isinstance(streamlines, np.ndarray):
        fgarray = streamlines
    else:
        # It's some other kind of thing (list, Streamlines, etc.).
        # Resample each streamline to the same number of points
        # list => np.array
        # Setting the number of points should happen in a streamline template
        # space, rather than in the subject native space, but for now we do
        # everything as in the Matlab version -- in native space.
        # In the future, an SLR object can be passed here, and then it would
        # move these streamlines into the template space before resampling...
        fgarray = _resample_bundle(streamlines, n_points)
    # ...and move them back to native space before indexing into the volume:
    values = dts.values_from_volume(img, fgarray, affine=affine)

    # We assume that weights *always sum to 1 across streamlines*:
    if weights is None:
        weights = np.ones(values.shape) / values.shape[0]

    tract_profile = np.sum(weights * values, 0)
    return tract_profile


def gaussian_weights(bundle, n_points=100, return_mahalnobis=False,
                     stat=np.mean):
    """
    Calculate weights for each streamline/node in a bundle, based on a
    Mahalanobis distance from the mean of the bundle, at that node

    Parameters
    ----------
    bundle : array or list
        If this is a list, assume that it is a list of streamline coordinates
        (each entry is a 2D array, of shape n by 3). If this is an array, this
        is a resampled version of the streamlines, with equal number of points
        in each streamline.
    n_points : int, optional
        The number of points to resample to. *If the `bundle` is an array, this
        input is ignored*. Default: 100.

    Returns
    -------
    w : array of shape (n_streamlines, n_points)
        Weights for each node in each streamline, calculated as its relative
        inverse of the Mahalanobis distance, relative to the distribution of
        coordinates at that node position across streamlines.
    """
    if isinstance(bundle, np.ndarray):
        # It's an array, go with it:
        n_points = bundle.shape[1]
    else:
        # It's something else, assume that it needs to be resampled:
        bundle = _resample_bundle(bundle, n_points)
    w = np.zeros((bundle.shape[0], n_points))

    # If there's only one fiber here, it gets the entire weighting:
    if bundle.shape[0] == 1:
        if return_mahalnobis:
            return np.array([np.nan])
        else:
            return np.array([1])

    for node in range(bundle.shape[1]):
        # This should come back as a 3D covariance matrix with the spatial
        # variance covariance of this node across the different streamlines
        # This is a 3-by-3 array:
        node_coords = bundle[:, node]
        c = np.cov(node_coords.T, ddof=0)
        c = np.array([[c[0, 0], c[0, 1], c[0, 2]],
                      [0, c[1, 1], c[1, 2]],
                      [0, 0, c[2, 2]]])
        # Calculate the mean or median of this node as well
        # delta = node_coords - np.mean(node_coords, 0)
        m = stat(node_coords, 0)
        # Weights are the inverse of the Mahalanobis distance
        for fn in range(bundle.shape[0]):
            # calculate Mahalanobis for node on fiber[fn]
            w[fn, node] = mahalanobis(node_coords[fn], m, np.linalg.inv(c))
    if return_mahalnobis:
        return w
    # weighting is inverse to the distance (the further you are, the less you
    # should be weighted)
    w = 1 / w
    # Normalize before returning, so that the weights in each node sum to 1:
    return w / np.sum(w, 0)


def split_streamlines(streamlines, template, low_coord=10):
    """
    Classify streamlines and split sl passing the mid-point below some height.
    Parameters
    ----------
    streamlines : list or Streamlines class instance.
    template : nibabel.Nifti1Image class instance
        An affine transformation into a template space.
    low_coords: int
        How many coordinates below the 0,0,0 point should a streamline be to
        be split if it passes the midline.
    Returns
    -------
    streamlines that have been processed, a boolean array of whether they
    cross the midline or not, a boolean array that for those who do not cross
    designates whether they are strictly in the left hemisphere, and a boolean
    that tells us whether the streamline has superior-inferior parts that pass
    below `low_coord` steps below the middle of the image (which should also
    be `low_coord` mms for templates with 1 mm resolution)
    """
    # What is the x,y,z coordinate of 0,0,0 in the template space?
    zero_coord = np.dot(np.linalg.inv(template.affine),
                        np.array([0, 0, 0, 1]))

    # cross_below = zero_coord[2] - low_coord
    crosses = np.zeros(len(streamlines), dtype=bool)
    # already_split = 0
    for sl_idx, sl in enumerate(streamlines):
        if np.any(sl[:, 0] > zero_coord[0]) and \
           np.any(sl[:, 0] < zero_coord[0]):
            # if np.any(sl[:, 2] < cross_below):
            #     # This is a streamline that needs to be split where it
            #     # crosses the midline:
            #     split_idx = np.argmin(np.abs(sl[:, 0] - zero_coord[0]))
            #     streamlines = aus.split_streamline(
            #         streamlines, sl_idx + already_split, split_idx)
            #     already_split = already_split + 1
            #     # Now that it's been split, neither cross the midline:
            #     crosses[sl_idx] = False
            #     crosses = np.concatenate([crosses[:sl_idx+1],
            #                               np.array([False]),
            #                               crosses[sl_idx+1:]])
            # else:
            crosses[sl_idx] = True
        else:
            crosses[sl_idx] = False

    # Move back to the original space:
    return streamlines, crosses


def _check_sl_with_inclusion(sl, include_rois, tol):
    """
    Helper function to check that a streamline is close to a list of
    inclusion ROIS.
    """
    dist = []
    for roi in include_rois:
        dist.append(cdist(sl, roi, 'sqeuclidean'))
        if np.min(dist[-1]) > tol:
            # Too far from one of them:
            return False, []
    # Apparently you checked all the ROIs and it was close to all of them
    return True, dist


def _check_sl_with_exclusion(sl, exclude_rois, tol):
    """ Helper function to check that a streamline is not too close to a list
    of exclusion ROIs.
    """
    for roi in exclude_rois:
        if np.min(cdist(sl, roi, 'sqeuclidean')) < tol:
            return False
    # Either there are no exclusion ROIs, or you are not close to any:
    return True


class Segment:
    def __init__(self):
        """
        Segment streamlines into bundles based on inclusion ROIs.

        References
        ----------
        .. [Hua2008] Hua K, Zhang J, Wakana S, Jiang H, Li X, et al. (2008)
        Tract probability maps in stereotaxic spaces: analyses of white
        matter anatomy and tract-specific quantification. Neuroimage 39:
        336-347
        """
        self.logger = logging.getLogger('AFQ.Segmentation')

    def setup(self, split=True, resample_np=0):
        """
        Define parameters for segment function

        Parameters
        ----------
        split : boolean
            If true, classify the streamlines and split those that:
            1) cross the midline, and 2) pass under 10 mm below
            the mid-point of their representation in the template space.
            Default: False
        resample_np : int
            Resample streamlines to resample_np number of points.
            If 0, no resampling is done. Default: 0
        """
        self.split = split
        self.resample_np = resample_np

    def segment(self, fdata, fbval, fbvec, bundle_dict, streamlines,
                b0_threshold=0, mapping=None, reg_prealign=None,
                reg_template=None, prob_threshold=0):
        """
        Prepare image data from DWI data, 
        Set mapping between DWI space and a template,
        Get fiber probabilites and ROIs for each bundle,
        And iterate over streamlines and bundles,
        assigning streamlines to fiber groups.

        Parameters
        ----------
        fdata, fbval, fbvec : str
            Full path to data, bvals, bvecs
        mapping : DiffeomorphicMap object, str or nib.Nifti1Image, optional.
            A mapping between DWI space and a template.
            If None, mapping will be registered from data used in prepare_img.
            Default: None.
        reg_template : str or nib.Nifti1Image, optional.
            Template to use for registration (defaults to the MNI T2)
        bundle_dict: dict
            The format is something like::

                {'name': {'ROIs':[img1, img2],
                'rules':[True, True]},
                'prob_map': img3,
                'cross_midline': False}
        streamlines : list of 2D arrays
            Each array is a streamline, shape (3, N).
            If streamlines is None, will use previously given streamlines.
            Default: None.
        """
        self.prepare_img(fdata, fbval, fbvec, b0_threshold)
        self.prepare_map(mapping, reg_prealign, reg_template)
        self.create_prob(bundle_dict)

        self.streamlines = streamlines
        if self.resample_np > 0:
            self.resample(self.resample_np)
        if self.split:
            self.split_sls()

        self.segment_sls(None, prob_threshold)
        

    def prepare_img(self, fdata, fbval, fbvec, b0_threshold=0):
        """
        Prepare image data from DWI data.

        Parameters
        ----------
        fdata, fbval, fbvec : str
            Full path to data, bvals, bvecs
        """
        self.logger.info("Preparing Image...")
        self.img, _, _, _ = \
            ut.prepare_data(fdata, fbval, fbvec,
                            b0_threshold=b0_threshold)
        self.fdata = fdata
        self.fbval = fbval
        self.fbvec = fbvec

    def prepare_map(self, mapping=None, reg_prealign=None, reg_template=None):
        """
        Set mapping between DWI space and a template.

        Parameters
        ----------
        mapping : DiffeomorphicMap object, str or nib.Nifti1Image, optional.
            A mapping between DWI space and a template.
            If None, mapping will be registered from data used in prepare_img.
            Default: None.

        reg_template : str or nib.Nifti1Image, optional.
            Template to use for registration (defaults to the MNI T2)
        """
        if reg_template is None:
            reg_template = dpd.read_mni_template()

        if mapping == None:
            gtab = dpg.gradient_table(self.fbval, self.fbvec)
            self.mapping = reg.syn_register_dwi(self.fdata, gtab)[1]
        elif isinstance(mapping, str) or isinstance(mapping, nib.Nifti1Image):
            if reg_prealign is None:
                reg_prealign = np.eye(4)
            self.mapping = reg.read_mapping(mapping, self.img, reg_template,
                                            prealign=reg_prealign)
        else:
            self.mapping = mapping

    def create_prob(self, bundle_dict):
        """
        Get fiber probabilites and ROIs for each bundle. 

        Parameters
        ----------
        bundle_dict: dict
            The format is something like::

                {'name': {'ROIs':[img1, img2],
                'rules':[True, True]},
                'prob_map': img3,
                'cross_midline': False}
        """
        self.bundle_dict = bundle_dict
        self.warped_prob_map = len(self.bundle_dict) * [None]
        self.include_rois = len(self.bundle_dict) * [None]
        self.exclude_rois = len(self.bundle_dict) * [None]

        self.logger.info("Preparing Fiber Probabilites and ROIs...")
        for bundle_idx, bundle in enumerate(self.bundle_dict):
            rules = self.bundle_dict[bundle]['rules']
            include_rois = []
            exclude_rois = []
            for rule_idx, rule in enumerate(rules):
                roi = self.bundle_dict[bundle]['ROIs'][rule_idx]
                if not isinstance(roi, np.ndarray):
                    roi = roi.get_fdata()
                warped_roi = auv.patch_up_roi(
                    (self.mapping.transform_inverse(
                        roi.astype(np.float32),
                        interpolation='linear')) > 0)

                if rule:
                    # include ROI:
                    include_rois.append(np.array(np.where(warped_roi)).T)
                else:
                    # Exclude ROI:
                    exclude_rois.append(np.array(np.where(warped_roi)).T)
            self.include_rois[bundle_idx] = include_rois
            self.exclude_rois[bundle_idx] = exclude_rois

            # The probability map if doesn't exist is all ones with the same
            # shape as the ROIs:
            prob_map = self.bundle_dict[bundle].get(
                'prob_map', np.ones(roi.shape))

            if not isinstance(prob_map, np.ndarray):
                prob_map = prob_map.get_fdata()
            self.warped_prob_map[bundle_idx] = self.mapping.transform_inverse(prob_map,
                                                             interpolation='nearest')

    def resample(self, nb_points, streamlines=None):
        """
        Resample streamlines to nb_points number of points.

        Parameters
        ----------
        nb_points : int
            Integer representing number of points wanted along the curve.
            Streamlines will be resampled to this number of points.
        streamlines : list of 2D arrays
            Each array is a streamline, shape (3, N).
            If streamlines is None, will use previously given streamlines.
            Default: None.
        """
        if streamlines == None:
            streamlines = self.streamlines

        self.streamlines = _resample_bundle(streamlines, nb_points)

    def split_sls(self, streamlines=None):
        """
        Classify the streamlines and split those that: 1) cross the
        midline, and 2) pass under 10 mm below the mid-point of their
        representation in the template space.

        Parameters
        ----------
        streamlines : list of 2D arrays
            Each array is a streamline, shape (3, N).
            If streamlines is None, will use previously given streamlines.
            Default: None.
        """
        if streamlines == None:
            streamlines = self.streamlines

        self.streamlines, self.crosses = \
            split_streamlines(streamlines, self.img)

    def segment_sls(self, streamlines=None, prob_threshold=0):
        """
        Iterate over streamlines and bundles, assigning streamlines to fiber groups.

        Parameters
        ----------
        streamlines : list of 2D arrays
            Each array is a streamline, shape (3, N).
            If streamlines is None, will use previously given streamlines.
            Default: None.

        prob_threshold : float.
            Initial cleaning of fiber groups is done using probability maps from
            [Hua2008]_. Here, we choose an average probability that needs to be
            exceeded for an individual streamline to be retained. Default: 0.
        """
        if streamlines == None:
            streamlines = self.streamlines
        else:
            self.streamlines = streamlines

        # For expedience, we approximate each streamline as a 100 point curve:
        fgarray = _resample_bundle(streamlines, 100)

        streamlines_in_bundles = np.zeros(
            (len(streamlines), len(self.bundle_dict)))
        min_dist_coords = np.zeros(
            (len(streamlines), len(self.bundle_dict), 2))
        self.fiber_groups = {}

        self.logger.info("Assigning Streamlines to Fiber Groups...")
        tol = dts.dist_to_corner(self.img.affine)**2
        for bundle_idx, bundle in enumerate(self.bundle_dict):
            fiber_probabilities = dts.values_from_volume(self.warped_prob_map[bundle_idx],
                                                         fgarray)
            fiber_probabilities = np.mean(fiber_probabilities, -1)

            crosses_midline = self.bundle_dict[bundle]['cross_midline']
            for sl_idx, sl in enumerate(streamlines):
                if fiber_probabilities[sl_idx] > prob_threshold:
                    if crosses_midline is not None:
                        try:
                            if self.crosses[sl_idx]:
                                # This means that the streamline does
                                # cross the midline:
                                if crosses_midline:
                                    # This is what we want, keep going
                                    pass
                                else:
                                    # This is not what we want, skip to next streamline
                                    continue
                        except NameError:
                            pass

                    is_close, dist = _check_sl_with_inclusion(sl, self.include_rois[bundle_idx],
                                                            tol)
                    if is_close:
                        is_far = _check_sl_with_exclusion(sl, self.exclude_rois[bundle_idx],
                                                        tol)
                        if is_far:
                            min_dist_coords[sl_idx, bundle_idx, 0] =\
                                np.argmin(dist[0], 0)[0]
                            min_dist_coords[sl_idx, bundle_idx, 1] =\
                                np.argmin(dist[1], 0)[0]
                            streamlines_in_bundles[sl_idx, bundle_idx] =\
                                fiber_probabilities[sl_idx]

        self.logger.info("Cleaning and Re-Orienting...")
        # Eliminate any fibers not selected using the plane ROIs:
        possible_fibers = np.sum(streamlines_in_bundles, -1) > 0
        streamlines = streamlines[possible_fibers]
        streamlines_in_bundles = streamlines_in_bundles[possible_fibers]
        min_dist_coords = min_dist_coords[possible_fibers]
        bundle_choice = np.argmax(streamlines_in_bundles, -1)

        # We do another round through, so that we can orient all the
        # streamlines within a bundle in the same orientation with respect to
        # the ROIs. This order is ARBITRARY but CONSISTENT (going from ROI0
        # to ROI1).
        for bundle_idx, bundle in enumerate(self.bundle_dict):
            select_idx = np.where(bundle_choice == bundle_idx)
            # Use a list here, because Streamlines don't support item assignment:
            select_sl = list(streamlines[select_idx])
            if len(select_sl) == 0:
                self.fiber_groups[bundle] = dts.Streamlines([])
                # There's nothing here, move to the next bundle:
                continue

            # Sub-sample min_dist_coords:
            min_dist_coords_bundle = min_dist_coords[select_idx]
            for idx in range(len(select_sl)):
                min0 = min_dist_coords_bundle[idx, bundle_idx, 0]
                min1 = min_dist_coords_bundle[idx, bundle_idx, 1]
                if min0 > min1:
                    select_sl[idx] = select_sl[idx][::-1]
            # Set this to nibabel.Streamlines object for output:
            select_sl = dts.Streamlines(select_sl)
            self.fiber_groups[bundle] = select_sl


def clean_fiber_group(streamlines, n_points=100, clean_rounds=5,
                      clean_threshold=3, min_sl=20, stat=np.mean):
    """
    Clean a segmented fiber group based on the Mahalnobis distance of
    each streamline

    Parameters
    ----------

    streamlines : nibabel.Streamlines class instance.
        The streamlines constituting a fiber group.

    clean_rounds : int, optional.
        Number of rounds of cleaning based on the Mahalanobis distance from
        the mean of extracted bundles. Default: 5

    clean_threshold : float, optional.
        Threshold of cleaning based on the Mahalanobis distance (the units are
        standard deviations). Default: 6.

    min_sl : int, optional.
        Number of streamlines in a bundle under which we will
        not bother with cleaning outliers. Default: 20.

    stat : callable, optional.
        The statistic of each node relative to which the Mahalanobis is
        calculated. Default: `np.mean` (but can also use median, etc.)

    Returns
    -------
    A nibabel.Streamlines class instance containing only the streamlines
    that have a Mahalanobis distance smaller than `clean_threshold` from
    the mean of each one of the nodes.
    """

    # We don't even bother if there aren't enough streamlines:
    if len(streamlines) < min_sl:
        return streamlines

    # Resample once up-front:
    fgarray = _resample_bundle(streamlines, n_points)
    # Keep this around, so you can use it for indexing at the very end:
    idx = np.arange(fgarray.shape[0])
    # This calculates the Mahalanobis for each streamline/node:
    w = gaussian_weights(fgarray, return_mahalnobis=True, stat=stat)
    # We'll only do this for clean_rounds
    rounds_elapsed = 0
    while (np.any(w > clean_threshold)
           and rounds_elapsed < clean_rounds
           and len(streamlines) > min_sl):
        # Select the fibers that have Mahalanobis smaller than the
        # threshold for all their nodes:
        idx_belong = np.where(
            np.all(w < clean_threshold, axis=-1))[0]
        idx = idx[idx_belong.astype(int)]
        # Update by selection:
        fgarray = fgarray[idx_belong.astype(int)]
        # Repeat:
        w = gaussian_weights(fgarray, return_mahalnobis=True)
        rounds_elapsed += 1
    # Select based on the variable that was keeping track of things for us:
    return streamlines[idx]


def recobundles(streamlines, bundle_dict):
    """
    Segment streamlines using the RecoBundles algorithm [Garyfallidis2017]

    Parameters
    ----------
    streamlines : list or Streamlines object.
        A whole-brain tractogram to be segmented.
    bundle_dict: dictionary
        Of the form:

            {'whole_brain': Streamlines,
            'CST_L': {'sl': Streamlines, 'centroid': array},
            'CST_R': {'sl': Streamlines, 'centroid': array},
            ...}

    Returns
    -------
    fiber_groups : dict
        Keys are names of the bundles, values are Streamline objects.
        The streamlines in each object have all been oriented to have the
        same orientation (using `dts.orient_by_streamline`).
    """
    fiber_groups = {}
    # We start with whole-brain SLR:
    atlas = bundle_dict['whole_brain']
    moved, transform, qb_centroids1, qb_centroids2 = whole_brain_slr(
        atlas, streamlines, x0='affine', verbose=False, progressive=True)

    # We generate our instance of RB with the moved streamlines:
    rb = RecoBundles(moved, verbose=False)

    # Next we'll iterate over bundles, registering each one:
    bundle_list = list(bundle_dict.keys())
    bundle_list.remove('whole_brain')

    for bundle in bundle_list:
        model_sl = bundle_dict[bundle]['sl']
        _, rec_labels = rb.recognize(model_bundle=model_sl,
                                     model_clust_thr=5.,
                                     reduction_thr=10,
                                     reduction_distance='mam',
                                     slr=True,
                                     slr_metric='asymmetric',
                                     pruning_distance='mam')

        # Use the streamlines in the original space:
        recognized_sl = streamlines[rec_labels]
        standard_sl = bundle_dict[bundle]['centroid']
        oriented_sl = dts.orient_by_streamline(recognized_sl, standard_sl)
        fiber_groups[bundle] = oriented_sl
    return fiber_groups
