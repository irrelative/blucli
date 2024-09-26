import curses
import time
import requests
from typing import List, Optional, Tuple, Union
from player import BlusoundPlayer, PlayerStatus, threaded_discover
import logging


# Set up logging
logging.basicConfig(filename='logs/cli.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

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

def display_player_selection(stdscr: curses.window, players: List[BlusoundPlayer], selected_index: int, active_player: Optional[BlusoundPlayer]) -> None:
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

def display_player_control(stdscr: curses.window, active_player: BlusoundPlayer, player_status: Optional[PlayerStatus]) -> None:
    stdscr.addstr(5, 2, "UP/DOWN: volume, p/SPACE: play/pause, >/<: skip/back, i: select input, b: back to player list, q: quit")
    if active_player and isinstance(player_status, PlayerStatus):
        stdscr.addstr(8, 2, f"Active Player: {active_player.name}")
        stdscr.addstr(9, 2, f"Status: {player_status.state}")
        volume_bar = create_volume_bar(player_status.volume)
        stdscr.addstr(10, 2, f"Volume: {volume_bar} {player_status.volume}%")
        stdscr.addstr(11, 2, f"Now Playing: {player_status.name} - {player_status.artist}")
        stdscr.addstr(12, 2, f"Album: {player_status.album}")
        stdscr.addstr(13, 2, f"Service: {player_status.service}")
        
        stdscr.addstr(15, 2, "Available Inputs:")
        for i, input_data in enumerate(active_player.inputs):
            if status.inputId and input_data.id == status.inputId:
                stdscr.attron(curses.color_pair(2))
                stdscr.addstr(16 + i, 4, f"* {input_data.text} ({input_data.input_type})")
                stdscr.attroff(curses.color_pair(2))
            else:
                stdscr.addstr(16 + i, 4, f"  {input_data.text} ({input_data.input_type})")

def display_input_selection(stdscr: curses.window, active_player: BlusoundPlayer, selected_input_index: int) -> None:
    stdscr.addstr(5, 2, "UP/DOWN: select input, ENTER: confirm selection, b: back to player control")
    stdscr.addstr(8, 2, "Select Input:")
    for i, input_data in enumerate(active_player.inputs):
        if i == selected_input_index:
            stdscr.attron(curses.color_pair(2))
            stdscr.addstr(9 + i, 4, f"> {input_data.text} ({input_data.input_type})")
            stdscr.attroff(curses.color_pair(2))
        else:
            stdscr.addstr(9 + i, 4, f"  {input_data.text} ({input_data.input_type})")

def handle_player_selection(key: int, selected_index: int, players: List[BlusoundPlayer], active_player: Optional[BlusoundPlayer]) -> Tuple[bool, Optional[BlusoundPlayer], Optional[PlayerStatus]]:
    if key == KEY_UP and selected_index > 0:
        selected_index -= 1
    elif key == KEY_DOWN and selected_index < len(players) - 1:
        selected_index += 1
    elif key == KEY_ENTER and players:
        active_player = players[selected_index]
        success, result = active_player.get_status()
        if success and isinstance(result, PlayerStatus):
            return True, active_player, result
        else:
            return False, active_player, None
    return False, active_player, None

def handle_player_control(key: int, active_player: BlusoundPlayer, player_status: Optional[PlayerStatus], title_win: curses.window, stdscr: curses.window) -> Tuple[bool, bool, Optional[PlayerStatus]]:
    new_status = None
    if key == KEY_B:
        return False, False, None
    elif key == KEY_UP:
        update_header(title_win, "Increasing volume...")
        new_volume = min(100, player_status.volume + 5) if player_status else 5
        success, message = active_player.set_volume(new_volume)
        if success:
            success, new_status = active_player.get_status()
            if success:
                display_player_control(stdscr, active_player, new_status)
        update_header(title_win, message)
    elif key == KEY_DOWN:
        update_header(title_win, "Decreasing volume...")
        new_volume = max(0, player_status.volume - 5) if player_status else 0
        success, message = active_player.set_volume(new_volume)
        if success:
            success, new_status = active_player.get_status()
            if success:
                display_player_control(stdscr, active_player, new_status)
        update_header(title_win, message)
    elif (key == ord('p') or key == KEY_SPACE) and active_player:
        update_header(title_win, "Toggling play/pause...")
        if player_status and player_status.state == "play":
            success, message = active_player.pause()
        else:
            success, message = active_player.play()
        if success:
            success, new_status = active_player.get_status()
        update_header(title_win, message)
    elif key == ord('>') and active_player:
        update_header(title_win, "Skipping to next track...")
        success, message = active_player.skip()
        if success:
            success, new_status = active_player.get_status()
        update_header(title_win, message)
    elif key == ord('<') and active_player:
        update_header(title_win, "Going to previous track...")
        success, message = active_player.back()
        if success:
            success, new_status = active_player.get_status()
        update_header(title_win, message)
    elif key == KEY_I:
        return True, True, None
    return True, False, new_status

def handle_input_selection(key: int, active_player: BlusoundPlayer, selected_input_index: int, title_win: curses.window) -> Tuple[bool, int, Optional[PlayerStatus]]:
    if key == KEY_B:
        return False, selected_input_index, None
    elif key == KEY_UP and selected_input_index > 0:
        selected_input_index -= 1
    elif key == KEY_DOWN and selected_input_index < len(active_player.inputs) - 1:
        selected_input_index += 1
    elif key == KEY_ENTER:
        selected_input = active_player.inputs[selected_input_index]
        update_header(title_win, f"Selecting input: {selected_input.text}")
        success, message = active_player.select_input(selected_input.input_type, selected_input.type_index)
        if success:
            success, new_status = active_player.get_status()
            if success:
                return False, selected_input_index, new_status
        update_header(title_win, message)
    return True, selected_input_index, None

def main(stdscr: curses.window) -> None:
    global input_selection_mode, selected_input_index

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
    player_status: Optional[PlayerStatus] = None

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
                player_mode, input_selection_mode, new_status = handle_player_control(key, active_player, player_status, title_win, stdscr)
                if new_status:
                    player_status = new_status
                if input_selection_mode:
                    selected_input_index = 0
            else:
                input_selection_mode, selected_input_index, new_status = handle_input_selection(key, active_player, selected_input_index, title_win)
                if new_status:
                    player_status = new_status

        # Update player status every 10 seconds
        current_time = time.time()
        if current_time - last_update_time >= 10:
            success, new_status = active_player.get_status()
            if success:
                player_status = new_status
            last_update_time = current_time
        
        # Refresh header
        update_header(title_win, "")

if __name__ == "__main__":
    curses.wrapper(main)
