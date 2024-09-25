import curses
import time
import threading
import requests
from typing import List, Optional
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
KEY_I = ord('i')

header_message: str = ""
header_message_time: float = 0
input_selection_mode: bool = False
selected_input_index: int = 0
player_status: Optional[PlayerStatus] = None

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

def display_player_selection(stdscr, players, selected_index, active_player):
    stdscr.addstr(5, 2, "Use UP/DOWN arrows to select, ENTER to activate, 'q' to quit")
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

def display_player_control(stdscr, active_player, player_status):
    stdscr.addstr(5, 2, "UP/DOWN: volume, p/SPACE: play/pause, >/<: skip/back, i: select input, b: back to player list, q: quit")
    if active_player and player_status:
        stdscr.addstr(8, 2, f"Active Player: {active_player.name}")
        stdscr.addstr(9, 2, f"Status: {player_status.state}")
        volume_bar = create_volume_bar(player_status.volume)
        stdscr.addstr(10, 2, f"Volume: {volume_bar} {player_status.volume}%")
        stdscr.addstr(11, 2, f"Now Playing: {player_status.name} - {player_status.artist}")
        stdscr.addstr(12, 2, f"Album: {player_status.album}")
        stdscr.addstr(13, 2, f"Service: {player_status.service}")
        
        stdscr.addstr(15, 2, "Available Inputs:")
        for i, input_data in enumerate(active_player.inputs):
            if player_status and input_data.id == player_status.inputId:
                stdscr.attron(curses.color_pair(2))
                stdscr.addstr(16 + i, 4, f"* {input_data.text} ({input_data.input_type})")
                stdscr.attroff(curses.color_pair(2))
            else:
                stdscr.addstr(16 + i, 4, f"  {input_data.text} ({input_data.input_type})")

def display_input_selection(stdscr, active_player, selected_input_index):
    stdscr.addstr(5, 2, "UP/DOWN: select input, ENTER: confirm selection, b: back to player control")
    stdscr.addstr(8, 2, "Select Input:")
    for i, input_data in enumerate(active_player.inputs):
        if i == selected_input_index:
            stdscr.attron(curses.color_pair(2))
            stdscr.addstr(9 + i, 4, f"> {input_data.text} ({input_data.input_type})")
            stdscr.attroff(curses.color_pair(2))
        else:
            stdscr.addstr(9 + i, 4, f"  {input_data.text} ({input_data.input_type})")

def handle_player_selection(key, selected_index, players, active_player):
    if key == KEY_UP and selected_index > 0:
        selected_index -= 1
    elif key == KEY_DOWN and selected_index < len(players) - 1:
        selected_index += 1
    elif key == KEY_ENTER and players:
        active_player = players[selected_index]
        try:
            player_status = active_player.get_status()
            return True, active_player, player_status
        except requests.RequestException:
            return False, active_player, None
    return False, active_player, None

def handle_player_control(key, active_player, player_status, title_win):
    if key == KEY_B:
        return False, False
    elif key == KEY_UP:
        update_header(title_win, "Increasing volume...")
        try:
            new_volume = min(100, player_status.volume + 5)
            active_player.set_volume(new_volume)
            player_status = active_player.get_status()
        except requests.RequestException:
            pass
        update_header(title_win, "")
    elif key == KEY_DOWN:
        update_header(title_win, "Decreasing volume...")
        try:
            new_volume = max(0, player_status.volume - 5)
            active_player.set_volume(new_volume)
            player_status = active_player.get_status()
        except requests.RequestException:
            pass
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
            pass
        update_header(title_win, "")
    elif key == ord('>') and active_player:
        update_header(title_win, "Skipping to next track...")
        try:
            active_player.skip()
            player_status = active_player.get_status()
        except requests.RequestException:
            pass
        update_header(title_win, "")
    elif key == ord('<') and active_player:
        update_header(title_win, "Going to previous track...")
        try:
            active_player.back()
            player_status = active_player.get_status()
        except requests.RequestException:
            pass
        update_header(title_win, "")
    elif key == KEY_I:
        return True, True
    return True, False

def handle_input_selection(key, active_player, selected_input_index, title_win):
    if key == KEY_B:
        return False
    elif key == KEY_UP and selected_input_index > 0:
        selected_input_index -= 1
    elif key == KEY_DOWN and selected_input_index < len(active_player.inputs) - 1:
        selected_input_index += 1
    elif key == KEY_ENTER:
        selected_input = active_player.inputs[selected_input_index]
        update_header(title_win, f"Selecting input: {selected_input.text}")
        try:
            active_player.select_input(selected_input.input_type, selected_input.type_index)
            player_status = active_player.get_status()
            return False
        except requests.RequestException:
            pass
        update_header(title_win, "")
    return True

def main(stdscr: curses.window) -> None:
    global player_status, input_selection_mode, selected_input_index

    # Clear screen and initialize
    stdscr.clear()
    input_selection_mode = False
    selected_input_index = 0
    curses.curs_set(0)
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)

    # Create title window
    height, width = stdscr.getmaxyx()
    title_win: curses.window = curses.newwin(3, width, 0, 0)
    title_win.bkgd(' ', curses.color_pair(1))

    # Start discovering Blusound players
    players: List[BlusoundPlayer] = threaded_discover()
    stdscr.addstr(5, 2, "Discovering Blusound players...")
    stdscr.refresh()

    selected_index: int = 0
    active_player: Optional[BlusoundPlayer] = None
    player_mode: bool = False
    last_update_time: float = 0.0

    # Main loop
    while True:
        stdscr.clear()
        stdscr.refresh()
        update_header(title_win, "")

        if not player_mode:
            display_player_selection(stdscr, players, selected_index, active_player)
        else:
            if not input_selection_mode:
                display_player_control(stdscr, active_player, player_status)
            else:
                display_input_selection(stdscr, active_player, selected_input_index)

        # Get user input
        stdscr.timeout(100)
        key = stdscr.getch()

        if key == ord('q'):
            break
        elif not player_mode:
            player_mode, active_player, new_status = handle_player_selection(key, selected_index, players, active_player)
            if new_status:
                player_status = new_status
            elif active_player is None:
                stdscr.addstr(height - 2, 2, "Error: Unable to connect to the player", curses.A_BOLD)
        else:
            if not input_selection_mode:
                player_mode, input_selection_mode = handle_player_control(key, active_player, player_status, title_win)
                if input_selection_mode:
                    selected_input_index = 0
            else:
                input_selection_mode = handle_input_selection(key, active_player, selected_input_index, title_win)

        # Update player status every 10 seconds
        current_time = time.time()
        if current_time - last_update_time >= 10:
            update_player_status(active_player)
            last_update_time = current_time
        
        # Refresh header
        update_header(title_win, "")

if __name__ == "__main__":
    curses.wrapper(main)
