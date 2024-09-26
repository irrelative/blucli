import requests
import xml.etree.ElementTree as ET
import time
import threading
import logging
from dataclasses import dataclass
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
from typing import List, Dict, Tuple, Optional, Union
import os

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Set up logging
logging.basicConfig(filename='logs/cli.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

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
class PlayerInput:
    type_index: str
    player_name: str
    text: str
    input_type: str
    id: str
    url: str
    image: str
    type: str

class BlusoundPlayer:
    def __init__(self, host_name, name):
        self.host_name = host_name
        self.name = name
        self.base_url = f"http://{self.host_name}:11000"
        self.inputs: List[PlayerInput] = []
        logger.info(f"Initialized BlusoundPlayer: {self.name} at {self.host_name}")
        self.capture_inputs()

    def capture_inputs(self) -> None:
        url = f"{self.base_url}/RadioBrowse"
        params = {'service': 'Capture'}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            self.inputs = []
            for item in root.findall('item'):
                input_data = PlayerInput(
                    type_index=item.get('typeIndex', ''),
                    player_name=item.get('playerName', ''),
                    text=item.get('text', ''),
                    input_type=item.get('inputType', ''),
                    id=item.get('id', ''),
                    url=item.get('URL', ''),
                    image=item.get('image', ''),
                    type=item.get('type', '')
                )
                self.inputs.append(input_data)
            logger.info(f"Captured {len(self.inputs)} inputs for {self.name}")
        except requests.RequestException as e:
            logger.error(f"Error capturing inputs for {self.name}: {str(e)}")

    def get_status(self, timeout: Optional[int] = None, etag: Optional[str] = None) -> Tuple[bool, Union[PlayerStatus, str]]:
        url = f"{self.base_url}/Status"
        params = {}
        if timeout:
            params['timeout'] = timeout
        if etag:
            params['etag'] = etag

        logger.debug(f"Getting status for {self.name}")
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            logger.info(f"Got status for {self.name}: {response.text}")
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
        url = f"{self.base_url}/Volume"
        params = {'level': volume}
        logger.info(f"Setting volume for {self.name} to {volume}")
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return True, "Volume set successfully"
        except requests.RequestException as e:
            logger.error(f"Error setting volume for {self.name}: {str(e)}")
            return False, str(e)

    def toggle_play_pause(self) -> Tuple[bool, str]:
        url = f"{self.base_url}/Pause?toggle=1"
        logger.info(f"Toggling play/pause for {self.name}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            return True, "Playback toggled successfully"
        except requests.RequestException as e:
            logger.error(f"Error toggling play/pause for {self.name}: {str(e)}")
            return False, str(e)

    def skip(self) -> Tuple[bool, str]:
        url = f"{self.base_url}/Skip"
        logger.info(f"Skipping track on {self.name}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            return True, "Skipped to next track successfully"
        except requests.RequestException as e:
            logger.error(f"Error skipping track on {self.name}: {str(e)}")
            return False, str(e)

    def back(self) -> Tuple[bool, str]:
        url = f"{self.base_url}/Back"
        logger.info(f"Going back a track on {self.name}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            return True, "Went back to previous track successfully"
        except requests.RequestException as e:
            logger.error(f"Error going back a track on {self.name}: {str(e)}")
            return False, str(e)

    def select_input(self, input_data: PlayerInput) -> Tuple[bool, str]:
        url = f"{self.base_url}/Play?url={input_data.url}"
        logger.info(f"Selecting input for {self.name}: type={input_data.input_type}, index={input_data.type_index}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            return True, "Input selected successfully"
        except requests.RequestException as e:
            logger.error(f"Error selecting input for {self.name}: {str(e)}")
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
