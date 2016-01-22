import logging

import numpy as np

from . import decoder
from . import fingerprint


class Lafayette():

    def __init__(self):
        self._data = {}
        self.logger = logging.getLogger('lafayette')

    def fingerprint_file(self, file_path, song_name=None, save=True):
        song_name = song_name or decoder.song_name(file_path)
        channels, frame_rate = decoder.read(file_path)
        all_hashes = set()

        for frames in channels:
            hashes = self.fingerprint_frames(frames, frame_rate)
            # hashes is a geberator
            all_hashes |= set(hashes)

        if save:
            self._insert_hashes(
                all_hashes,
                {'id': song_name}
            )
        return song_name, all_hashes

    def fingerprint_frames(self, frames, frame_rate):
        nums = np.fromstring(frames, np.int16)
        return fingerprint.fingerprint(nums, frame_rate)

    def _insert_hashes(self, hashes, track_data):
        count = 0
        for hash_, offset in hashes:
            self._insert_hash(hash_, offset, track_data)
            count += 1
        self.logger.debug('Inserted %s hashes.', count)

    def _insert_hash(self, hash_, offset, song_data):
        self._data[hash_] = {
            'song': song_data,
            'offset': offset
        }

    def rm_hashes(self, hashes):
        count = 0
        for hash_ in hashes:
            if self._data.pop(hash_, None):
                count += 1
        return count

    def match_file(self, file_path):
        _, fingerprint = self.fingerprint_file(file_path, save=False)
        matches =  self.get_matched(fingerprint)
        return self.best_match(matches)

    def match_frames(self, frames, frame_rate):
        nums = np.fromstring(frames, np.int16)
        fingerprints = self.fingerprint_frames(nums[0::1], frame_rate)
        matches = self.get_matched(fingerprints)
        return self.best_match(matches)

    def get_matched(self, fingerprints):
        for hash_, offset in fingerprints:
            data = self._data.get(hash_)
            if not data:
                continue
            yield hash_, data['song']['id'], data['offset'] - offset

    def get_by_id(self, id_):
        for track in [hash_info['song'] for hash_info in self._data.values()]:
            if track['id'] == id_:
                return track

    def best_match(self, matches):
        """
            Finds hash matches that align in time with other matches and finds
            consensus about which hashes are "true" signal from the audio.

            Returns a dictionary with match information.
        """
        diff_counter = {}
        largest = 0
        largest_count = 0
        best_id = None
        for hash_, id_, diff in matches:
            if diff not in diff_counter:
                diff_counter[diff] = {}
            if id_ not in diff_counter[diff]:
                diff_counter[diff][id_] = 0
            diff_counter[diff][id_] += 1

            if diff_counter[diff][id_] > largest_count:
                largest = diff
                largest_count = diff_counter[diff][id_]
                best_id = id_

        nseconds = fingerprint.offset_to_sec(largest)

        song = self.get_by_id(best_id)
        if not song:
            return
        song['offset_sec'] = nseconds
        song['offset'] = int(largest)
        song['hit_count'] = largest_count
        return song
