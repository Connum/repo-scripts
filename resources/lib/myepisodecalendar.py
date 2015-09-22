#!/usr/bin/env python
# -*- coding: utf-8 -*-

from BeautifulSoup import BeautifulSoup
import cookielib
import re
import urllib, urllib2, urlparse
import xbmc # only for debugging

# This is totally stolen from script.xbmc.subtitles plugin !
REGEX_EXPRESSIONS = [
    '[Ss]([0-9]+)[][._-]*[Ee]([0-9]+)([^\\\\/]*)$',
    '[\._ \-]([0-9]+)x([0-9]+)([^\\/]*)',                     # foo.1x09
    '[\._ \-]([0-9]+)([0-9][0-9])([\._ \-][^\\/]*)',          # foo.109
    '([0-9]+)([0-9][0-9])([\._ \-][^\\/]*)',
    '[\\\\/\\._ -]([0-9]+)([0-9][0-9])[^\\/]*',
    'Season ([0-9]+) - Episode ([0-9]+)[^\\/]*',              # Season 01 - Episode 02
    'Season ([0-9]+) Episode ([0-9]+)[^\\/]*',                # Season 01 Episode 02
    '[\\\\/\\._ -][0]*([0-9]+)x[0]*([0-9]+)[^\\/]*',
    '[[Ss]([0-9]+)\]_\[[Ee]([0-9]+)([^\\/]*)',                #foo_[s01]_[e01]
    '[\._ \-][Ss]([0-9]+)[\.\-]?[Ee]([0-9]+)([^\\/]*)',       #foo, s01e01, foo.s01.e01, foo.s01-e01
    's([0-9]+)ep([0-9]+)[^\\/]*',                             #foo - s01ep03, foo - s1ep03
    '[Ss]([0-9]+)[][ ._-]*[Ee]([0-9]+)([^\\\\/]*)$',
    '[\\\\/\\._ \\[\\(-]([0-9]+)x([0-9]+)([^\\\\/]*)$'
    ]

MYEPISODE_URL = "http://www.myepisodecalendar.com"

def sanitize(title, replace):
    for char in ['[', ']', '_', '(', ')', '..', '.', '-', '  ']:
        title = title.replace(char, replace)
    return title

# only for debugging
def log(msg):
    xbmc.log("################## DEBUG: \n%s" % (msg, ),
        level=xbmc.LOGDEBUG)

class MyEpisodeCalendar(object):

    def __init__(self, userid, password):
        self.userid = userid
        self.password = password
        self.shows = {}

        self.cj = cookielib.CookieJar()
        self.opener = urllib2.build_opener(
            urllib2.HTTPRedirectHandler(),
            urllib2.HTTPHandler(debuglevel=0),
            urllib2.HTTPSHandler(debuglevel=0),
            urllib2.HTTPCookieProcessor(self.cj)
        )
        self.opener.addheaders = [
            ('User-agent', 'Lynx/2.8.1pre.9 libwww-FM/2.14')
        ]

        login_data = urllib.urlencode({
            'email' : self.userid,
            'password' : self.password,
            'submit' : "Login",
            })
        login_url = "%s/%s" % (MYEPISODE_URL, "login/")
        self.send_req(login_url, login_data)
        settings_url = "%s/%s" % (MYEPISODE_URL, "settings/")
        data = self.send_req(settings_url)
        self.is_logged = True
        # Quickly check if it seems we are logged on.
        if (data is None) or (self.userid not in data):
            self.is_logged = False

    def send_req(self, url, data = None):
        try:
            response = self.opener.open(url, data)
            return ''.join(response.readlines())
        except:
            return None

    def get_show_list(self):
        # Populate shows with the list of show_ids in our account
        myshows_url = "%s/%s" % (MYEPISODE_URL, "myShows")
        data = self.send_req(myshows_url)
        if data is None:
            return False
        soup = BeautifulSoup(data)
        mylist = soup.find("div", {"class": re.compile(r'\bpageRowContainer\b')})
        mylist_tr = mylist.findAll("div", {"class": re.compile(r'\bbigBannerContainer\b')})

        for row in mylist_tr:
            link = row.find('a', {'href': True})
            link_url = link.get('href')
            showid = link_url.split('/')[-1]
            key = link.get('title').strip()
            sanitized_key = sanitize(key, '')
            if sanitized_key != key:
                key = ";".join([key, sanitized_key])
            self.shows[key.lower()] = int(showid)
        return True

    def find_show_link(self, data, show_name, strict=False):
        if data is None:
            return None
        soup = BeautifulSoup(data)
        tvshownames = soup.findAll("div", {"class": re.compile(r'\btvShowName\b')})

        show_href = None
        show_name = show_name.lower()
        for show in tvshownames:
            link = show.find("a", href=True)
            if link.string is None:
                continue
            if strict:
                if link.string.lower() == show_name:
                    show_href = link.get('href')
                    break
            else:
                if link.string.lower().startswith(show_name):
                    show_href = link.get('href')
                    break
        return show_href

    def find_show_id(self, show_name):
        # Try to find the ID of the show in our account first
        # Create a slice with only the show that may match
        slice_show  = {}
        show_name = show_name.lower()
        
        for keys, v in self.shows.iteritems():
            if ';' in keys:
                keys = keys.split(';')
            else:
                keys = [keys,]
            for k in keys:
                if show_name in k or show_name.startswith(k):
                    slice_show[k] = v
        if len(slice_show) == 1:
            return slice_show.values()[0]
        # We loop through a slice containings the possibilities and we
        # search strictly for the show name.
        for key, value in slice_show.iteritems():
            if key == show_name:
                return value

        # You should really never fall there, at this point, the show should be
        # in your account, except if you disabled the feature.

        # It's not in our account yet ?
        # Try Find a show through its name and report its id
        search_data = urllib.urlencode({
            'keyword' : show_name,
            })
        search_url = "%s/%s" % (MYEPISODE_URL, "search")
        data = self.send_req(search_url, search_data)
        show_href = self.find_show_link(data, show_name)

        # TODO: try to automatically request a show to be added to MEC
        # TODO: check if this is working for MEC
        if show_href is None:
            # Try to lookup the list of all the shows to find the exact title
            list_url = "%s/%s/%s" % (MYEPISODE_URL, "allShows/filter-by-name",
                    show_name[0].upper())
            data = self.send_req(list_url)
            show_href = self.find_show_link(data, show_name, strict=True)

        # Really did not find anything :'(
        if show_href is None:
            return None

        showid = show_href.split('/')[-1]

        if showid is None:
            return None
        return int(showid.strip())

    # This is totally stolen from script.xbmc.subtitles plugin !
    def get_info(self, file_name):
        title = None
        episode = None
        season = None
        for regex in REGEX_EXPRESSIONS:
            response_file = re.findall(regex, file_name)
            if len(response_file) > 0 :
                season = response_file[0][0]
                episode = response_file[0][1]
            else:
                continue
            title = re.split(regex, file_name)[0]
            title = sanitize(title, ' ')
            title = title.strip()
            return title.title(), season, episode
        return None, None, None

    def add_show(self, show_id):
        # Try to add the show to your account.
        tracklist_data = urllib.urlencode({
            'tvShowID' : show_id,
            'type' : "add",
            })
        url = "%s/actions/trackList.php" % MYEPISODE_URL
        data = self.send_req(url, tracklist_data)
        if data is None:
            return False
        # Update list
        self.get_show_list()
        return True

    def set_episode_watched(self, show_id, season, episode):
        # http://www.myepisodecalendar.com/episodeSummaries/Family-Guy/68/Season-1
        season_url = "%s/episodes//%d/Season-%d" % (MYEPISODE_URL,
                show_id, int(season))
        episode = int(episode)

        season_data = self.send_req(season_url)
        soup = BeautifulSoup(season_data)

        divs_epno = soup.findAll("div", {"id": "episodeNo"})
        for epnodiv in divs_epno:
            try:
                intContent = int(epnodiv.string.strip())
            except:
                continue
            else:
                if intContent == int(episode):
                    div_epno = epnodiv
                    break

        # episode could not be found on this page...
        if div_epno is None:
            return False

        episode_id = re.findall('[^\d](\d+)$', div_epno.parent.get("id"))[0]

        episode_add_data = urllib.urlencode({
            'episodeID' : episode_id,
            'season' : int(season),
            'tvShowID' : show_id,
            'type' : "add",
            })
        seen_url = "%s/actions/watchList.php" % MYEPISODE_URL
        data = self.send_req(seen_url, episode_add_data)

        if data is None:
            return False
        return True

