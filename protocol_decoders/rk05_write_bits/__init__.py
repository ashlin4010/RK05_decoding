# SPDX-License-Identifier: GPL-2.0-or-later
"""Decode raw bits from the active-low RK05 WRITE DATA AND CLOCK line.

Include the start of the write burst so the decoder can identify the clock phase.
"""

from .pd import Decoder
