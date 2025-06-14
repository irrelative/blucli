import curses
import time
import requests
from typing import List, Optional, Tuple
from player import BlusoundPlayer, PlayerStatus, PlayerSource, threaded_discover
import logging
from logging.handlers import RotatingFileHandler
import json
from config import get_preference, set_preference
import curses.textpad
import signal
import sys

# Set up logging
log_file = 'logs/cli.log'
log_handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=1)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
log_handler.setFormatter(log_formatter)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

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
KEY_RIGHT = curses.KEY_RIGHT
KEY_LEFT = curses.KEY_LEFT
KEY_S = ord('s')

def create_volume_bar(volume, width=20):
    filled = int(volume / 100 * width)
    return f"[{'#' * filled}{'-' * (width - filled)}]"

class BlusoundCLI:
    def __init__(self):
        self.header_message: str = ""
        self.header_message_time: float = 0
        self.shortcuts_open: bool = False
        self.selector_shortcuts_open: bool = False
        self.source_selection_mode: bool = False
        self.selected_source_index: List[int] = []
        self.player_status: Optional[PlayerStatus] = None
        self.detail_view: bool = False
        self.selected_index: int = 0
        self.active_player: Optional[BlusoundPlayer] = None
        self.players: List[BlusoundPlayer] = []
        self.last_update_time: float = 0.0
        self.current_sources: List[PlayerSource] = []
        self.search_mode: bool = False
        self.search_results: List[PlayerSource] = []
        self.search_selected_index: int = 0

    def update_header(self, title_win: curses.window, message: str, view: str, active_player: Optional[BlusoundPlayer] = None):
        title_win.erase()
        header = f"Blusound CLI - {view}"
        if active_player:
            header += f" - {active_player.name}"
        title_win.addstr(1, 2, header, curses.A_BOLD)
        if message:
            self.header_message = message
            self.header_message_time = time.time()
        if time.time() - self.header_message_time < 2:
            max_width = title_win.getmaxyx()[1] - len(header) - 7
            truncated_message = self.header_message[:max_width] if len(self.header_message) > max_width else self.header_message
            try:
                title_win.addstr(1, len(header) + 4, f"- {truncated_message}")
            except curses.error:
                pass  # Ignore if still doesn't fit
        title_win.refresh()

    def update_player_status(self):
        if self.active_player:
            try:
                success, status = self.active_player.get_status()
                if success:
                    self.player_status = status
                else:
                    logger.error(f"Error updating player status: {status}")
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
            stdscr.addstr(stdscr.getmaxyx()[0] - 2, 2, "Press '?' for shortcuts, 'd' for detail view")
            stdscr.addstr(stdscr.getmaxyx()[0] - 1, 2, "Press 's' to select streaming sources")

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

        active_source = next((source for source in active_player.sources if source.input_type == player_status.inputId), None)
        if active_source:
            stdscr.addstr(10, 2, f"{'Active Input:':<{max_label_width + 1}} {active_source.text} ({active_source.input_type})")
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
            ("SPACE", "Play/Pause"),
            (">/<", "Skip/Previous track"),
            ("i", "Select input"),
            ("p", "Pretty print player state"),
            ("b", "Back to player list"),
            ("q", "Quit application"),
        ]

        for i, (key, description) in enumerate(shortcuts):
            modal_win.addstr(3 + i, 2, f"{key:<10} : {description}")

        modal_win.addstr(modal_height - 2, 2, "Press any key to close", curses.A_ITALIC)
        modal_win.refresh()

    def display_source_selection(self, stdscr: curses.window):
        active_player = self.active_player
        height, width = stdscr.getmaxyx()
        max_display_items = height - 12  # Reserve space for header and instructions

        stdscr.addstr(5, 2, "UP/DOWN: select source, ENTER: expand/select, LEFT: go back, RIGHT: expand")
        stdscr.addstr(6, 2, "n: next page, p: previous page, b: back to player control")
        stdscr.addstr(8, 2, "Select Source:")
        
        # Ensure current_sources is populated if it's the initial entry to source selection
        if not self.current_sources and self.active_player:
            self.current_sources = self.active_player.sources

        # Ensure selected_source_index is initialized
        if not self.selected_source_index:
            self.selected_source_index = [0]

        if not self.current_sources: # If still no sources (e.g. player has none)
            stdscr.addstr(9, 4, "No sources available.")
            stdscr.refresh()
            return

        # At this point, self.current_sources is not empty.
        # Ensure selected_source_index[-1] is valid for current_sources
        # Clamp to the last valid index if out of bounds high
        if self.selected_source_index[-1] >= len(self.current_sources):
            self.selected_source_index[-1] = max(0, len(self.current_sources) - 1)
        # Clamp to 0 if out of bounds low (shouldn't happen with current logic but defensive)
        if self.selected_source_index[-1] < 0:
             self.selected_source_index[-1] = 0
        
        total_items = len(self.current_sources) # Should be > 0 here if we reached this point

        current_page = max(0, self.selected_source_index[-1] // max_display_items)
        start_index = max(0, current_page * max_display_items)
        end_index = min(start_index + max_display_items, total_items)

        for i in range(start_index, end_index):
            source = self.current_sources[i]
            indent = "  " * (len(self.selected_source_index) - 1) # Current depth for indentation
            prefix = ">" if i == self.selected_source_index[-1] else " "
            expand_indicator = "+" if source.browse_key else " "
            display_index = i - start_index # Relative to the start of the window
            stdscr.addstr(9 + display_index, 4, f"{indent}{prefix} {expand_indicator} {source.text}")

        if total_items > max_display_items:
            page_info = f"Page {current_page + 1}/{(total_items + max_display_items - 1) // max_display_items}"
            stdscr.addstr(height - 2, width - len(page_info) - 2, page_info)

        # Remove the automatic fetching of nested sources

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
                success, status = self.active_player.get_status()
                if success:
                    self.player_status = status
                    set_preference('last_player', self.active_player.name)
                    return True, self.active_player, False
                else:
                    logger.error(f"Error getting player status: {status}")
                    self.active_player = None
                    self.player_status = None
                    return False, None, False
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
        elif key == KEY_SPACE and self.active_player:
            self.update_header(title_win, "Toggling play/pause...", "Player Control")
            success, message = self.active_player.toggle_play_pause()
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
            self.source_selection_mode = True
            self.selected_source_index = [0]
            self.current_sources = self.active_player.sources
        elif key == KEY_S:
            self.search_mode = True
            self.search_results = []
            self.search_selected_index = 0
        elif key == KEY_QUESTION:
            self.shortcuts_open = not self.shortcuts_open
        elif key == KEY_D:
            self.detail_view = not self.detail_view
            self.update_header(title_win, f"{'Detailed' if self.detail_view else 'Summary'} view", "Player Control")
        elif key == KEY_P:
            self.pretty_print_player_state(stdscr)
        return True, False

    def pretty_print_player_state(self, stdscr: curses.window):
        if self.active_player and self.player_status:
            def serialize_source(source):
                return {
                    "text": source.text,
                    "image": source.image,
                    "browse_key": source.browse_key,
                    "play_url": source.play_url,
                    "input_type": source.input_type,
                    "type": source.type,
                    "children": [serialize_source(child) for child in source.children]
                }

            player_state = {
                "player": {
                    "name": self.active_player.name,
                    "host_name": self.active_player.host_name,
                    "base_url": self.active_player.base_url,
                    "sources": [serialize_source(source) for source in self.active_player.sources]
                },
                "status": self.player_status.__dict__
            }
            pretty_state = json.dumps(player_state, indent=2)
            
            # Log the pretty print data
            logger.info(f"Pretty print data:\n{pretty_state}")

            # Display in a new scrollable window
            height, width = stdscr.getmaxyx()
            lines = pretty_state.splitlines()
            
            content_height = len(lines)
            content_width = 0
            if lines:
                content_width = max(len(line) for line in lines)
            content_width = min(content_width, width - 6) # Max content width for pad

            popup_content_h = min(content_height, height - 6)
            popup_content_w = content_width
            
            popup_height = popup_content_h + 2 # For border
            popup_width = popup_content_w + 2   # For border
            
            popup_start_y = (height - popup_height) // 2
            popup_start_x = (width - popup_width) // 2
            
            popup_win = curses.newwin(popup_height, popup_width, popup_start_y, popup_start_x)
            popup_win.box()
            popup_win.addstr(0, 2, " Player State (UP/DOWN scroll, 'q' to close) ", curses.A_REVERSE)

            content_pad = curses.newpad(content_height + 1, content_width + 1) # Pad for actual content
            for i, line_text in enumerate(lines):
                try:
                    content_pad.addstr(i, 0, line_text[:content_width])
                except curses.error:
                    pass 
            
            pad_pos = 0 # Current top line of the pad to display
            popup_win.refresh()

            while True:
                sminrow = popup_start_y + 1 # Screen y for top of pad viewport
                smincol = popup_start_x + 1 # Screen x for left of pad viewport
                smaxrow = popup_start_y + popup_height - 2 # Screen y for bottom of pad viewport
                smaxcol = popup_start_x + popup_width - 2  # Screen x for right of pad viewport
                
                content_pad.refresh(pad_pos, 0, sminrow, smincol, smaxrow, smaxcol)
                
                key_press = stdscr.getch() # Use stdscr.getch() as main loop does
                
                if key_press == ord('q'):
                    break
                elif key_press == curses.KEY_DOWN:
                    if pad_pos < content_height - popup_content_h: # Check scroll bounds
                         pad_pos += 1
                elif key_press == curses.KEY_UP:
                    if pad_pos > 0:
                        pad_pos -= 1
            
            stdscr.touchwin() # Mark window as changed
            stdscr.refresh()   # Refresh underlying screen

    def handle_source_selection(self, key: int, title_win: curses.window) -> Tuple[bool, List[int]]:
        height, _ = title_win.getmaxyx()
        max_display_items = height - 12 # Used for page navigation logic
        logger.info("Key pressed in source selection: %s", key)

        if key == KEY_B: # Back to player control
            self.source_selection_mode = False
            self.current_sources = [] # Reset for next entry
            self.selected_source_index = [0] # Reset for next entry
            return False, self.selected_source_index

        # Ensure selected_source_index is initialized (should be by display logic, but defensive)
        if not self.selected_source_index:
            self.selected_source_index = [0]

        if key == KEY_LEFT: # Navigate up the source hierarchy
            if len(self.selected_source_index) > 1: # Can only go left if not at root level
                self.selected_source_index.pop()
                # Reconstruct current_sources based on the new (parent) path
                path_sources = self.active_player.sources
                for i in range(len(self.selected_source_index) - 1): # Iterate to parent of new current level
                    idx = self.selected_source_index[i]
                    if idx < len(path_sources) and hasattr(path_sources[idx], 'children'):
                        path_sources = path_sources[idx].children
                    else: # Path broken or item has no children
                        path_sources = [] 
                        break
                self.current_sources = path_sources
                
                # Ensure last index is valid for newly populated current_sources
                if self.current_sources and self.selected_source_index[-1] >= len(self.current_sources):
                    self.selected_source_index[-1] = max(0, len(self.current_sources) - 1)
                elif not self.current_sources: # Navigated to an empty list
                    self.selected_source_index[-1] = 0 
            else: # At root level, pressing left exits source selection mode
                self.source_selection_mode = False
                self.current_sources = []
                self.selected_source_index = [0]
                return False, self.selected_source_index
            return True, self.selected_source_index # Stay in source selection mode

        # Handle other keys only if there are current_sources to interact with
        if not self.current_sources:
            self.update_header(title_win, "No sources available to navigate.", "Source Selection")
            return True, self.selected_source_index # Stay in mode, but do nothing else

        # At this point, self.current_sources is NOT empty.
        # Ensure current index is valid before use for other operations
        current_idx_val = self.selected_source_index[-1]
        if current_idx_val >= len(self.current_sources):
            self.selected_source_index[-1] = len(self.current_sources) - 1
        if current_idx_val < 0: self.selected_source_index[-1] = 0 # Should not happen

        # Handle UP, DOWN, page navigation (n, p), RIGHT (expand), ENTER (select/play)
        if key == KEY_UP:
            if self.selected_source_index[-1] > 0:
                self.selected_source_index[-1] -= 1
        elif key == KEY_DOWN:
            if self.selected_source_index[-1] < len(self.current_sources) - 1:
                self.selected_source_index[-1] += 1
        elif key == ord('n'):  # Next page
            current_page_items = max_display_items if max_display_items > 0 else len(self.current_sources) # Avoid division by zero
            next_page_start_index = ((self.selected_source_index[-1] // current_page_items) + 1) * current_page_items
            if next_page_start_index < len(self.current_sources):
                self.selected_source_index[-1] = next_page_start_index
            else: # If trying to go past last page, go to last item
                self.selected_source_index[-1] = len(self.current_sources) -1
        elif key == ord('p'):  # Previous page
            current_page_items = max_display_items if max_display_items > 0 else len(self.current_sources)
            prev_page_start_index = ((self.selected_source_index[-1] // current_page_items) - 1) * current_page_items
            if prev_page_start_index >= 0:
                self.selected_source_index[-1] = prev_page_start_index
            else: # If trying to go before first page, go to first item
                self.selected_source_index[-1] = 0
        elif key == KEY_RIGHT or key == KEY_ENTER: # Expand or Play/Select
            selected_source = self.current_sources[self.selected_source_index[-1]]
            if selected_source.browse_key: # If it's expandable
                self.active_player.get_nested_sources(selected_source) # Fetch children
                if selected_source.children:
                    self.current_sources = selected_source.children
                    self.selected_source_index.append(0)
                else:
                    self.update_header(title_win, f"No nested sources found for: {selected_source.text}", "Source Selection")
            elif selected_source.play_url:
                self.update_header(title_win, f"Selecting source: {selected_source.text}", "Source Selection")
                success, message = self.active_player.select_input(selected_source)
                if success:
                    self.update_player_status()
                    return False, self.selected_source_index
                self.update_header(title_win, message, "Source Selection")
            else:
                self.update_header(title_win, f"Cannot expand or play: {selected_source.text}", "Source Selection")
        return True, self.selected_source_index

    def main(self, stdscr: curses.window):
        stdscr.erase()
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

        # Try to select the last player
        last_player_name = get_preference('last_player')
        if last_player_name:
            for i, player in enumerate(self.players):
                if player.name == last_player_name:
                    self.selected_index = i
                    player_mode, self.active_player, _ = self.handle_player_selection(KEY_ENTER)
                    break

        while True:
            stdscr.erase()
            stdscr.refresh()
            if not player_mode:
                self.update_header(title_win, "", "Player Selection")
                self.display_player_selection(stdscr)
            else:
                if not self.source_selection_mode:
                    self.update_header(title_win, "", "Player Control", self.active_player)
                    self.display_player_control(stdscr)
                else:
                    self.update_header(title_win, "", "Source Selection", self.active_player)
                    self.display_source_selection(stdscr)

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
                    if player_mode:
                        self.update_player_status()
            else:
                if self.shortcuts_open:
                    if key != -1:
                        self.shortcuts_open = False
                elif self.search_mode:
                    self.search_mode = self.handle_search(key, title_win, stdscr)
                elif not self.source_selection_mode:
                    player_mode, _ = self.handle_player_control(key, title_win, stdscr)
                else:
                    self.source_selection_mode, _ = self.handle_source_selection(key, title_win)

            current_time = time.time()
            if self.active_player and current_time - self.last_update_time >= 10:
                self.update_player_status()
                self.last_update_time = current_time

            self.update_header(title_win, "", "Player Selection" if not player_mode else "Player Control")

    def get_input(self, stdscr, prompt):
        curses.noecho()  # Disable automatic echoing
        stdscr.addstr(prompt)
        stdscr.refresh()
        input_str = ""
        
        while True:
            try:
                ch = stdscr.getch()
                
                if ch == 10:  # Enter key
                    break
                elif ch == 127 or ch == 8:  # Backspace
                    if input_str:
                        input_str = input_str[:-1]
                        y, x = stdscr.getyx()
                        stdscr.addstr(y, x-1, " ")  # Clear the last character
                        stdscr.move(y, x-1)
                elif ch >= 32 and ch <= 126:  # Printable ASCII range
                    input_str += chr(ch)
                    stdscr.addch(ch)  # Manually echo the character
                stdscr.refresh()
            except ValueError:
                # Ignore invalid characters
                pass

        return input_str.strip()

    def handle_search(self, key: int, title_win: curses.window, stdscr: curses.window) -> bool:
        if not self.search_results:
            self.update_header(title_win, "Enter search term:", "Search")
            stdscr.move(5, 2)  # Move cursor to appropriate position
            search_term = self.get_input(stdscr, "Search: ")
            
            if search_term:
                self.update_header(title_win, f"Searching for: {search_term}", "Search")
                stdscr.refresh()
                if self.active_player and self.active_player.sources:
                    search_key_to_use = self.active_player.sources[0].search_key
                    if search_key_to_use:
                        self.search_results = self.active_player.search(search_key_to_use, search_term)
                        self.search_selected_index = 0
                        if not self.search_results:
                             self.update_header(title_win, f"No results for: {search_term}", "Search")
                        # Proceed to display results (even if empty)
                    else:
                        self.update_header(title_win, "Search not available (no search key for current sources).", "Search")
                        self.search_results = [] # Clear previous results
                        return False # Exit search mode
                else:
                    self.update_header(title_win, "No active player or sources available for search.", "Search")
                    return False
            else:
                self.update_header(title_win, "Search cancelled", "Search")
                return False
        else:
            if key == KEY_UP and self.search_selected_index > 0:
                self.search_selected_index -= 1
            elif key == KEY_DOWN and self.search_selected_index < len(self.search_results) - 1:
                self.search_selected_index += 1
            elif key == KEY_ENTER:
                selected_source = self.search_results[self.search_selected_index]
                success, message = self.active_player.select_input(selected_source)
                self.update_header(title_win, message, "Search")
                if success:
                    self.update_player_status()
                    return False
            elif key == KEY_B:
                return False

        self.display_search_results(stdscr)
        return True

    def display_search_results(self, stdscr: curses.window):
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        max_display_items = height - 8

        stdscr.addstr(5, 2, "Search Results:")
        for i, source in enumerate(self.search_results[:max_display_items]):
            if i == self.search_selected_index:
                stdscr.attron(curses.color_pair(2))
            stdscr.addstr(7 + i, 4, f"{source.text}")
            if i == self.search_selected_index:
                stdscr.attroff(curses.color_pair(2))

        stdscr.addstr(height - 2, 2, "UP/DOWN: navigate, ENTER: select, b: back")
        stdscr.refresh()

def signal_handler(sig, frame):
    curses.endwin()
    sys.exit(0)

if __name__ == "__main__":
    cli = BlusoundCLI()
    signal.signal(signal.SIGINT, signal_handler)
    try:
        curses.wrapper(cli.main)
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        import pdb; pdb.post_mortem()
        raise e
