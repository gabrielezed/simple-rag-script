# modules/terminal_colors.py

class Colors:
    """
    A class to hold ANSI escape codes for terminal colors.
    These are supported by most modern terminals, including Linux,
    macOS, and Windows Terminal.
    """
    MAGENTA = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m' # Resets the color to the default