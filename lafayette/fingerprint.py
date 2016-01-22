from __future__ import absolute_import, print_function
import hashlib
from operator import itemgetter

import numpy as np
import matplotlib.mlab as mlab
from scipy.ndimage.filters import maximum_filter
from scipy.ndimage.morphology import binary_erosion
from scipy.ndimage.morphology import generate_binary_structure
from scipy.ndimage.morphology import iterate_structure

IDX_FREQ_I = 0
IDX_TIME_J = 1

######################################################################
# Sampling rate, related to the Nyquist conditions, which affects
# the range frequencies we can detect.
FRAME_RATE = 44100

######################################################################
# Size of the FFT window, affects frequency granularity
WINDOW_SIZE = 4096

######################################################################
# Ratio by which each sequential window overlaps the last and the
# next window. Higher overlap will allow a higher granularity of offset
# matching, but potentially more fingerprints.
OVERLAP_RATIO = 0.5

######################################################################
# Degree to which a fingerprint can be paired with its neighbors --
# higher will cause more fingerprints, but potentially better accuracy.
FAN_VALUE = 15

######################################################################
# Minimum amplitude in spectrogram in order to be considered a peak.
# This can be raised to reduce number of fingerprints, but can negatively
# affect accuracy.
AMP_MIN = 10

######################################################################
# Number of cells around an amplitude peak in the spectrogram in order
# for Lafayette to consider it a spectral peak. Higher values mean less
# fingerprints and faster matching, but can potentially affect accuracy.
PEAK_NEIGHBORHOOD_SIZE = 20

######################################################################
# Thresholds on how close or far fingerprints can be in time in order
# to be paired as a fingerprint. If your max is too low, higher values of
# FAN_VALUE may not perform as expected.
MIN_HASH_TIME_DELTA = 0
MAX_HASH_TIME_DELTA = 200

######################################################################
# If True, will sort peaks temporally for fingerprinting;
# not sorting will cut down number of fingerprints, but potentially
# affect performance.
PEAK_SORT = True

######################################################################
# Number of bits to throw away from the front of the SHA1 hash in the
# fingerprint calculation. The more you throw away, the less storage, but
# potentially higher collisions and misclassifications when identifying songs.
FINGERPRINT_REDUCTION = 20


def fingerprint(
        channel_samples,
        frame_rate=None,
        wsize=None,
        wratio=None,
        fan_value=None,
        amp_min=None):
    """
    FFT the channel, log transform output, find local maxima, then return
    locally sensitive hashes.
    """
    frame_rate = frame_rate or FRAME_RATE
    wsize = wsize or WINDOW_SIZE
    wratio = wratio or OVERLAP_RATIO
    fan_value = fan_value or FAN_VALUE
    amp_min = amp_min or AMP_MIN

    # FFT the signal and extract frequency components
    arr2D = mlab.specgram(
        channel_samples,
        NFFT=wsize,
        Fs=frame_rate,
        window=mlab.window_none,
        noverlap=int(wsize * wratio))[0]

    # apply log transform since specgram() returns linear array
    #arr2D = 10 * np.log10(arr2D)
    arr2D[arr2D == -np.inf] = 0  # replace infs with zeros

    # find local maxima
    local_maxima = get_2D_peaks(arr2D, amp_min=amp_min)

    # return hashes
    return generate_hashes(local_maxima, fan_value=fan_value)


def get_2D_peaks(arr2D, amp_min=None):

    amp_min = amp_min or AMP_MIN
    # http://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.morphology.iterate_structure.html#scipy.ndimage.morphology.iterate_structure
    struct = generate_binary_structure(2, 1)
    neighborhood = iterate_structure(struct, PEAK_NEIGHBORHOOD_SIZE)

    # find local maxima using our fliter shape
    local_max = maximum_filter(arr2D, footprint=neighborhood) == arr2D
    #print(local_max)
    background = (arr2D == 0)
    eroded_background = binary_erosion(background, structure=neighborhood, border_value=1)

    # Boolean mask of arr2D with True at peaks
    detected_peaks = local_max - eroded_background

    # extract peaks
    amps = arr2D[detected_peaks]
    j, i = np.where(detected_peaks)

    # filter peaks
    amps = amps.flatten()
    peaks = zip(i, j, amps)
    peaks_filtered = [x for x in peaks if x[2] > amp_min]  # freq, time, amp

    # get indices for frequency and time
    frequency_idx = [x[1] for x in peaks_filtered]
    #time_idx = [x[0] / (WINDOW_SIZE * OVERLAP_RATIO) for x in peaks_filtered]
    time_idx = [x[0] for x in peaks_filtered]

    return list(zip(frequency_idx, time_idx))


def generate_hashes(peaks, fan_value=None):
    """
    Hash list structure:
       sha1_hash[0:20]    time_offset
    [(e05b341a9b77a51fd26, 32), ... ]
    """
    fan_value = fan_value or FAN_VALUE
    if PEAK_SORT:
        peaks.sort(key=itemgetter(1))

    #print(peaks)
    #print(len(peaks))

    for i in range(len(peaks)):
        for j in range(1, fan_value):
            if (i + j) >= len(peaks):
                continue
            freq1 = peaks[i][IDX_FREQ_I]
            freq2 = peaks[i + j][IDX_FREQ_I]

            t1 = peaks[i][IDX_TIME_J]
            t2 = peaks[i + j][IDX_TIME_J]
            t_delta = t2 - t1

            if MIN_HASH_TIME_DELTA <= t_delta <= MAX_HASH_TIME_DELTA:
                h = hashlib.sha1(('%s|%s|%s' % (freq1, freq2, t_delta)).encode('utf-8'))
                yield h.hexdigest()[FINGERPRINT_REDUCTION:], t1


def offset_to_sec(offset):
    return round(float(offset) / FRAME_RATE *
                         WINDOW_SIZE *
                         OVERLAP_RATIO, 5)
