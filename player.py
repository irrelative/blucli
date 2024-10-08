import requests
import xml.etree.ElementTree as ET
import time
import threading
import logging
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass, field
import os
import xml.etree.ElementTree as ET

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Set up logging
log_file = 'logs/cli.log'
log_handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=1)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
log_handler.setFormatter(log_formatter)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

@dataclass
class PlayerStatus:
    etag: str = ''
    album: str = ''
    artist: str = ''
    name: str = ''
    state: str = ''
    volume: int = 0
    service: str = ''
    inputId: str = ''
    can_move_playback: bool = False
    can_seek: bool = False
    cursor: int = 0
    db: float = 0.0
    fn: str = ''
    image: str = ''
    indexing: int = 0
    mid: int = 0
    mode: int = 0
    mute: bool = False
    pid: int = 0
    prid: int = 0
    quality: int = 0
    repeat: int = 0
    service_icon: str = ''
    service_name: str = ''
    shuffle: bool = False
    sid: int = 0
    sleep: str = ''
    song: int = 0
    stream_format: str = ''
    sync_stat: int = 0
    title1: str = ''
    title2: str = ''
    title3: str = ''
    totlen: int = 0
    secs: int = 0

@dataclass
class PlayerSource:
    text: str
    image: str
    browse_key: Optional[str]
    play_url: Optional[str]
    input_type: Optional[str]
    type: str
    children: List['PlayerSource'] = field(default_factory=list)

class BlusoundPlayer:
    def __init__(self, host_name, name):
        self.host_name = host_name
        self.name = name
        self.base_url = f"http://{self.host_name}:11000"
        self.sources: List[PlayerSource] = []
        logger.info(f"Initialized BlusoundPlayer: {self.name} at {self.host_name}")
        self.initialize_sources()

    def request(self, url: str, params: Optional[Dict] = None) -> requests.Response:
        full_url = f"{self.base_url}{url}"
        logger.info(f"Sending request to: {full_url}")
        logger.info(f"Request params: {params}")
        response = requests.get(full_url, params=params)
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response content: {response.text}")
        response.raise_for_status()
        return response

    def capture_sources(self, browse_key: Optional[str] = None) -> List[PlayerSource]:
        url = "/Browse"
        params = {"key": browse_key} if browse_key else None
        try:
            response = self.request(url, params)
            root = ET.fromstring(response.text)
            sources = []
            for item in root.findall('item'):
                source = PlayerSource(
                    text=item.get('text', ''),
                    image=item.get('image', ''),
                    browse_key=item.get('browseKey'),
                    play_url=item.get('playURL'),
                    input_type=item.get('inputType'),
                    type=item.get('type', '')
                )
                sources.append(source)
            logger.info(f"Captured {len(sources)} sources for {self.name}")
            return sources
        except requests.RequestException as e:
            logger.error(f"Error capturing sources for {self.name}: {str(e)}")
            return []

    def get_nested_sources(self, source: PlayerSource) -> None:
        if source.browse_key:
            nested_sources = self.capture_sources(source.browse_key)
            if nested_sources:
                source.children = nested_sources
            else:
                logger.warning(f"No nested sources found for {source.text}")

    def initialize_sources(self) -> None:
        self.sources = self.capture_sources()
        if not self.sources:
            logger.warning(f"No sources found for {self.name}. Retrying...")
            time.sleep(1)  # Wait for a second before retrying
            self.sources = self.capture_sources()
        logger.info(f"Initialized {len(self.sources)} sources for {self.name}")

    def get_status(self, timeout: Optional[int] = None, etag: Optional[str] = None) -> Tuple[bool, Union[PlayerStatus, str]]:
        url = "/Status"
        params = {}
        if timeout:
            params['timeout'] = timeout
        if etag:
            params['etag'] = etag

        logger.debug(f"Getting status for {self.name}")
        try:
            response = self.request(url, params)
            root = ET.fromstring(response.text)
            
            def safe_find(element, tag, default=''):
                found = element.find(tag)
                return found.text if found is not None else default

            def safe_int(value, default=0):
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default

            status = PlayerStatus(
                etag=root.get('etag', ''),
                album=safe_find(root, 'album'),
                artist=safe_find(root, 'artist'),
                name=safe_find(root, 'title1'),
                state=safe_find(root, 'state'),
                volume=safe_int(safe_find(root, 'volume')),
                service=safe_find(root, 'service'),
                inputId=safe_find(root, 'inputId'),
                can_move_playback=safe_find(root, 'canMovePlayback') == 'true',
                can_seek=safe_int(safe_find(root, 'canSeek')) == 1,
                cursor=safe_int(safe_find(root, 'cursor')),
                db=float(safe_find(root, 'db', '0')),
                fn=safe_find(root, 'fn'),
                image=safe_find(root, 'image'),
                indexing=safe_int(safe_find(root, 'indexing')),
                mid=safe_int(safe_find(root, 'mid')),
                mode=safe_int(safe_find(root, 'mode')),
                mute=safe_int(safe_find(root, 'mute')) == 1,
                pid=safe_int(safe_find(root, 'pid')),
                prid=safe_int(safe_find(root, 'prid')),
                quality=safe_int(safe_find(root, 'quality')),
                repeat=safe_int(safe_find(root, 'repeat')),
                service_icon=safe_find(root, 'serviceIcon'),
                service_name=safe_find(root, 'serviceName'),
                shuffle=safe_int(safe_find(root, 'shuffle')) == 1,
                sid=safe_int(safe_find(root, 'sid')),
                sleep=safe_find(root, 'sleep'),
                song=safe_int(safe_find(root, 'song')),
                stream_format=safe_find(root, 'streamFormat'),
                sync_stat=safe_int(safe_find(root, 'syncStat')),
                title1=safe_find(root, 'title1'),
                title2=safe_find(root, 'title2'),
                title3=safe_find(root, 'title3'),
                totlen=safe_int(safe_find(root, 'totlen')),
                secs=safe_int(safe_find(root, 'secs'))
            )
            logger.info(f"Status for {self.name}: {status}")
            return True, status
        except requests.RequestException as e:
            logger.error(f"Error getting status for {self.name}: {str(e)}")
            return False, str(e)

    def set_volume(self, volume: int) -> Tuple[bool, str]:
        url = "/Volume"
        params = {'level': volume}
        logger.info(f"Setting volume for {self.name} to {volume}")
        try:
            self.request(url, params)
            return True, "Volume set successfully"
        except requests.RequestException as e:
            logger.error(f"Error setting volume for {self.name}: {str(e)}")
            return False, str(e)

    def toggle_play_pause(self) -> Tuple[bool, str]:
        url = "/Pause"
        params = {'toggle': 1}
        logger.info(f"Toggling play/pause for {self.name}")
        try:
            self.request(url, params)
            return True, "Playback toggled successfully"
        except requests.RequestException as e:
            logger.error(f"Error toggling play/pause for {self.name}: {str(e)}")
            return False, str(e)

    def skip(self) -> Tuple[bool, str]:
        url = "/Skip"
        logger.info(f"Skipping track on {self.name}")
        try:
            self.request(url)
            return True, "Skipped to next track successfully"
        except requests.RequestException as e:
            logger.error(f"Error skipping track on {self.name}: {str(e)}")
            return False, str(e)

    def back(self) -> Tuple[bool, str]:
        url = "/Back"
        logger.info(f"Going back a track on {self.name}")
        try:
            self.request(url)
            return True, "Went back to previous track successfully"
        except requests.RequestException as e:
            logger.error(f"Error going back a track on {self.name}: {str(e)}")
            return False, str(e)

    def select_input(self, source: PlayerSource) -> Tuple[bool, str]:
        if source.play_url:
            url = source.play_url
        elif source.browse_key:
            url = "/Browse"
            params = {'key': source.browse_key}
        else:
            return False, "Invalid source"
        logger.info(f"Selecting source for {self.name}: {source.text}")

        try:
            self.request(url, params if source.browse_key else None)
            return True, f"{source.text} selected successfully"
        except requests.RequestException as e:
            logger.error(f"Error selecting source for {self.name}: {str(e)}")
            return False, str(e)

class MyListener(ServiceListener):
    def __init__(self):
        self.players = []

    def add_service(self, zeroconf: Zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        ipv4 = [addr for addr in info.parsed_addresses() if addr.count('.') == 3][0]
        player = BlusoundPlayer(host_name=ipv4, name=info.server)
        self.players.append(player)
        logger.info(f"Discovered new player: {player.name} at {player.host_name}")

    def remove_service(self, zeroconf, type, name):
        self.players = [p for p in self.players if p.name != name]
        logger.info(f"Removed player: {name}")

    def update_service(self, zeroconf, type, name):
        logger.info(f"Updated service: {name}")

def discover(players):
    logger.info("Starting discovery process")
    zeroconf = Zeroconf()
    listener = MyListener()
    ServiceBrowser(zeroconf, "_musc._tcp.local.", listener)
    try:
        while True:
            time.sleep(1)
            players[:] = listener.players
    finally:
        zeroconf.close()
        logger.info("Discovery process ended")

def threaded_discover():
    logger.info("Starting threaded discovery")
    players = []
    discovery_thread = threading.Thread(target=discover, args=(players,), daemon=True)
    discovery_thread.start()
    return players
