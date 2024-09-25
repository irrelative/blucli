import curses
import time
import threading
import requests
from player import BlusoundPlayer, PlayerStatus, threaded_discover

# Define arrow key codes
KEY_UP = 65
KEY_DOWN = 66
KEY_ENTER = 10

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
