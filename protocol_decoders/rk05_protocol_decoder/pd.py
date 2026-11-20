# SPDX-License-Identifier: GPL-2.0-or-later

from collections import deque
from math import ceil
from struct import pack

import sigrokdecode as srd

HEADER_BITS = 16
WORD_BITS = 12
WORD_COUNT = 256
CRC_BITS = 16
DATA_END = HEADER_BITS + WORD_BITS * WORD_COUNT
SECTOR_END = DATA_END + CRC_BITS
NS_PER_SECOND = 10 ** 9

READ_CLK, READ_DATA, WRITE, READ_GATE, WRITE_GATE = range(5)

READ_SECTOR, WRITE_SECTOR, HEADER, PAYLOAD_ADDRESS, WORD, CRC, WARNING = range(7)


def track_text(cylinder):
    return 'Track/Cyl={}'.format('?' if cylinder is None else cylinder)


def wire_bytes(value):
    # Match the reference script: reverse the bits of each received byte,
    # then display the low byte before the high byte.
    return '{:08b}{:08b}'.format(value & 0xFF, value >> 8)


class Sector:
    def __init__(self, decoder, reading):
        self.decoder = decoder
        self.reading = reading
        self.name = 'Read' if reading else 'Write'
        self.reset()

    def reset(self):
        self.start = None
        self.end = None
        self.zeros = 0
        self.synced = False
        self.bits = 0
        self.field_bits = 0
        self.value = 0
        self.cylinder = None
        self.data_start = None
        self.data_end = None
        self.words = []
        self.diagnostic_address = None

    def finish(self, timing_error=False):
        header_only = self.reading and self.bits == HEADER_BITS
        if self.synced and not header_only:
            label = '{} incomplete ({}/{} bits after sync)'.format(
                self.name, self.bits, SECTOR_END)
            if timing_error:
                label += ' (write pulse timing)'
            self.decoder.annotate(self.start, self.end, WARNING, label, 'Incomplete')
        self.reset()

    def bit(self, start, end, bit):
        if not self.synced:
            if not bit:
                if not self.zeros:
                    self.start = start
                self.zeros += 1
            elif self.zeros >= self.decoder.options['preamble_zeros']:
                if not self.zeros:
                    self.start = start
                self.synced = True
                self.end = end
            else:
                self.reset()
            return

        if not self.field_bits:
            self.field_start = start
        self.end = end
        self.value |= bit << self.field_bits
        self.field_bits += 1
        self.bits += 1
        if self.bits <= HEADER_BITS:
            width = HEADER_BITS
        else:
            width = WORD_BITS if self.bits <= DATA_END else CRC_BITS
        if self.field_bits != width:
            return

        value = self.value
        self.field_bits = self.value = 0
        if self.bits == HEADER_BITS:
            self.header(value)
        elif self.bits <= DATA_END:
            self.word(value)
        else:
            self.complete(value)

    def header(self, value):
        cylinder = (value >> 5) & 0xFF
        self.cylinder = cylinder if not value & 0xE01F else None
        address = track_text(self.cylinder)
        label = '{} header {} | {} | {} preamble zeros'.format(
            self.name, wire_bytes(value), address, self.zeros)
        self.decoder.annotate(self.field_start, self.end, HEADER, label, address)
        if self.cylinder is None:
            message = 'Nonzero header padding (cylinder bits decode to {})'.format(cylinder)
            self.decoder.annotate(self.field_start, self.end, WARNING, message, 'Header padding')

    def word(self, value):
        if not self.words:
            self.data_start = self.field_start
        self.words.append(value)
        self.data_end = self.end
        self.decoder.annotate(self.field_start, self.end, WORD, '{:04o}'.format(value))
        if len(self.words) != 2 or self.decoder.options['diagnostic_address'] != 'yes':
            return

        high, low = self.words
        cylinder = ((high & 1) << 7) | ((low >> 5) & 0x7F)
        head = (low >> 4) & 1
        sector = low & 0x0F
        address = '{} H={} S={}'.format(track_text(cylinder), head, sector)
        self.diagnostic_address = address
        label = 'Diagnostic address {} ({:04o} {:04o})'.format(address, high, low)
        self.decoder.annotate(self.data_start, self.end, PAYLOAD_ADDRESS, label, address)
        if self.cylinder is not None and self.cylinder != cylinder:
            message = 'Diagnostic cylinder {} differs from header cylinder {}'.format(
                cylinder, self.cylinder)
            self.decoder.annotate(self.data_start, self.end, WARNING, message, 'Address mismatch')

    def complete(self, crc):
        self.decoder.annotate(self.field_start, self.end, CRC, 'CRC ' + wire_bytes(crc), 'CRC')
        address = self.diagnostic_address
        if address is None:
            address = track_text(self.cylinder)
        label = '{} {} words | {}'.format(self.name, len(self.words), address)
        short_label = '{} {}'.format(self.name, address)
        operation = READ_SECTOR if self.reading else WRITE_SECTOR
        self.decoder.annotate(self.start, self.end, operation, label, short_label, self.name)
        binary_class = 0 if self.reading else 1
        self.decoder.put(self.data_start, self.data_end, self.decoder.out_binary,
                         [binary_class, pack('<{}H'.format(WORD_COUNT), *self.words)])
        self.reset()


class Decoder(srd.Decoder):
    api_version = 3
    id = 'rk05'
    name = 'RK05 (RK8-E)'
    longname = 'RK05 disk interface for the PDP-8 RK8-E'
    desc = 'Decodes read and write sectors, addresses, data words, and CRCs.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Retro computing']
    channels = ()
    optional_channels = (
        {'id': 'read_clk', 'name': 'READ CLK', 'desc': 'Read clock, active low'},
        {'id': 'read_data', 'name': 'READ DATA', 'desc': 'Read data, active low'},
        {'id': 'write', 'name': 'WRITE', 'desc': 'Combined write clock and data, active low'},
        {'id': 'read_gate', 'name': 'READ GATE', 'desc': 'Read enable, active low'},
        {'id': 'write_gate', 'name': 'WRITE GATE', 'desc': 'Write enable, active low'},
    )
    options = (
        {'id': 'delay_ns', 'desc': 'Read sample delay (ns)', 'default': 440},
        {'id': 'clock_period_ns', 'desc': 'Write clock period (ns)', 'default': 690},
        {'id': 'preamble_zeros', 'desc': 'Minimum preamble zeros', 'default': 8},
        {'id': 'diagnostic_address', 'desc': 'Diagnostic address in data words 0 and 1',
         'default': 'yes', 'values': ('yes', 'no')},
    )
    annotations = (
        ('read', 'Read sector'), ('write', 'Write sector'),
        ('header', 'Disk header'), ('diagnostic-address', 'Diagnostic address'),
        ('word', 'Data word (octal)'), ('crc', 'Recorded CRC'), ('warning', 'Warning'),
    )
    annotation_rows = (
        ('operations', 'Operations', (READ_SECTOR, WRITE_SECTOR)),
        ('headers', 'Disk headers', (HEADER,)),
        ('addresses', 'Diagnostic address', (PAYLOAD_ADDRESS,)),
        ('words', 'Data words', (WORD,)),
        ('checksums', 'CRC', (CRC,)),
        ('warnings', 'Warnings', (WARNING,)),
    )
    binary = (
        ('read', 'Read sectors (16-bit little-endian words)'),
        ('write', 'Write sectors (16-bit little-endian words)'),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def annotate(self, start, end, annotation, *labels):
        self.put(start, end, self.out_ann, [annotation, list(labels)])

    def write_edge(self, edge):
        clock, previous = self.write_clock, self.write_previous
        self.write_previous = edge
        if previous is None:
            if self.write_boundary or edge - self.capture_start >= self.idle:
                self.write_clock = edge
            return

        gap = edge - previous
        if self.full_min <= gap <= self.full_max:
            if clock is not None and clock != previous:
                self.write_sector.finish(timing_error=True)
            self.write_sector.bit(previous, edge, 0)
            self.write_clock = edge
        elif self.half_min <= gap <= self.half_max:
            if clock is not None and clock != previous:
                if self.full_min <= edge - clock <= self.full_max:
                    self.write_sector.bit(clock, edge, 1)
                    self.write_clock = edge
                else:
                    self.write_sector.finish(timing_error=True)
                    self.write_clock = None
        else:
            self.write_sector.finish(timing_error=True)
            self.write_clock = None

    def end_write_burst(self):
        self.write_sector.finish()
        self.write_previous = self.write_clock = None
        self.write_boundary = True

    def decode(self):
        self.mapped = {ch for ch in range(len(self.optional_channels)) if self.has_channel(ch)}
        have_read = {READ_CLK, READ_DATA} <= self.mapped
        have_write = WRITE in self.mapped
        if not (have_read or have_write):
            raise ValueError('Assign READ CLK and READ DATA, or WRITE.')

        period_ns = self.options['clock_period_ns']
        delay_ns = self.options['delay_ns']
        if period_ns <= 0 or delay_ns < 0 or self.options['preamble_zeros'] < 0:
            raise ValueError('Clock period must be positive, and delay and preamble must be nonnegative.')
        if not self.samplerate:
            raise ValueError('A capture sample rate is required to decode read or write data.')

        rate = self.samplerate
        period = period_ns * rate / NS_PER_SECOND
        delay = (delay_ns * rate + NS_PER_SECOND - 1) // NS_PER_SECOND
        self.idle = ceil(3 * period)
        read_idle = max(self.idle, delay + 1)
        self.half_min, self.half_max = 0.30 * period, 0.70 * period
        self.full_min, self.full_max = 0.80 * period, 1.20 * period

        watches = []
        if have_read:
            watches.append(('read', {READ_CLK: 'f'}))
            if READ_GATE in self.mapped:
                watches.append(('read gate', {READ_GATE: 'e'}))
        if have_write:
            watches.append(('write', {WRITE: 'f'}))
            if WRITE_GATE in self.mapped:
                watches.append(('write gate', {WRITE_GATE: 'e'}))
        edges = [condition for _, condition in watches]

        read_sector = Sector(self, reading=True)
        self.write_sector = Sector(self, reading=False)
        pending = deque()
        last_read = None
        self.write_previous = self.write_clock = None
        self.write_boundary = False
        self.wait()
        self.capture_start = self.samplenum
        while True:
            read_end = None if last_read is None else last_read + read_idle
            write_end = None if self.write_previous is None else self.write_previous + self.idle
            next_read = pending[0][0] if pending else None
            deadline = min((point for point in (read_end, write_end, next_read)
                            if point is not None), default=None)
            conditions = edges if deadline is None else edges + [{'skip': deadline - self.samplenum}]
            # Unpack the pin levels because AllLogic reuses the tuple on the next wait.
            _, read_data, _, read_gate, write_gate = self.wait(conditions)
            sample = self.samplenum
            matched = self.matched
            if isinstance(matched, int):
                matched = tuple(matched & (1 << index) for index in range(len(watches)))
            events = {name for (name, _), active in zip(watches, matched) if active}

            # A releasing gate can coincide with the last clock. Let its
            # delayed sample complete before closing the read burst.
            read_open = READ_GATE not in self.mapped or read_gate == 0
            read_gate_edge = 'read gate' in events
            read_starting = read_gate_edge and read_open
            if read_starting:
                pending.clear()
            # A timeout may arrive a sample late across AllLogic capture chunks.
            while pending and pending[0][0] <= sample:
                _, clock = pending.popleft()
                read_sector.bit(clock, sample, 1 - read_data)
            if read_starting or (read_end is not None and sample >= read_end):
                read_sector.finish()
                last_read = None
            if 'read' in events and (read_open or read_gate_edge):
                if delay:
                    pending.append((sample + delay, sample))
                else:
                    read_sector.bit(sample, sample, 1 - read_data)
                last_read = sample
            if not read_open and not pending and last_read is not None:
                read_sector.finish()
                last_read = None

            write_open = WRITE_GATE not in self.mapped or write_gate == 0
            write_gate_edge = 'write gate' in events
            if (write_end is not None and sample >= write_end) or (write_gate_edge and write_open):
                self.end_write_burst()
            if 'write' in events and (write_open or write_gate_edge):
                self.write_edge(sample)
            if write_gate_edge and not write_open:
                self.end_write_burst()
