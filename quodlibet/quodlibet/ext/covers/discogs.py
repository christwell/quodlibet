# -*- coding: utf-8 -*-
# Copyright 2016 Mice Pápai
#           2018 Nick Boultbee
#
# Based on lastfm.py by Simonas Kazlauskas
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.


from os import path

import re
from gi.repository import Soup

from quodlibet import _
from quodlibet.plugins.cover import cover_dir
from quodlibet.util.http import download_json
from quodlibet.util.cover.http import escape_query_value
from quodlibet.util.cover.http import ApiCoverSourcePlugin
from quodlibet.util.path import escape_filename
from quodlibet.util import print_d


class DiscogsCover(ApiCoverSourcePlugin):
    PLUGIN_ID = "discogs-cover"
    PLUGIN_NAME = _("Discogs Cover Source")
    PLUGIN_DESC = _("Downloads covers from Discogs.")

    credentials = ('key=aWfZGjHQvkMcreUECGAp' +
                   '&secret=VlORkklpdvAwJMwxUjNNSgqicjuizJAl')
    use_secondary = True

    @classmethod
    def group_by(cls, song):
        return song.album_key

    @staticmethod
    def priority():
        return 0.6

    @property
    def cover_path(self):
        mbid = self.song.get('musicbrainz_albumid', None)
        if mbid:
            return path.join(cover_dir, escape_filename(mbid))
        else:
            return super(DiscogsCover, self).cover_path

    @property
    def url(self):
        _url = ('https://api.discogs.com/database/search?' +
                self.credentials +
                '&type=release' +
                '&artist={artist}' +
                '&release_title={album}')
        # Discogs seems to use 'Various' almost exclusively for compilations
        artists = self._album_artists_for(self.song) or 'Various'
        if 'various artists' in artists.lower():
            artists = 'Various'
        artist = escape_query_value(artists)
        album = escape_query_value(self.song.get('album', ''))
        if artist and album:
            return _url.format(artist=artist, album=album)
        else:
            return None   # Not enough data

    def _handle_search_response(self, message, json_dict, data=None):
        if not json_dict:
            print_d('Server did not return any valid JSON')
            return self.emit('search-complete', [])

        try:
            res_url = json_dict.get('results', [])[0].get('resource_url', '')
        except IndexError:
            print_d('Album data is not available')
            return self.emit('search-complete', [])
        else:
            msg = Soup.Message.new('GET',
                                   "%s?%s" % (res_url, self.credentials))
            download_json(msg, self.cancellable, self._handle_album_data, None)

    def _handle_album_data(self, message, json_dict, data=None):

        images = json_dict.get('images', None)

        if not images:
            print_d('Covers are not available')
            return self.emit('search-complete', [])

        results = list(self._covers_of_type(images))
        if not results and images and self.use_secondary:
            results.append(next(self._covers_of_type(images, "secondary")))

        self.emit('search-complete', results)

    def _covers_of_type(self, images, image_type='primary'):
        for image in images:
            url = image.get('uri')
            if url and image['type'] == image_type:
                dimensions = re.compile(r'/(\d+x\d+)/').search(url)
                dimensions = dimensions and dimensions.group(1)
                yield ({'cover': image['uri'], 'dimensions': dimensions})
