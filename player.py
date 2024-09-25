import requests
import xml.etree.ElementTree as ET
import time
import threading
import logging
from dataclasses import dataclass
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

# Set up logging
logging.basicConfig(filename='cli.log', level=logging.INFO,
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

class BlusoundPlayer:
    def __init__(self, host_name, name):
        self.host_name = host_name
        self.name = name
        self.base_url = f"http://{self.host_name}:11000"
        logger.info(f"Initialized BlusoundPlayer: {self.name} at {self.host_name}")

    def get_status(self, timeout=None, etag=None):
        url = f"{self.base_url}/Status"
        params = {}
        if timeout:
            params['timeout'] = timeout
        if etag:
            params['etag'] = etag

        logger.debug(f"Getting status for {self.name}")
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
            name=safe_find(root, 'title1'),  # Changed from 'name' to 'title1'
            state=safe_find(root, 'state'),
            volume=safe_int(safe_find(root, 'volume')),
            service=safe_find(root, 'service')
        )
        logger.info(f"Status for {self.name}: {status}")
        return status

    def set_volume(self, volume):
        url = f"{self.base_url}/Volume"
        params = {'level': volume}
        logger.info(f"Setting volume for {self.name} to {volume}")
        response = requests.get(url, params=params)
        response.raise_for_status()

    def play(self):
        url = f"{self.base_url}/Play"
        logger.info(f"Playing {self.name}")
        response = requests.get(url)
        response.raise_for_status()

    def pause(self):
        url = f"{self.base_url}/Pause"
        logger.info(f"Pausing {self.name}")
        response = requests.get(url)
        response.raise_for_status()

    def skip(self):
        url = f"{self.base_url}/Skip"
        logger.info(f"Skipping track on {self.name}")
        response = requests.get(url)
        response.raise_for_status()

    def back(self):
        url = f"{self.base_url}/Back"
        logger.info(f"Going back a track on {self.name}")
        response = requests.get(url)
        response.raise_for_status()

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
    browser = ServiceBrowser(zeroconf, "_musc._tcp.local.", listener)
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
