import curses
import time

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

    # Main loop
    while True:
        # Update the screen
        stdscr.refresh()

        # Display the title
        title_win.clear()
        title_win.addstr(1, 2, "Blusound CLI", curses.A_BOLD)
        title_win.refresh()

        # Display instructions
        stdscr.addstr(5, 2, "Press 'q' to quit")

        # Get user input
        key = stdscr.getch()

        if key == ord('q'):
            break

        # Small delay to reduce CPU usage
        time.sleep(0.1)

if __name__ == "__main__":
    curses.wrapper(main)
