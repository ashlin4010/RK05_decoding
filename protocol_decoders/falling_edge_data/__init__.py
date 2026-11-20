# SPDX-License-Identifier: GPL-2.0-or-later
"""Sample DATA a configurable number of nanoseconds after each falling CLK edge.

The decoder marks the first capture sample at or after the requested time.
"""

from .pd import Decoder
