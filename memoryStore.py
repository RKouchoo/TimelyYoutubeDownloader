#!/usr/bin/python
# -*- coding: utf-8 -*-


class simpleData:

    def __init__(
            self,
            channels,
            names,
            videos,
    ):
        self.memChannels = channels
        self.memNames = names
        self.memVideos = videos


class opmlExtract:

    def __init__(self, opmls, names):
        self.memOPMLS = opmls
        self.memNames = names


class dbCacheVideo:

    def __init__(self, dlCache, position):
        self.memDLCache = dlCache
        self.memPosition = position
