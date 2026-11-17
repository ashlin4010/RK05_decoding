import sys
import struct
import datetime
import argparse
import os
from dataclasses import dataclass

# input_file = "analysis\\card_2\\Error.rke"
input_file = "images/FORMATTED_1.rke"


FIRST_SECTOR_OFFSET = 0x16d
SECTOR_HEADER_BIT_TIMES_LEN = 2
SECTOR_HEADER_BIT_COUNT_LEN = 2
SECTOR_HEADER_LEN = SECTOR_HEADER_BIT_TIMES_LEN + SECTOR_HEADER_BIT_COUNT_LEN

MINIMUM_DATA_SIZE_BITS = (12 * 256) + 16 + 16
RK_HEADER_LEN = 2 # 16 bit cylinder address
RK_CRC_LEN = 2

#
#   Various lengths in the header
#
hdrMagicLen = 10
hdrVersionLen = 4
hdrImageNameLen = 11
hdrDescLen = 200
hdrDateLen = 20
hdrControllerLen = 100
magicNumber = b"\x89RK05\r\n\x1A\x00\x00"
versionNumber = b"1.1\x00"

@dataclass
class Header:
    valid_magic: bool
    version: str
    image_name: str
    description: str
    date: str
    controller: str
    bit_rate: int
    number_of_cylinders: int
    number_of_sectors_total: int
    number_sectors_per_track: int
    number_of_heads: int
    microseconds_per_sector: int

@dataclass
class SectorBlock:
    sector: int
    surface: int
    cylinder: int
    offset_into_file: int
    bit_times_sector_to_start_bit: int
    data_bits_after_start_bit: int
    data_block_count: int


def read_rke_header(fileName):
    header_raw = {}
    with open(fileName, "rb") as f:
        magic = f.read(hdrMagicLen)
        header_raw["magicValid"] = False
        header_raw["version"] = f.read(hdrVersionLen)
        header_raw["imageName"] = f.read(hdrImageNameLen)
        header_raw["description"] = f.read(hdrDescLen)
        header_raw["date"] = f.read(hdrDateLen)
        header_raw["controller"] = f.read(hdrControllerLen)

        header_raw["bitRate"] = f.read(4)
        header_raw["numberOfCylinders"] = f.read(4)
        header_raw["numberSectorsPerTrack"] = f.read(4)
        header_raw["numberOfHeads"] = f.read(4)
        header_raw["microsecondsPerSector"] = f.read(4)

    header = Header(
        valid_magic=magic == magicNumber,
        version=header_raw["version"].decode("ascii"),
        image_name=header_raw["imageName"].decode("ascii"),
        description=header_raw["description"].decode("ascii"),
        date=header_raw["date"].decode("ascii"),
        controller=header_raw["controller"].decode("ascii"),
        bit_rate=struct.unpack(">I", header_raw["bitRate"])[0],
        number_of_cylinders=struct.unpack(">I", header_raw["numberOfCylinders"])[0],
        number_of_sectors_total=struct.unpack(">I", header_raw["numberSectorsPerTrack"])[0] * struct.unpack(">I", header_raw["numberOfHeads"])[0] * struct.unpack(">I", header_raw["numberOfCylinders"])[0],
        number_sectors_per_track=struct.unpack(">I", header_raw["numberSectorsPerTrack"])[0],
        number_of_heads=struct.unpack(">I", header_raw["numberOfHeads"])[0],
        microseconds_per_sector=struct.unpack(">I", header_raw["microsecondsPerSector"])[0]
    )

    # Only valid for RK8 images
    assert header.version.encode("ascii") == versionNumber
    assert header.valid_magic
    assert header.bit_rate == 1440000
    assert header.number_of_cylinders == 203
    assert header.number_sectors_per_track == 16
    assert header.number_of_heads == 2
    assert header.microseconds_per_sector == 2500
    return header


def decode_rke_sector_header(data):
    bit_time = struct.unpack("<H", data[:SECTOR_HEADER_BIT_TIMES_LEN])[0]
    bit_count = struct.unpack("<H", data[SECTOR_HEADER_BIT_TIMES_LEN:SECTOR_HEADER_BIT_TIMES_LEN + SECTOR_HEADER_BIT_COUNT_LEN])[0]
    return bit_time, bit_count


def find_rke_sectors(fileName, rke_header: Header):
    sectors = []
    offset = FIRST_SECTOR_OFFSET

    with open(fileName, "rb") as f:
        for i in range(rke_header.number_of_sectors_total):
            f.seek(offset)
            header = f.read(SECTOR_HEADER_BIT_TIMES_LEN + SECTOR_HEADER_BIT_COUNT_LEN)
            bit_time, bit_count = decode_rke_sector_header(header)

            # Calculate data block length
            data_block_count = (bit_count // 16) if (bit_count % 16 == 0) else (bit_count // 16) + 1

            # Make sure the bit count meets the minimum data size requirement
            assert bit_count >= MINIMUM_DATA_SIZE_BITS
            assert (data_block_count * 16) >= MINIMUM_DATA_SIZE_BITS

            # head = i % rke_header.number_of_heads
            # sector_number = (i // rke_header.number_of_heads) % rke_header.number_sectors_per_track
            # cylinder = (i // (rke_header.number_of_heads * rke_header.number_sectors_per_track)) % rke_header.number_of_cylinders

            sector_number = i % rke_header.number_sectors_per_track
            head = (i // rke_header.number_sectors_per_track) % rke_header.number_of_heads
            cylinder = i // (rke_header.number_sectors_per_track * rke_header.number_of_heads)

            sector = SectorBlock(
                sector=sector_number,
                surface=head,
                cylinder=cylinder,
                offset_into_file=offset,
                bit_times_sector_to_start_bit=bit_time,
                data_bits_after_start_bit=bit_count,
                data_block_count=data_block_count,
            )

            sectors.append(sector)
            offset = offset + SECTOR_HEADER_LEN + (data_block_count * 2)
    return sectors

def read_rke_sector_data(fileName, sector_block: SectorBlock):
    rk_header = None
    rk_data = None
    rk_crc = None

    rk_data_raw = None

    with open(fileName, "rb") as f:
        # Seek to the start of the data block, skipping the sector header
        f.seek(sector_block.offset_into_file + SECTOR_HEADER_LEN)

        # This is the cylinder address when the disk formatted
        rk_header = f.read(RK_HEADER_LEN)
        # print as binary
        print(f"RK Header (binary): {' '.join(f'{byte:08b}' for byte in rk_header)}")

        # Just make sure the data length is a whole number of bytes
        assert (256 * 12) % 8 == 0

        # Read all data at once
        rk_data_raw = f.read((256 * 12) // 8)

        # Read the CRC for the data block
        rk_crc = f.read(RK_CRC_LEN)
        print(f"RK CRC (binary): {' '.join(f'{byte:08b}' for byte in rk_crc)}")

        # Make sure we didn't read more words than the data block count
        words_read = (f.tell() - sector_block.offset_into_file) / 2
        assert words_read <= sector_block.data_block_count

        # 256 PDP-8 words occupy 384 packed bytes.
        if len(rk_data_raw) != 384:
            raise ValueError(f"Expected 384 payload bytes, got {len(rk_data_raw)}")

        # Make 12bit data into 16bit words
        rk_data = []
        for i in range(0, len(rk_data_raw), 3):
            b0, b1, b2 = rk_data_raw[i:i + 3]
            word1 = (b0 | ((b1 & 0x0F) << 8)) & 0o7777
            word2 = ((b1 >> 4) | (b2 << 4)) & 0o7777
            rk_data.extend((word1, word2))
        return rk_header, rk_data, rk_crc


def decode_rk_header(rk_header):
    assert rk_header[0] & 0b00011111 == 0
    assert rk_header[1] & 0b11100000 == 0
    rk_cylinder = (struct.unpack("<H", rk_header)[0]) >> 5
    return rk_cylinder

def main():
    fileName = input_file

    # Read the rke header
    header = read_rke_header(fileName)

    # Find all the sectors in the RKE file
    sector_blocks = find_rke_sectors(fileName, header)

    data_hashes = []
    bit_count_histogram = dict()
    bit_time_histogram = dict()

    for i, sector_block in enumerate(sector_blocks):
        print(
            f"Sector Block {i}\n"
            f"  Sector:           {sector_block.sector}\n"
            f"  Surface:          {sector_block.surface}\n"
            f"  Cylinder:         {sector_block.cylinder}\n"
            f"  Offset:           {sector_block.offset_into_file:#x}\n"
            f"  Bit time:         {sector_block.bit_times_sector_to_start_bit}\n"
            f"  Bit count:        {sector_block.data_bits_after_start_bit}\n"
            f"  Data block count: {sector_block.data_block_count}"
        )

        # Decode the RK header and check integrity
        rk_header, rk_data, rk_crc = read_rke_sector_data(fileName, sector_block)
        rk_cylinder = decode_rk_header(rk_header)

        # Check that the RK cylinder matches the sector block cylinder
        assert rk_cylinder == sector_block.cylinder

        # histogram of bit counts and bit times
        bit_count_histogram[sector_block.data_bits_after_start_bit] = bit_count_histogram.get(sector_block.data_bits_after_start_bit, 0) + 1
        bit_time_histogram[sector_block.bit_times_sector_to_start_bit] = bit_time_histogram.get(sector_block.bit_times_sector_to_start_bit, 0) + 1

        # Exclude the first 2 words, often contains absolute address
        data_block_hash = hash(tuple(rk_data[2:]))
        data_hashes.append(data_block_hash)

        # Decode absolute address from the first 2 words of RK data
        sector_number = rk_data[1] & 0x0F
        side_number = (rk_data[1] >> 4) & 0x01
        cylinder_number = ((rk_data[0] & 0x01) << 7) | ((rk_data[1] >> 5) & 0x7F)

        print(
            f"      Decoded Sector number:    {sector_number}\n"
            f"      Decoded Side number:      {side_number}\n"
            f"      Decoded Cylinder number:  {cylinder_number}\n"
            f"      Data Block Hash (skip 2): {data_block_hash} "
        )

        for j, word in enumerate(rk_data):
            # if j == 0 or j == 1: continue # Skip the first 2 words containing absolute address
            print(f"      RK Data Word {j:03}:  {word:04o} {word:012b}")
            if j >= 5: break # Only print the first few data words for inspection

        # Check that the decoded absolute address matches the sector block
        # assert sector_number == sector_block.sector
        # assert side_number == sector_block.surface
        # assert cylinder_number == sector_block.cylinder

        # if sector_block.sector == 10 and sector_block.cylinder == 1:
        #     break


    # Nicely formatted output for bit count histogram
    print("\nBit count histogram:")
    for bit_count, occurrences in sorted(bit_count_histogram.items()):
        print(f"  Bit count {bit_count}, Mod: {bit_count % 16}: {occurrences} occurrences")


    # Nicely formatted output for bit time histogram
    print("\nBit time histogram:")
    for bit_time, occurrences in sorted(bit_time_histogram.items()):
        print(f"  Bit time {bit_time}, Mod: {bit_time % 16}: {occurrences} occurrences")


if __name__ == "__main__":
    main()
