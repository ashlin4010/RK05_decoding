# SPDX-License-Identifier: GPL-2.0-or-later

import sigrokdecode as srd


class Decoder(srd.Decoder):
    api_version = 3
    id = 'rk05_write_bits'
    name = 'RK05 Write Bits'
    longname = 'RK05 Write Data and Clock'
    desc = 'Extracts raw bits from the active-low RK05 write signal.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Clock/timing']
    channels = (
        {'id': 'write', 'name': 'WRITE', 'desc': 'Write Data and Clock (active low)'},
    )
    options = (
        {'id': 'clock_period_ns', 'desc': 'Clock period (ns)', 'default': 690},
    )
    annotations = (('bit', 'Bit'),)
    annotation_rows = (('bits', 'Bits', (0,)),)

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def decode(self):
        if not self.samplerate:
            raise ValueError('A capture sample rate is required.')
        period_ns = self.options['clock_period_ns']
        if period_ns <= 0:
            raise ValueError('Clock period must be greater than zero.')

        period = period_ns * self.samplerate / 1_000_000_000
        half_min, half_max = 0.30 * period, 0.70 * period
        full_min, full_max = 0.80 * period, 1.20 * period
        idle_gap = 3 * period
        falling = {0: 'f'}

        self.wait()
        capture_start = self.samplenum
        self.wait(falling)
        previous = self.samplenum
        clock = previous if previous - capture_start > idle_gap else None

        while True:
            self.wait(falling)
            edge = self.samplenum
            gap = edge - previous

            if full_min <= gap <= full_max:
                # A full-period gap identifies two clock pulses and a zero.
                self.put(previous, edge, self.out_ann, [0, ['0']])
                clock = edge
            elif half_min <= gap <= half_max:
                # Two half-period gaps after a known clock enclose a data pulse.
                if clock is not None and previous != clock:
                    if full_min <= edge - clock <= full_max:
                        self.put(clock, edge, self.out_ann, [0, ['1']])
                        clock = edge
                    else:
                        clock = None
            else:
                # The first pulse of a new write burst is a clock pulse.
                clock = edge if gap > idle_gap else None

            previous = edge
