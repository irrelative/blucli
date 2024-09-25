# Blusound CLI

A CLI interface to Blusound streamers.

## Features

* Discover Blusound players on the network
* Display list of discovered players
* Volume up/down
* Pause/play
* Skip/back tracks
* Display currently playing information

## Requirements

* Python 3.6+
* zeroconf library
* requests library

## Installation

1. Clone this repository
2. Install the required dependencies:

   ```
   pip install zeroconf requests
   ```

## Usage

Run the script using:

```
python cli.py
```

## Controls

* Use UP/DOWN arrows to select a player
* ENTER to activate a player
* 'p' to play/pause
* '+' to increase volume
* '-' to decrease volume
* '>' to skip to the next track
* '<' to go back to the previous track
* 'q' to quit the application
