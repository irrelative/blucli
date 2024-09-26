import curses
import time
import requests
from typing import List, Optional, Tuple
from player import BlusoundPlayer, PlayerStatus, threaded_discover
import logging

# Set up logging
logging.basicConfig(filename='logs/cli.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# Define key codes
KEY_UP = curses.KEY_UP
KEY_DOWN = curses.KEY_DOWN
KEY_ENTER = 10
KEY_B = ord('b')
KEY_SPACE = ord(' ')
KEY_I = ord('i')
KEY_QUESTION = ord('?')
KEY_D = ord('d')
KEY_P = ord('p')
KEY_RIGHT = ord('>')
KEY_LEFT = ord('<')

def create_volume_bar(volume, width=20):
    filled = int(volume / 100 * width)
    return f"[{'#' * filled}{'-' * (width - filled)}]"

class BlusoundCLI:
    def __init__(self):
        self.header_message: str = ""
        self.header_message_time: float = 0
        self.shortcuts_open: bool = False
        self.selector_shortcuts_open: bool = False
        self.input_selection_mode: bool = False
        self.selected_input_index: int = 0
        self.player_status: Optional[PlayerStatus] = None
        self.detail_view: bool = False
        self.selected_index: int = 0
        self.active_player: Optional[BlusoundPlayer] = None
        self.players: List[BlusoundPlayer] = []
        self.last_update_time: float = 0.0

    def update_header(self, title_win: curses.window, message: str, view: str, active_player: Optional[BlusoundPlayer] = None):
        title_win.clear()
        header = f"Blusound CLI - {view}"
        if active_player:
            header += f" - {active_player.name}"
        title_win.addstr(1, 2, header, curses.A_BOLD)
        if message:
            self.header_message = message
            self.header_message_time = time.time()
        if time.time() - self.header_message_time < 2:
            title_win.addstr(1, len(header) + 4, f"- {self.header_message}")
        title_win.refresh()

    def update_player_status(self):
        if self.active_player:
            try:
                self.player_status = self.active_player.get_status()
            except requests.RequestException as e:
                logger.error(f"Error updating player status: {e}")

    def display_player_selection(self, stdscr: curses.window):
        if self.selector_shortcuts_open:
            self.display_selector_shortcuts(stdscr)
        else:
            stdscr.addstr(5, 2, "Discovered Blusound players:")
            for i, player in enumerate(self.players):
                if i == self.selected_index:
                    stdscr.attron(curses.color_pair(2))
                if player == self.active_player:
                    stdscr.addstr(6 + i, 4, f"* {player.name} ({player.host_name})")
                else:
                    stdscr.addstr(6 + i, 4, f"  {player.name} ({player.host_name})")
                if i == self.selected_index:
                    stdscr.attroff(curses.color_pair(2))
            stdscr.addstr(stdscr.getmaxyx()[0] - 1, 2, "Press '?' to show keyboard shortcuts")

    def display_selector_shortcuts(self, stdscr: curses.window):
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

    def display_player_control(self, stdscr: curses.window):
        if self.shortcuts_open:
            self.display_shortcuts(stdscr)
        elif self.active_player and isinstance(self.player_status, PlayerStatus):
            if self.detail_view:
                self.display_detail_view(stdscr)
            else:
                self.display_summary_view(stdscr)
            stdscr.addstr(stdscr.getmaxyx()[0] - 1, 2, "Press '?' for shortcuts, 'd' for detail view")

    def display_summary_view(self, stdscr: curses.window):
        player_status = self.player_status
        active_player = self.active_player
        labels = ["Status", "Volume", "Now Playing", "Album", "Service", "Active Input"]
        max_label_width = max(len(label) for label in labels)

        stdscr.addstr(5, 2, f"{'Status:':<{max_label_width + 1}} {player_status.state}")
        volume_bar = create_volume_bar(player_status.volume)
        stdscr.addstr(6, 2, f"{'Volume:':<{max_label_width + 1}} {volume_bar} {player_status.volume}%")
        stdscr.addstr(7, 2, f"{'Now Playing:':<{max_label_width + 1}} {player_status.name} - {player_status.artist}")
        stdscr.addstr(8, 2, f"{'Album:':<{max_label_width + 1}} {player_status.album}")
        stdscr.addstr(9, 2, f"{'Service:':<{max_label_width + 1}} {player_status.service}")

        active_input = next((input_data for input_data in active_player.inputs if input_data.id == player_status.inputId), None)
        if active_input:
            stdscr.addstr(10, 2, f"{'Active Input:':<{max_label_width + 1}} {active_input.text} ({active_input.input_type})")
        else:
            stdscr.addstr(10, 2, f"{'Active Input:':<{max_label_width + 1}} No active input")

    def display_detail_view(self, stdscr: curses.window):
        player_status = self.player_status
        height, width = stdscr.getmaxyx()
        attributes = vars(player_status)
        max_label_width = max(len(attr) for attr in attributes)

        y = 5
        for attr, value in attributes.items():
            if y >= height - 2:
                break
            label = f"{attr}:"
            value_str = str(value)
            if len(value_str) > width - max_label_width - 5:
                value_str = value_str[:width - max_label_width - 8] + "..."
            stdscr.addstr(y, 2, f"{label:<{max_label_width + 1}} {value_str}")
            y += 1

    def display_shortcuts(self, stdscr: curses.window):
        height, width = stdscr.getmaxyx()
        modal_height, modal_width = 12, 50
        start_y, start_x = (height - modal_height) // 2, (width - modal_width) // 2

        modal_win = curses.newwin(modal_height, modal_width, start_y, start_x)
        modal_win.box()

        modal_win.addstr(1, 2, "Keyboard Shortcuts", curses.A_BOLD)

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

    def display_input_selection(self, stdscr: curses.window):
        active_player = self.active_player
        selected_input_index = self.selected_input_index
        stdscr.addstr(5, 2, "UP/DOWN: select input, ENTER: confirm selection, b: back to player control")
        stdscr.addstr(8, 2, "Select Input:")
        for i, input_data in enumerate(active_player.inputs):
            if i == selected_input_index:
                stdscr.attron(curses.color_pair(2))
                stdscr.addstr(9 + i, 4, f"> {input_data.text} ({input_data.input_type})")
                stdscr.attroff(curses.color_pair(2))
            else:
                stdscr.addstr(9 + i, 4, f"  {input_data.text} ({input_data.input_type})")

    def handle_player_selection(self, key: int) -> Tuple[bool, Optional[BlusoundPlayer], bool]:
        if self.selector_shortcuts_open:
            return False, self.active_player, False
        if key == KEY_UP and self.selected_index > 0:
            self.selected_index -= 1
        elif key == KEY_DOWN and self.selected_index < len(self.players) - 1:
            self.selected_index += 1
        elif key == KEY_ENTER and self.players:
            self.active_player = self.players[self.selected_index]
            try:
                self.player_status = self.active_player.get_status()
                return True, self.active_player, False
            except requests.RequestException as e:
                logger.error(f"Error connecting to the player: {e}")
                self.active_player = None
                self.player_status = None
                return False, None, False
        elif key == KEY_QUESTION:
            self.selector_shortcuts_open = not self.selector_shortcuts_open
        return False, self.active_player, False

    def handle_player_control(self, key: int, title_win: curses.window, stdscr: curses.window) -> Tuple[bool, bool]:
        if key == KEY_B:
            return False, False
        elif key == KEY_UP and self.active_player:
            self.update_header(title_win, "Increasing volume...", "Player Control")
            new_volume = min(100, self.player_status.volume + 5) if self.player_status else 5
            success, message = self.active_player.set_volume(new_volume)
            if success:
                self.update_player_status()
                self.display_player_control(stdscr)
            self.update_header(title_win, message, "Player Control")
        elif key == KEY_DOWN and self.active_player:
            self.update_header(title_win, "Decreasing volume...", "Player Control")
            new_volume = max(0, self.player_status.volume - 5) if self.player_status else 0
            success, message = self.active_player.set_volume(new_volume)
            if success:
                self.update_player_status()
                self.display_player_control(stdscr)
            self.update_header(title_win, message, "Player Control")
        elif (key == KEY_P or key == KEY_SPACE) and self.active_player:
            self.update_header(title_win, "Toggling play/pause...", "Player Control")
            if self.player_status and self.player_status.state == "play":
                success, message = self.active_player.pause()
            else:
                success, message = self.active_player.play()
            if success:
                self.update_player_status()
            self.update_header(title_win, message, "Player Control")
        elif key == KEY_RIGHT and self.active_player:
            self.update_header(title_win, "Skipping to next track...", "Player Control")
            success, message = self.active_player.skip()
            if success:
                self.update_player_status()
            self.update_header(title_win, message, "Player Control")
        elif key == KEY_LEFT and self.active_player:
            self.update_header(title_win, "Going to previous track...", "Player Control")
            success, message = self.active_player.back()
            if success:
                self.update_player_status()
            self.update_header(title_win, message, "Player Control")
        elif key == KEY_I:
            self.input_selection_mode = True
            self.selected_input_index = 0
        elif key == KEY_QUESTION:
            self.shortcuts_open = not self.shortcuts_open
        elif key == KEY_D:
            self.detail_view = not self.detail_view
            self.update_header(title_win, f"{'Detailed' if self.detail_view else 'Summary'} view", "Player Control")
        return True, False

    def handle_input_selection(self, key: int, title_win: curses.window) -> Tuple[bool, int]:
        if key == KEY_B:
            return False, self.selected_input_index
        elif key == KEY_UP and self.selected_input_index > 0:
            self.selected_input_index -= 1
        elif key == KEY_DOWN and self.selected_input_index < len(self.active_player.inputs) - 1:
            self.selected_input_index += 1
        elif key == KEY_ENTER:
            selected_input = self.active_player.inputs[self.selected_input_index]
            self.update_header(title_win, f"Selecting input: {selected_input.text}", "Input Selection")
            success, message = self.active_player.select_input(selected_input)
            if success:
                self.update_player_status()
                return False, self.selected_input_index
            self.update_header(title_win, message, "Input Selection")
        return True, self.selected_input_index

    def main(self, stdscr: curses.window):
        stdscr.clear()
        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)

        height, width = stdscr.getmaxyx()
        title_win: curses.window = curses.newwin(3, width, 0, 0)
        title_win.bkgd(' ', curses.color_pair(1))

        self.players = threaded_discover()
        stdscr.addstr(5, 2, "Discovering Blusound players...")
        stdscr.refresh()

        player_mode: bool = False

        while True:
            stdscr.clear()
            stdscr.refresh()
            if not player_mode:
                self.update_header(title_win, "", "Player Selection")
                self.display_player_selection(stdscr)
            else:
                if not self.input_selection_mode:
                    self.update_header(title_win, "", "Player Control", self.active_player)
                    self.display_player_control(stdscr)
                else:
                    self.update_header(title_win, "", "Input Selection", self.active_player)
                    self.display_input_selection(stdscr)

            stdscr.timeout(100)
            key = stdscr.getch()

            if key == ord('q'):
                break
            elif not player_mode:
                if self.selector_shortcuts_open:
                    if key != -1:
                        self.selector_shortcuts_open = False
                else:
                    player_mode, self.active_player, _ = self.handle_player_selection(key)
            else:
                if self.shortcuts_open:
                    if key != -1:
                        self.shortcuts_open = False
                elif not self.input_selection_mode:
                    player_mode, _ = self.handle_player_control(key, title_win, stdscr)
                else:
                    self.input_selection_mode, _ = self.handle_input_selection(key, title_win)

            current_time = time.time()
            if self.active_player and current_time - self.last_update_time >= 10:
                self.update_player_status()
                self.last_update_time = current_time

            self.update_header(title_win, "", "Player Selection" if not player_mode else "Player Control")

if __name__ == "__main__":
    cli = BlusoundCLI()
    curses.wrapper(cli.main)
