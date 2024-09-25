import curses
import time
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

def main(stdscr):
    # Clear screen
    stdscr.clear()

    # Hide the cursor
    curses.curs_set(0)

    # Define color pairs
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)

    # Create a window for the title
    height, width = stdscr.getmaxyx()
    title_win = curses.newwin(3, width, 0, 0)
    title_win.bkgd(' ', curses.color_pair(1))

    # Discover Blusound players
    stdscr.addstr(5, 2, "Discovering Blusound players...")
    stdscr.refresh()
    players = discover()

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
        stdscr.addstr(5, 2, "Press 'q' to quit")

        # Display discovered players
        stdscr.addstr(7, 2, "Discovered Blusound players:")
        for i, player in enumerate(players, start=1):
            stdscr.addstr(8 + i, 4, f"{i}. {player.name} ({player.host_name})")

        # Get user input
        key = stdscr.getch()

        if key == ord('q'):
            break

        # Small delay to reduce CPU usage
        time.sleep(0.1)

if __name__ == "__main__":
    curses.wrapper(main)
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

def discover():
    zeroconf = Zeroconf()
    listener = MyListener()
    browser = ServiceBrowser(zeroconf, "_musc._tcp.local.", listener)
    time.sleep(5)  # Wait for 5 seconds to discover players
    zeroconf.close()
    return listener.players
