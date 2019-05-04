###########################################################################
# Author: Jodi Jones <venom@gen-x.co.nz>
# URL: https://github.com/VeNoMouS/Sick-Beard
#
# This file is part of Sick Beard.
#
# Sick Beard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sick Beard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.
###########################################################################

import os
import re
import sys
import urllib
import generic
import datetime
import sickbeard
import exceptions

from lib import cloudscraper
from lib.requests import exceptions
from xml.sax.saxutils import escape

from sickbeard import db
from sickbeard import logger
from sickbeard import tvcache
from sickbeard.exceptions import ex
from sickbeard.common import Quality
from sickbeard.common import Overview
from sickbeard import show_name_helpers


class TorrentLeechProvider(generic.TorrentProvider):

    ###########################################################################
    def __init__(self):
        generic.TorrentProvider.__init__(self, "TorrentLeech")
        self.cache = TorrentLeechCache(self)
        self.name = "TorrentLeech"
        self.session = None
        self.supportsBacklog = True
        self.url = 'https://classic.torrentleech.org/'
        self.funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + "()"
        logger.log("[" + self.name + "] initializing...")

    ###########################################################################

    def isEnabled(self):
        return sickbeard.TORRENTLEECH

    ###########################################################################

    def imageName(self):
        return 'torrentleech.png'

    ###########################################################################

    def getQuality(self, item):
        quality = Quality.nameQuality(item[0])
        return quality

    ###########################################################################

    def _get_title_and_url(self, item):
        return item

    ###########################################################################

    def _get_airbydate_season_range(self, season):
        if season is None:
            return ()
        year, month = map(int, season.split('-'))
        min_date = datetime.date(year, month, 1)
        if month == 12:
            max_date = datetime.date(year, month, 31)
        else:
            max_date = datetime.date(
                year,
                month + 1,
                1
            ) - datetime.timedelta(days=1)
        return (min_date, max_date)

    ###########################################################################

    def _get_season_search_strings(self, show, season=None):
        search_string = []

        if not show:
            return []

        myDB = db.DBConnection()

        if show.air_by_date:
            (min_date, max_date) = self._get_airbydate_season_range(season)
            sqlResults = myDB.select(
                "SELECT * FROM tv_episodes WHERE showid = ? AND airdate >= ? AND airdate <= ?",
                [
                    show.tvdbid,
                    min_date.toordinal(),
                    max_date.toordinal()
                ]
            )
        else:
            sqlResults = myDB.select(
                "SELECT * FROM tv_episodes WHERE showid = ? AND season = ?",
                [
                    show.tvdbid,
                    season
                ]
            )

        for sqlEp in sqlResults:
            if show.getOverview(int(sqlEp["status"])) in (
                Overview.WANTED,
                Overview.QUAL
            ):
                if show.air_by_date:
                    for show_name in set(show_name_helpers.allPossibleShowNames(show)):
                        search_string.append(
                            "{0} {1}".format(
                                show_name_helpers.sanitizeSceneName(show_name),
                                str(datetime.date.fromordinal(sqlEp["airdate"])).replace('-', '.')
                            )
                        )
                else:
                    for show_name in set(show_name_helpers.allPossibleShowNames(show)):
                        search_string.append(
                            "{0} {1}".format(
                                show_name_helpers.sanitizeSceneName(show_name),
                                sickbeard.config.naming_ep_type[2] % {
                                    'seasonnumber': season,
                                    'episodenumber': int(sqlEp["episode"])
                                }
                            )
                        )
        return search_string

    ###########################################################################

    def _get_episode_search_strings(self, ep_obj):
        search_string = []

        if not ep_obj:
            return []

        if ep_obj.show.air_by_date:
            for show_name in set(show_name_helpers.allPossibleShowNames(ep_obj.show)):
                search_string.append(
                    "{0} {1}".format(
                        show_name_helpers.sanitizeSceneName(show_name),
                        str(ep_obj.airdate).replace('-', '.')
                    )
                )
        else:
            for show_name in set(show_name_helpers.allPossibleShowNames(ep_obj.show)):
                search_string.append(
                    "{0} {1}".format(
                        show_name_helpers.sanitizeSceneName(show_name),
                        sickbeard.config.naming_ep_type[2] % {
                            'seasonnumber': ep_obj.season,
                            'episodenumber':  ep_obj.episode
                        }
                    )
                )
        return search_string

    ###########################################################################

    def _doSearch(self, search_params, show=None):
        logger.log("[{0}] {1} Performing Search: {2}".format(
                self.name,
                self.funcName(),
                search_params
            )
        )

        return self.parseResults(
            "{0}torrents/browse/index/query/{1}/categories/26,27,32/newfilter/3".format(
                self.url,
                search_params.replace(':','')
            )
        )

    ##################################################################################################

    def parseResults(self, searchUrl):
        data = self.getURL(searchUrl)
        results = []

        if data:
            logger.log("[{0}] {1} URL: {2}".format(
                    self.name,
                    self.funcName(),
                    searchUrl
                ),
                logger.DEBUG
            )

            for torrent in re.compile(
                '<span class="title"><a href="/torrent/\d+">(?P<title>.*?)</a>.*?<td class="quickdownload">\s+<a href="(?P<url>.*?)">',
                re.MULTILINE|re.DOTALL
            ).finditer(data):
                try:
                    results.append(
                        (
                            torrent.group('title').replace('.',' ').decode('ascii'),
                            torrent.group('url')
                        )
                    )

                    logger.log("[{0}] {1} Title: {2}".format(
                            self.name,
                            self.funcName(),
                            torrent.group('title')
                        ),
                        logger.DEBUG
                    )

                except:
                    logger.log("[{0}] {1} Skipping torrent, non standard character found and/or unable to extract torrent download information.".format(
                            self.name,
                            self.funcName(),
                        ),
                        logger.DEBUG
                    )

            if len(results):
                logger.log("[{0}] {1} Some results found.".format(
                        self.name,
                        self.funcName(),
                    )
                )
            else:
                logger.log("[{0}] {1} No results found.".format(
                        self.name,
                        self.funcName(),
                    )
                )
        else:
            logger.log("[{0}] {1} Error no data returned!!".format(
                    self.name,
                    self.funcName(),
                )
            )
        return results

    ###########################################################################

    def getURL(self, url, headers=None):
        response = None

        if not self.session:
             if not self._doLogin():
                return response

        if not headers:
            headers = []

        try:
            response = self.session.get(url, verify=False)

        except (exceptions.ConnectionError, exceptions.HTTPError), e:
            logger.log("[{0}] {1}  Error loading URL: {2}, Error: {3} ".format(
                    self.name,
                    self.funcName(),
                    url,
                    e
                ),
                logger.ERROR
            )
            return None

        if response.status_code not in [200,302,303]:
            logger.log("[{0}] {1} requested URL: {2} returned status code is {3}".format(
                    self.name,
                    self.funcName(),
                    url,
                    response.status_code
                ),
                logger.ERROR
            )
            return None

        return response.content

    ###########################################################################

    def _doLogin(self):
        login_params  = {
            'username': sickbeard.TORRENTLEECH_USERNAME,
            'password': sickbeard.TORRENTLEECH_PASSWORD,
            'remember_me': 'on',
            'login': 'submit'
        }

        self.session = cloudscraper.create_scraper()
        logger.log("[" + self.name + "] Attempting to Login")

        try:
            response = self.session.post(
                "{0}user/account/login".format(self.url),
                data=login_params,
                timeout=30,
                verify=False
            )
        except (exceptions.ConnectionError, exceptions.HTTPError), e:
            logger.log("[{0}] {1} Error: {2}".format(
                    self.name,
                    self.funcName(),
                    e
                ),
                logger.ERROR
            )
            return False

        if re.search("Invalid Username/password|<title>Login :: TorrentLeech.org</title>", response.text) \
        or response.status_code in [401,403]:
            logger.log("[{0}] {1} Login Failed, Invalid username or password, Check your settings".format(
                    self.name,
                    self.funcName(),
                ),
                logger.ERROR
            )
            return False
        return True

    ###########################################################################


class TorrentLeechCache(tvcache.TVCache):

    ###########################################################################

    def __init__(self, provider):
        tvcache.TVCache.__init__(self, provider)
        # only poll TorrentLeech every 15 minutes max
        self.minTime = 15

    ###########################################################################

    def _getRSSData(self):
        # TorrentLeech's RSS sucks.. its all or nothing... so manual reconstruction required for just tv sections...
        xml = "<rss xmlns:atom=\"http://www.w3.org/2005/Atom\" version=\"2.0\">" + \
            "<channel>" + \
            "<title>" + provider.name + "</title>" + \
            "<link>" + provider.url + "</link>" + \
            "<description>torrent search</description>" + \
            "<language>en-us</language>" + \
            "<atom:link href=\"" + provider.url + "\" rel=\"self\" type=\"application/rss+xml\"/>"

        search_ret = provider._doSearch("")
        if search_ret:
            for title, url in search_ret:
                xml += "<item>" + "<title>" + escape(title) + "</title>" +  "<link>"+ urllib.quote(url,'/,:') + "</link>" + "</item>"

        xml += "</channel> </rss>"
        return xml

    ###########################################################################

provider = TorrentLeechProvider()
