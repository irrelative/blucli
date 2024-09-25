import curses
import time
import threading
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

# Define arrow key codes
KEY_UP = 65
KEY_DOWN = 66
KEY_ENTER = 10

class BlusoundPlayer:
    def __init__(self, host_name, name):
        self.host_name = host_name
        self.name = name

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

        # Display discovered players
        stdscr.addstr(7, 2, "Discovered Blusound players:")
        for i, player in enumerate(players):
            if i == selected_index:
                stdscr.attron(curses.color_pair(2))
            if player == active_player:
                stdscr.addstr(8 + i, 4, f"* {player.name} ({player.host_name})")
            else:
                stdscr.addstr(8 + i, 4, f"  {player.name} ({player.host_name})")
            if i == selected_index:
                stdscr.attroff(curses.color_pair(2))

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
        elif key == -1:
            # No input, continue to next iteration
            continue

if __name__ == "__main__":
    curses.wrapper(main)
