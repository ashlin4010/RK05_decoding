# SPDX-License-Identifier: GPL-2.0-or-later

from collections import deque

import sigrokdecode as srd


class Decoder(srd.Decoder):
    api_version = 3
    id = 'falling_edge'
    name = 'Falling Edge'
    longname = 'Falling-edge clocked data sampler'
    desc = 'Samples DATA after each falling CLK edge.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Util']
    channels = (
        {'id': 'clk', 'name': 'CLK', 'desc': 'Clock input'},
        {'id': 'data', 'name': 'DATA', 'desc': 'Data input'},
    )
    options = (
        {'id': 'delay_ns', 'desc': 'Delay after falling edge (ns)', 'default': 0},
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
        delay_ns = self.options['delay_ns']
        if delay_ns < 0:
            raise ValueError('Delay must be zero or greater.')

        delay_samples = 0
        if delay_ns:
            if not self.samplerate:
                raise ValueError('A capture sample rate is required for a nonzero delay.')
            ns_per_second = 1_000_000_000
            delay_samples = (delay_ns * self.samplerate + ns_per_second - 1) // ns_per_second

        pending = deque()
        self.wait()  # Establish the initial CLK level from the capture.
        while True:
            conditions = [{0: 'f'}]
            if pending:
                # Keep looking for falling edges while waiting for a scheduled sample.
                conditions.append({'skip': pending[0] - self.samplenum})

            _, data = self.wait(conditions)
            sample = self.samplenum
            if self.matched[0]:
                pending.append(sample + delay_samples)

            if pending and pending[0] == sample:
                pending.popleft()
                self.put(sample, sample, self.out_ann, [0, [str(data)]])
