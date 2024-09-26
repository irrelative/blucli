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
KEY_QUESTION = ord('?')

header_message: str = ""
show_shortcuts: bool = False
shortcuts_open: bool = False
selector_shortcuts_open: bool = False
header_message_time: float = 0
input_selection_mode: bool = False
selected_input_index: int = 0
player_status: Optional[PlayerStatus] = None

def update_header(title_win, message, view, active_player=None):
    global header_message, header_message_time
    title_win.clear()
    header = f"Blusound CLI - {view}"
    if active_player:
        header += f" - {active_player.name}"
    title_win.addstr(1, 2, header, curses.A_BOLD)
    if message:
        header_message = message
        header_message_time = time.time()
    if time.time() - header_message_time < 2:
        title_win.addstr(1, len(header) + 4, f"- {header_message}")
    title_win.refresh()

def update_player_status(active_player):
    global player_status
    if active_player:
        try:
            player_status = active_player.get_status()
        except requests.RequestException:
            pass

def display_player_selection(stdscr: curses.window, players: List[BlusoundPlayer], selected_index: int, active_player: Optional[BlusoundPlayer], selector_shortcuts_open: bool) -> None:
    if selector_shortcuts_open:
        display_selector_shortcuts(stdscr)
    else:
        stdscr.addstr(5, 2, "Discovered Blusound players:")
        for i, player in enumerate(players):
            if i == selected_index:
                stdscr.attron(curses.color_pair(2))
            if player == active_player:
                stdscr.addstr(6 + i, 4, f"* {player.name} ({player.host_name})")
            else:
                stdscr.addstr(6 + i, 4, f"  {player.name} ({player.host_name})")
            if i == selected_index:
                stdscr.attroff(curses.color_pair(2))
        stdscr.addstr(stdscr.getmaxyx()[0] - 1, 2, "Press '?' to show keyboard shortcuts")

def display_selector_shortcuts(stdscr: curses.window) -> None:
    height, width = stdscr.getmaxyx()
    modal_height, modal_width = 10, 50
    start_y, start_x = (height - modal_height) // 2, (width - modal_width) // 2

    modal_win = curses.newwin(modal_height, modal_width, start_y, start_x)
    modal_win.box()

    modal_win.addstr(1, 2, "Player Selector Shortcuts", curses.A_BOLD)

    shortcuts = [
        ("UP/DOWN", "Select player"),
        ("ENTER", "Activate player"),
        ("q", "Quit application"),
    ]

    for i, (key, description) in enumerate(shortcuts):
        modal_win.addstr(3 + i, 2, f"{key:<10} : {description}")

    modal_win.addstr(modal_height - 2, 2, "Press any key to close", curses.A_ITALIC)
    modal_win.refresh()

def display_player_control(stdscr: curses.window, active_player: BlusoundPlayer, player_status: Optional[PlayerStatus], show_shortcuts: bool) -> None:
    if show_shortcuts:
        display_shortcuts(stdscr)
    elif active_player and isinstance(player_status, PlayerStatus):
        stdscr.addstr(5, 2, f"Status: {player_status.state}")
        volume_bar = create_volume_bar(player_status.volume)
        stdscr.addstr(6, 2, f"Volume: {volume_bar} {player_status.volume}%")
        stdscr.addstr(7, 2, f"Now Playing: {player_status.name} - {player_status.artist}")
        stdscr.addstr(8, 2, f"Album: {player_status.album}")
        stdscr.addstr(9, 2, f"Service: {player_status.service}")
        
        stdscr.addstr(12, 2, "Active Input:")
        active_input = next((input_data for input_data in active_player.inputs if input_data.id == player_status.inputId), None)
        if active_input:
            stdscr.attron(curses.color_pair(2))
            stdscr.addstr(13, 4, f"* {active_input.text} ({active_input.input_type})")
            stdscr.attroff(curses.color_pair(2))
        else:
            stdscr.addstr(13, 4, "No active input")
        
        stdscr.addstr(stdscr.getmaxyx()[0] - 1, 2, "Press '?' to show keyboard shortcuts")

def display_shortcuts(stdscr: curses.window) -> None:
    height, width = stdscr.getmaxyx()
    modal_height, modal_width = 12, 50
    start_y, start_x = (height - modal_height) // 2, (width - modal_width) // 2

    # Create a new window for the modal
    modal_win = curses.newwin(modal_height, modal_width, start_y, start_x)
    modal_win.box()

    # Add title
    modal_win.addstr(1, 2, "Keyboard Shortcuts", curses.A_BOLD)

    # Add shortcuts
    shortcuts = [
        ("UP/DOWN", "Adjust volume"),
        ("p/SPACE", "Play/Pause"),
        (">/<", "Skip/Previous track"),
        ("i", "Select input"),
        ("b", "Back to player list"),
        ("q", "Quit application"),
    ]

    for i, (key, description) in enumerate(shortcuts):
        modal_win.addstr(3 + i, 2, f"{key:<10} : {description}")

    modal_win.addstr(modal_height - 2, 2, "Press any key to close", curses.A_ITALIC)
    modal_win.refresh()

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

def handle_player_selection(key: int, selected_index: int, players: List[BlusoundPlayer], active_player: Optional[BlusoundPlayer], selector_shortcuts_open: bool) -> Tuple[bool, Optional[BlusoundPlayer], Optional[PlayerStatus], bool]:
    if selector_shortcuts_open:
        return False, active_player, None, False
    if key == KEY_UP and selected_index > 0:
        selected_index -= 1
    elif key == KEY_DOWN and selected_index < len(players) - 1:
        selected_index += 1
    elif key == KEY_ENTER and players:
        active_player = players[selected_index]
        success, result = active_player.get_status()
        if success and isinstance(result, PlayerStatus):
            return True, active_player, result, False
        else:
            return False, active_player, None, False
    elif key == KEY_QUESTION:
        return False, active_player, None, True
    return False, active_player, None, False

def handle_player_control(key: int, active_player: Optional[BlusoundPlayer], player_status: Optional[PlayerStatus], title_win: curses.window, stdscr: curses.window) -> Tuple[bool, bool, Optional[PlayerStatus], bool]:
    global shortcuts_open
    new_status = None
    if key == KEY_B:
        return False, False, None, False
    elif key == KEY_UP and active_player:
        update_header(title_win, "Increasing volume...", "Player Control")
        new_volume = min(100, player_status.volume + 5) if player_status else 5
        success, message = active_player.set_volume(new_volume)
        if success:
            success, new_status = active_player.get_status()
            if success:
                display_player_control(stdscr, active_player, new_status, shortcuts_open)
        update_header(title_win, message, "Player Control")
    elif key == KEY_DOWN:
        update_header(title_win, "Decreasing volume...", "Player Control")
        new_volume = max(0, player_status.volume - 5) if player_status else 0
        success, message = active_player.set_volume(new_volume)
        if success:
            success, new_status = active_player.get_status()
            if success:
                display_player_control(stdscr, active_player, new_status, shortcuts_open)
        update_header(title_win, message, "Player Control")
    elif (key == ord('p') or key == KEY_SPACE) and active_player:
        update_header(title_win, "Toggling play/pause...", "Player Control")
        if player_status and player_status.state == "play":
            success, message = active_player.pause()
        else:
            success, message = active_player.play()
        if success:
            success, new_status = active_player.get_status()
        update_header(title_win, message, "Player Control")
    elif key == ord('>') and active_player:
        update_header(title_win, "Skipping to next track...", "Player Control")
        success, message = active_player.skip()
        if success:
            success, new_status = active_player.get_status()
        update_header(title_win, message, "Player Control")
    elif key == ord('<') and active_player:
        update_header(title_win, "Going to previous track...", "Player Control")
        success, message = active_player.back()
        if success:
            success, new_status = active_player.get_status()
        update_header(title_win, message, "Player Control")
    elif key == KEY_I:
        return True, True, None, False
    elif key == KEY_QUESTION:
        shortcuts_open = not shortcuts_open
    return True, False, new_status, shortcuts_open

def handle_input_selection(key: int, active_player: BlusoundPlayer, selected_input_index: int, title_win: curses.window) -> Tuple[bool, int, Optional[PlayerStatus]]:
    if key == KEY_B:
        return False, selected_input_index, None
    elif key == KEY_UP and selected_input_index > 0:
        selected_input_index -= 1
    elif key == KEY_DOWN and selected_input_index < len(active_player.inputs) - 1:
        selected_input_index += 1
    elif key == KEY_ENTER:
        selected_input = active_player.inputs[selected_input_index]
        update_header(title_win, f"Selecting input: {selected_input.text}", "Input Selection")
        success, message = active_player.select_input(selected_input)
        if success:
            success, new_status = active_player.get_status()
            if success:
                return False, selected_input_index, new_status
        update_header(title_win, message, "Input Selection")
    return True, selected_input_index, None

def main(stdscr: curses.window) -> None:
    global input_selection_mode, selected_input_index, shortcuts_open, selector_shortcuts_open

    # Clear screen and initialize
    stdscr.clear()
    input_selection_mode = False
    selected_input_index = 0
    shortcuts_open = False
    selector_shortcuts_open = False
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
        if not player_mode:
            update_header(title_win, "", "Player Selection")
            display_player_selection(stdscr, players, selected_index, active_player, selector_shortcuts_open)
        else:
            if not input_selection_mode:
                update_header(title_win, "", "Player Control", active_player)
                display_player_control(stdscr, active_player, player_status, shortcuts_open)
            else:
                update_header(title_win, "", "Input Selection", active_player)
                display_input_selection(stdscr, active_player, selected_input_index)

        # Get user input
        stdscr.timeout(100)
        key = stdscr.getch()

        if key == ord('q'):
            break
        elif not player_mode:
            if selector_shortcuts_open:
                if key != -1:
                    selector_shortcuts_open = False
            else:
                player_mode, active_player, new_status, selector_shortcuts_open = handle_player_selection(key, selected_index, players, active_player, selector_shortcuts_open)
                if new_status:
                    player_status = new_status
                elif active_player is None:
                    stdscr.addstr(height - 2, 2, "Error: Unable to connect to the player", curses.A_BOLD)
        else:
            if shortcuts_open:
                if key != -1:
                    shortcuts_open = False
            elif not input_selection_mode:
                player_mode, input_selection_mode, new_status, shortcuts_open = handle_player_control(key, active_player, player_status, title_win, stdscr)
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
        if active_player and current_time - last_update_time >= 10:
            success, new_status = active_player.get_status()
            if success:
                player_status = new_status
            last_update_time = current_time
        
        # Refresh header
        update_header(title_win, "", "Player Selection" if not player_mode else "Player Control")

if __name__ == "__main__":
    curses.wrapper(main)
