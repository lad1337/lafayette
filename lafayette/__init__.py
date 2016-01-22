import logging

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
        return fingerprint.fingerprint(frames, frame_rate=frame_rate)

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

    def match_file(self, file_path):
        _, fingerprint = self.fingerprint_file(file_path, save=False)
        matches =  self.get_matched(fingerprint)
        return self.best_match(matches)

    def match_frames(self, frames, frame_rate):
        fingerprint = self.fingerprint_frames(frames, frame_rate)
        matches = self.get_matched(fingerprint)
        return self.best_match(matches)

    def get_matched(self, fingerprint):
        #fingerprint = [h for h in fingerprint]
        #print("searching %s hashes" % len(fingerprint))
        for hash_, offset in fingerprint:
            #print("searching for:", hash_)
            data = self._data.get(hash_)
            if not data:
                continue
            yield data['song']['id'], data['offset'] - offset

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
        for id_, diff in matches:
            if diff not in diff_counter:
                diff_counter[diff] = {}
            if id_ not in diff_counter[diff]:
                diff_counter[diff][id_] = 0
            diff_counter[diff][id_] += 1

            if diff_counter[diff][id_] > largest_count:
                largest = diff
                largest_count = diff_counter[diff][id_]
                best_id = id_


        # return match info
        nseconds = fingerprint.offset_to_sec(largest)

        song = self.get_by_id(best_id)
        if not song:
            return
        song['offset_sec'] = nseconds
        song['offset'] = int(largest)
        song['hit_count'] = largest_count
        return song
