import logging
import async_timeout
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import requests
import json
import isodate

# to do list
# music/video 구분
# channel 지원
# debug : Youtube Playlist를 그대로 내 repository에 fork후에 HACS에서 download해보기

from random import randint
from .const import DOMAIN, ICON, CONF_APIKEY, CONF_PLAYLISTS, CONF_PLAYLIST_ID, CONF_PLAYLIST_NAME, BASE_URL, BASE_URL2, BASE_URL3, VIDEO_URL, MUSIC_URL, ATTR_SNIPPET, ATTR_TIT, ATTR_URL

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_APIKEY): cv.string,
    vol.Required(CONF_PLAYLISTS): vol.All(cv.ensure_list, [{
        vol.Required(CONF_PLAYLIST_ID): cv.string,
        vol.Required(CONF_PLAYLIST_NAME): cv.string,    # btchois: Optional->Required
    }]),
})

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):  # pylint: disable=unused-argument
    """Setup sensor platform."""
    apikey      = config[CONF_APIKEY]
    playlists   = config[CONF_PLAYLISTS]

    sensors = []

    session = async_create_clientsession(hass)

    for plist in playlists:
        sensor = YoutubeSensor(apikey, plist[CONF_PLAYLIST_ID], plist[CONF_PLAYLIST_NAME], session)

        await sensor.async_update()

        sensors += [ sensor ]

    async_add_entities(sensors, True)

class YoutubeSensor(Entity):
    """YouTube Sensor class"""
    def __init__(self, apikey, playlist_id, playlist_name, session):
        self._session       = session
        self._image         = None
        self._apikey        = apikey
        self._name          = playlist_name 
        self._playlist_id   = playlist_id
        self._playlist_name = playlist_name
        self._video_url     = None
        self._music_url     = None

        self._init          = False
        # btchois
        self._video_num   = 0
        self._play_id     = 0
        self._video_duration = None
        self._video_miniutes = 0

        _LOGGER.error(self._name)

        #self.data = {}
        self.playlist = []

    async def async_update(self):
        """Update sensor."""
        _LOGGER.debug('%s - Running update', self._name)

        # btchois
        res_json = { "nextPageToken": "Initial" }
        token = ''
        first = True

        #dict = {}
        try:

            if not self._init:
                while ('nextPageToken' in res_json):
                    if first:
                        url = BASE_URL.format(self._playlist_id, self._apikey)
                        first = False
                    else:
                        url = BASE_URL2.format(self._playlist_id, self._apikey, token) 

                    res = await self._session.get(url)
                    res_json = await res.json()
                    res_items = res_json['items']
                    #_LOGGER.error(res_items)

                    self._video_number = res_json['pageInfo']['totalResults']
                    if 'nextPageToken' in res_json:
                        token = res_json['nextPageToken']

                    init = False

                    for res_item in res_items:

                        title = res_item[ATTR_SNIPPET][ATTR_TIT]
                        if title == 'Private video':
                            continue

                        id    = res_item[ATTR_SNIPPET]['resourceId']['videoId']
                        kind  = res_item[ATTR_SNIPPET]['resourceId']['kind']
                        #url   = VIDEO_URL.format(id)
                        thumbnail_url    = res_item[ATTR_SNIPPET]['thumbnails']['default'][ATTR_URL]
                        thumbnail_medium = res_item[ATTR_SNIPPET]['thumbnails']['medium'][ATTR_URL]
                        thumbnail_high   = res_item[ATTR_SNIPPET]['thumbnails']['high'][ATTR_URL]

                        thumbnail_url = thumbnail_medium

                        #dict[id] = {
                        #    'video_id': id,
                        #    'title':    title,
                        #    'url':      url,
                        #    'thumbnail_url': thumbnail_url,
                        #    'kind' : kind,
                        #}

                        temp = {
                            'video_id': id,
                            'title':    title,
                        #    'url':      url,
                            'thumbnail_url': thumbnail_url,
                            'kind' : kind,
                        }

                        self.playlist.append(temp)
                        #_LOGGER.error(temp)

                #self.data = dict
                self._init = True

            if self._init:
                ri = randint(0, self._video_number-1)

                self._playlist_id = ri

                self._name           = self.playlist[ri]['title']
                self._image          = self.playlist[ri]['thumbnail_url']

                video_id             = self.playlist[ri]['video_id']
                _LOGGER.error('current video id: %s', video_id)

                self._video_url      = VIDEO_URL.format(video_id)
                self._music_url      = MUSIC_URL.format(video_id)
                
                # video duration
                url2 = BASE_URL3.format(video_id, self._apikey) 
                #_LOGGER.error('video url: %s', url2)

                res2 = await self._session.get(url2)
                res_json2 = await res2.json()
                res_items2 = res_json2['items']
                #_LOGGER.error('res_items2: %s', res_items2)

                #for res_item in res_items:
                video_duration = res_items2[0]['contentDetails']['duration']

                video_miniutes = 0
                if video_duration=='P0D':  # P0D means live
                    video_miniutes = -1
                else:
                    video_miniutes = int(isodate.parse_duration(video_duration).total_seconds()//60)
                self._video_miniutes = video_miniutes
                #_LOGGER.error('minutes: %s', video_miniutes)

        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error('%s - Could not update - %s', self._name, error)

    @property
    def name(self):
        """Name."""
        return self._name
        #return self._playlist_name

    @property
    def entity_picture(self):
        """Picture."""
        return self._image

    @property
    def entity_id(self):
        return 'sensor.youtube_{}'.format(self._playlist_name)

    @property
    def state(self):
        """State."""
        return self._video_url

    @property
    def icon(self):
        """Icon."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Attributes."""
        att = {}

        att['playlist_id'] = self._playlist_id
        att['playlist_name'] = self._playlist_name

        att['video_number'] = self._video_number
        att['video_title'] = self._name
        att['video_url'] = self._video_url
        att['music_url'] = self._music_url
        att['video_miniutes'] = self._video_miniutes

        #for key, val  in self.data.items():
        #    att[val['title']] = val['url']

        return att
