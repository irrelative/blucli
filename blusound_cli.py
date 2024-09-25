import curses
import time
import threading
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

# Define arrow key codes
KEY_UP = 65
KEY_DOWN = 66
KEY_ENTER = 10

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

def main(stdscr):
    # Clear screen
    stdscr.clear()

    # Hide the cursor
    curses.curs_set(0)

    # Define color pairs
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)

    # Create a window for the title
    height, width = stdscr.getmaxyx()
    title_win = curses.newwin(3, width, 0, 0)
    title_win.bkgd(' ', curses.color_pair(1))

    # Start discovering Blusound players in a separate thread
    players = threaded_discover()
    stdscr.addstr(5, 2, "Discovering Blusound players...")
    stdscr.refresh()

    selected_index = 0
    active_player = None
    player_status = None

    # Main loop
    while True:
        # Update the screen
        stdscr.clear()
        stdscr.refresh()

        # Display the title
        title_win.clear()
        title_win.addstr(1, 2, "Blusound CLI", curses.A_BOLD)
        title_win.refresh()

        # Display instructions
        stdscr.addstr(5, 2, "Use UP/DOWN arrows to select, ENTER to activate, 'q' to quit")
        stdscr.addstr(6, 2, "p: play/pause, +/-: volume up/down, >/<: skip/back")

        # Display discovered players
        stdscr.addstr(8, 2, "Discovered Blusound players:")
        for i, player in enumerate(players):
            if i == selected_index:
                stdscr.attron(curses.color_pair(2))
            if player == active_player:
                stdscr.addstr(9 + i, 4, f"* {player.name} ({player.host_name})")
            else:
                stdscr.addstr(9 + i, 4, f"  {player.name} ({player.host_name})")
            if i == selected_index:
                stdscr.attroff(curses.color_pair(2))

        # Display active player status
        if active_player and player_status:
            stdscr.addstr(9 + len(players) + 1, 2, f"Active Player: {active_player.name}")
            stdscr.addstr(9 + len(players) + 2, 2, f"Status: {player_status.state}")
            stdscr.addstr(9 + len(players) + 3, 2, f"Volume: {player_status.volume}")
            stdscr.addstr(9 + len(players) + 4, 2, f"Now Playing: {player_status.name} - {player_status.artist}")
            stdscr.addstr(9 + len(players) + 5, 2, f"Album: {player_status.album}")
            stdscr.addstr(9 + len(players) + 6, 2, f"Service: {player_status.service}")

        # Get user input (with timeout)
        stdscr.timeout(100)  # Set timeout to 100ms
        key = stdscr.getch()

        if key == ord('q'):
            break
        elif key == KEY_UP and selected_index > 0:
            selected_index -= 1
        elif key == KEY_DOWN and selected_index < len(players) - 1:
            selected_index += 1
        elif key == KEY_ENTER and players:
            active_player = players[selected_index]
            try:
                player_status = active_player.get_status()
            except requests.RequestException:
                stdscr.addstr(height - 2, 2, "Error: Unable to connect to the player", curses.A_BOLD)
        elif key == ord('p') and active_player:
            try:
                if player_status and player_status.state == "play":
                    active_player.pause()
                else:
                    active_player.play()
                player_status = active_player.get_status()
            except requests.RequestException:
                stdscr.addstr(height - 2, 2, "Error: Unable to change playback state", curses.A_BOLD)
        elif key == ord('+') and active_player:
            try:
                new_volume = min(100, player_status.volume + 5)
                active_player.set_volume(new_volume)
                player_status = active_player.get_status()
            except requests.RequestException:
                stdscr.addstr(height - 2, 2, "Error: Unable to change volume", curses.A_BOLD)
        elif key == ord('-') and active_player:
            try:
                new_volume = max(0, player_status.volume - 5)
                active_player.set_volume(new_volume)
                player_status = active_player.get_status()
            except requests.RequestException:
                stdscr.addstr(height - 2, 2, "Error: Unable to change volume", curses.A_BOLD)
        elif key == ord('>') and active_player:
            try:
                active_player.skip()
                player_status = active_player.get_status()
            except requests.RequestException:
                stdscr.addstr(height - 2, 2, "Error: Unable to skip track", curses.A_BOLD)
        elif key == ord('<') and active_player:
            try:
                active_player.back()
                player_status = active_player.get_status()
            except requests.RequestException:
                stdscr.addstr(height - 2, 2, "Error: Unable to go back", curses.A_BOLD)
        elif key == -1:
            # No input, update status if there's an active player
            if active_player:
                try:
                    player_status = active_player.get_status()
                except requests.RequestException:
                    pass

if __name__ == "__main__":
    curses.wrapper(main)
