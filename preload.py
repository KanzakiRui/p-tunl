import os
import sys

# Add --tunnel argument to sys.argv before webui parses arguments
if '--tunnel' in sys.argv:
    sys.argv.append('--pinggy-tunnel')  # Our custom flag
    sys.argv.remove('--tunnel')