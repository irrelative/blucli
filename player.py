import requests
import xml.etree.ElementTree as ET
import time
import threading
from dataclasses import dataclass
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

@dataclass
class PlayerStatus:
    etag: str
    album: str
    artist: str
    name: str
    state: str
    volume: int
    service: str

class BlusoundPlayer:
    def __init__(self, host_name, name):
        self.host_name = host_name
        self.name = name
        self.base_url = f"http://{self.host_name}:11000"

    def get_status(self, timeout=None, etag=None):
        url = f"{self.base_url}/Status"
        params = {}
        if timeout:
            params['timeout'] = timeout
        if etag:
            params['etag'] = etag

        response = requests.get(url, params=params)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        return PlayerStatus(
            etag=root.get('etag'),
            album=root.find('album').text,
            artist=root.find('artist').text,
            name=root.find('name').text,
            state=root.find('state').text,
            volume=int(root.find('volume').text),
            service=root.find('service').text
        )

    def set_volume(self, volume):
        url = f"{self.base_url}/Volume"
        params = {'level': volume}
        response = requests.get(url, params=params)
        response.raise_for_status()

    def play(self):
        url = f"{self.base_url}/Play"
        response = requests.get(url)
        response.raise_for_status()

    def pause(self):
        url = f"{self.base_url}/Pause"
        response = requests.get(url)
        response.raise_for_status()

    def skip(self):
        url = f"{self.base_url}/Skip"
        response = requests.get(url)
        response.raise_for_status()

    def back(self):
        url = f"{self.base_url}/Back"
        response = requests.get(url)
        response.raise_for_status()

class MyListener(ServiceListener):
    def __init__(self):
        self.players = []

    def add_service(self, zeroconf: Zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        ipv4 = [addr for addr in info.parsed_addresses() if addr.count('.') == 3][0]
        self.players.append(BlusoundPlayer(host_name=ipv4, name=info.server))

    def remove_service(self, zeroconf, type, name):
        self.players = [p for p in self.players if p.name != name]

    def update_service(self, zeroconf, type, name):
        pass

def discover(players):
    zeroconf = Zeroconf()
    listener = MyListener()
    browser = ServiceBrowser(zeroconf, "_musc._tcp.local.", listener)
    try:
        while True:
            time.sleep(1)
            players[:] = listener.players
    finally:
        zeroconf.close()

def threaded_discover():
    players = []
    discovery_thread = threading.Thread(target=discover, args=(players,), daemon=True)
    discovery_thread.start()
    return players
