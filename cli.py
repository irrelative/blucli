import curses
import time
import threading
import requests
from player import BlusoundPlayer, PlayerStatus, threaded_discover

def create_volume_bar(volume, width=20):
    filled = int(volume / 100 * width)
    return f"[{'#' * filled}{'-' * (width - filled)}]"

# Define key codes
KEY_UP = curses.KEY_UP
KEY_DOWN = curses.KEY_DOWN
KEY_ENTER = 10
KEY_B = ord('b')
KEY_SPACE = ord(' ')

header_message = ""
header_message_time = 0

def update_header(title_win, message):
    global header_message, header_message_time
    title_win.clear()
    title_win.addstr(1, 2, "Blusound CLI", curses.A_BOLD)
    if message:
        header_message = message
        header_message_time = time.time()
    if time.time() - header_message_time < 2:
        title_win.addstr(1, 16, f" - {header_message}")
    title_win.refresh()

def update_player_status(active_player):
    global player_status
    if active_player:
        try:
            player_status = active_player.get_status()
        except requests.RequestException:
            pass

def main(stdscr):
    global player_status  # Make player_status global so it can be accessed in update_player_status

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
    player_mode = False  # False for player selection, True for player control

    # Set up a timer for updating player status
    last_update_time = 0

    # Main loop
    while True:
        # Update the screen
        stdscr.clear()
        stdscr.refresh()

        # Display the title
        update_header(title_win, "")

        if not player_mode:
            # Display instructions for player selection mode
            stdscr.addstr(5, 2, "Use UP/DOWN arrows to select, ENTER to activate, 'q' to quit")
            
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
        else:
            # Display instructions for player control mode
            stdscr.addstr(5, 2, "UP/DOWN: volume, p/SPACE: play/pause, >/<: skip/back, b: back to player list, q: quit")
            
            # Display active player status
            if active_player and player_status:
                stdscr.addstr(8, 2, f"Active Player: {active_player.name}")
                stdscr.addstr(9, 2, f"Status: {player_status.state}")
                volume_bar = create_volume_bar(player_status.volume)
                stdscr.addstr(10, 2, f"Volume: {volume_bar} {player_status.volume}%")
                stdscr.addstr(11, 2, f"Now Playing: {player_status.name} - {player_status.artist}")
                stdscr.addstr(12, 2, f"Album: {player_status.album}")
                stdscr.addstr(13, 2, f"Service: {player_status.service}")
                
                # Display captured inputs
                stdscr.addstr(15, 2, "Available Inputs:")
                for i, input_data in enumerate(active_player.inputs):
                    if player_status and input_data.id == player_status.inputId:
                        stdscr.attron(curses.color_pair(2))
                        stdscr.addstr(16 + i, 4, f"* {input_data.text} ({input_data.input_type})")
                        stdscr.attroff(curses.color_pair(2))
                    else:
                        stdscr.addstr(16 + i, 4, f"  {input_data.text} ({input_data.input_type})")

        # Get user input (with timeout)
        stdscr.timeout(100)  # Set timeout to 100ms
        key = stdscr.getch()

        if key == ord('q'):
            break
        elif not player_mode:
            if key == KEY_UP and selected_index > 0:
                selected_index -= 1
            elif key == KEY_DOWN and selected_index < len(players) - 1:
                selected_index += 1
            elif key == KEY_ENTER and players:
                active_player = players[selected_index]
                try:
                    player_status = active_player.get_status()
                    player_mode = True
                except requests.RequestException:
                    stdscr.addstr(height - 2, 2, "Error: Unable to connect to the player", curses.A_BOLD)
        else:
            if key == KEY_B:
                player_mode = False
            elif key == KEY_UP:
                if not player_mode and selected_index > 0:
                    selected_index -= 1
                elif player_mode and active_player:
                    update_header(title_win, "Increasing volume...")
                    try:
                        new_volume = min(100, player_status.volume + 5)
                        active_player.set_volume(new_volume)
                        player_status = active_player.get_status()
                    except requests.RequestException:
                        stdscr.addstr(height - 2, 2, "Error: Unable to change volume", curses.A_BOLD)
                    update_header(title_win, "")
            elif key == KEY_DOWN:
                if not player_mode and selected_index < len(players) - 1:
                    selected_index += 1
                elif player_mode and active_player:
                    update_header(title_win, "Decreasing volume...")
                    try:
                        new_volume = max(0, player_status.volume - 5)
                        active_player.set_volume(new_volume)
                        player_status = active_player.get_status()
                    except requests.RequestException:
                        stdscr.addstr(height - 2, 2, "Error: Unable to change volume", curses.A_BOLD)
                    update_header(title_win, "")
            elif (key == ord('p') or key == KEY_SPACE) and active_player:
                update_header(title_win, "Toggling play/pause...")
                try:
                    if player_status and player_status.state == "play":
                        active_player.pause()
                    else:
                        active_player.play()
                    player_status = active_player.get_status()
                except requests.RequestException:
                    stdscr.addstr(height - 2, 2, "Error: Unable to change playback state", curses.A_BOLD)
                update_header(title_win, "")
            elif key == ord('>') and active_player:
                update_header(title_win, "Skipping to next track...")
                try:
                    active_player.skip()
                    player_status = active_player.get_status()
                except requests.RequestException:
                    stdscr.addstr(height - 2, 2, "Error: Unable to skip track", curses.A_BOLD)
                update_header(title_win, "")
            elif key == ord('<') and active_player:
                update_header(title_win, "Going to previous track...")
                try:
                    active_player.back()
                    player_status = active_player.get_status()
                except requests.RequestException:
                    stdscr.addstr(height - 2, 2, "Error: Unable to go back", curses.A_BOLD)
                update_header(title_win, "")

        # Update player status every 10 seconds and refresh header
        current_time = time.time()
        if current_time - last_update_time >= 10:
            update_player_status(active_player)
            last_update_time = current_time
        
        # Refresh header to clear message after 2 seconds
        update_header(title_win, "")

if __name__ == "__main__":
    curses.wrapper(main)
