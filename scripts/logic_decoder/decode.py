import struct

HEADER_LENGTH = 16
CRC_LENGTH = 16
DATA_WORD_LENGTH = 12
DATA_WORDS_COUNT = 256


def extract_data(file_path):
    preamble_length = 0
    header = []
    data_words = []
    CRC = []
    data = []

    with open(file_path, encoding="utf-8-sig") as file:
        bits = (int(line) for line in file if line.strip())
        for bit in bits:
            if bit == 1:
                break
            preamble_length += 1

        data = list(bits)
    assert len(data) >= 3104, "Not enough data bits"
    data = data[:3104] # Keep only data bits

    # Extract header
    header = data[:HEADER_LENGTH]
    header = header[:8][::-1] + header[8:][::-1]

    # Extract raw data words
    raw_data_words = data[HEADER_LENGTH:HEADER_LENGTH + (DATA_WORDS_COUNT * DATA_WORD_LENGTH)]
    assert len(raw_data_words) / DATA_WORD_LENGTH == DATA_WORDS_COUNT, "Data words count mismatch"

    # Extract CRC
    CRC = data[HEADER_LENGTH + (DATA_WORDS_COUNT * DATA_WORD_LENGTH):HEADER_LENGTH + (DATA_WORDS_COUNT * DATA_WORD_LENGTH) + CRC_LENGTH]
    CRC = CRC[:8][::-1] + CRC[8:][::-1]
    assert len(CRC) == CRC_LENGTH, "CRC length mismatch"

    for start in range(0, len(raw_data_words), 12):
        word = 0
        for bit in reversed(raw_data_words[start:start + 12]):
            word = (word << 1) | bit
        data_words.append(word)

    return preamble_length, header, data_words, CRC


def decode_rk_header(rk_header):
    assert rk_header[0] & 0b00011111 == 0
    assert rk_header[1] & 0b11100000 == 0
    rk_cylinder = (struct.unpack("<H", rk_header)[0]) >> 5
    return rk_cylinder


def decode_seek(file_path):
    preamble_length = 0
    header = []
    data = []

    with open(file_path, encoding="utf-8-sig") as file:
        bits = (int(line) for line in file if line.strip())
        for bit in bits:
            if bit == 1:
                break
            preamble_length += 1

        data = list(bits)
    assert len(data) >= 16, "Not enough data bits"
    header = data[:16] # Keep only data bits
    header = header[:8][::-1] + header[8:][::-1]

    # Decode RK header to get the cylinder number
    header_low_byte = int("".join(str(bit) for bit in header[:8]), 2)
    header_high_byte = int("".join(str(bit) for bit in header[8:]), 2)
    header_bytes = bytes([header_low_byte, header_high_byte])
    rk_cylinder = decode_rk_header(header_bytes)

    return preamble_length, header, rk_cylinder



def decode_file(file_path):
    preamble_length, header, data_words, CRC = extract_data(file_path)

    # Decode absolute address from the first 2 words of RK data
    sector_number = data_words[1] & 0x0F
    side_number = (data_words[1] >> 4) & 0x01
    cylinder_number = ((data_words[0] & 0x01) << 7) | ((data_words[1] >> 5) & 0x7F)

    print(
        f"Sector number:    {sector_number}\n"
        f"Side number:      {side_number}\n"
        f"Cylinder number:  {cylinder_number}"
    )

    # Debug output
    print(f"    Preamble: {preamble_length}")
    print(f"    Header: {"".join(str(bit) for bit in header)}")
    print(f"    CRC: {"".join(str(bit) for bit in CRC)}")

    # Print data words in a more readable format in octal
    for i, word in enumerate(data_words):
        print(f"        Data Word {i:03}: {word:04o} {word:012b}")
        if i > 4:
            break
    print()



def main():

    """
        Bad starts:
        Sector number:    10
        Side number:      0
        Cylinder number:  1
    """

    write_sequence = 0
    read_sequence = 0

    print("================== Track 1 ==================")
    for i in range(0, 16):
        print(f"Decoding file {i}, write sequence {write_sequence}")
        decode_file(f"good/write/track_1/{i+1}.txt")
        write_sequence = (write_sequence + 3) % 16

    print("================== Track 2 ==================")
    for i in range(0, 16):
        print(f"Decoding file {i}, write sequence {write_sequence}")
        decode_file(f"good/write/track_2/{i+1}.txt")
        write_sequence = (write_sequence + 3) % 16

    print("================== Track 0 ==================")
    for i in range(0, 16):
        print(f"Decoding file {i}, write sequence {write_sequence}")
        decode_file(f"good/write/track_3/{i+1}.txt")
        write_sequence = (write_sequence + 3) % 16


    print("=============================================")
    print("==================  Read  ==================")
    print("================== Track 1 ==================")
    read_sequence = 0
    for i in range(0, 3):
        print(f"Decoding file {i}, read sequence {read_sequence}")
        decode_file(f"good/read/track_1/{i+1}.txt")
        read_sequence = (read_sequence + 5) % 16

    print("================== Track 2 ==================")
    read_sequence = 0
    for i in range(0, 3):
        print(f"Decoding file {i}, read sequence {read_sequence}")
        decode_file(f"good/read/track_2/{i+1}.txt")
        read_sequence = (read_sequence + 5) % 16

    print("================== Track 0 ==================")
    read_sequence = 0
    for i in range(0, 3):
        print(f"Decoding file {i}, read sequence {read_sequence}")
        decode_file(f"good/read/track_3/{i+1}.txt")
        read_sequence = (read_sequence + 5) % 16



    print("==================== Bad =====================")
    print("================== Track 1 ==================")
    read_sequence = 0
    for i in range(0, 3):
        print(f"Decoding file {i}, read sequence {read_sequence}")
        decode_file(f"bad/read/track_1/{i+1}.txt")
        read_sequence = (read_sequence + 5) % 16

    # # print()
    # decode_file(f"bad/track_1_s_10.txt")

    # # Decode seek
    # preamble_length, header, rk_cylinder = decode_seek("good/seek/good_track_3.txt")
    # print(f"Seek: Preamble length: {preamble_length}, RK Cylinder: {rk_cylinder}\n")

if __name__ == "__main__":
    main()
