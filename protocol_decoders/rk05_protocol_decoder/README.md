# RK05 (RK8-E) for PulseView

Copy the `rk05` folder into a directory shown under **Settings → About → Protocol decoder search paths**. Restart PulseView and add **RK05 (RK8-E)**. [Sigrok decoder installation guide](https://sigrok.org/wiki/Protocol_decoder_HOWTO#Tips)

## Assign the captured signals

| To decode | Assign |
| --- | --- |
| Reads | **READ CLK** and **READ DATA** |
| Writes | **WRITE**, the combined write clock and data line |

Map **READ GATE** or **WRITE GATE** if captured. Otherwise the decoder uses gaps between pulses to find the ends of bursts. The read sample delay defaults to **440 ns** after the falling edge. The write clock period defaults to **690 ns**. The decoder looks for at least eight zero bits before sync. Lower **Minimum preamble zeros** if the capture starts close to the sync bit.

## Read the trace

- **Operations** and **Diagnostic address** use words 0 and 1 of the sector data. `Track/Cyl` is the cylinder, `H` is the head or side, and `S` is the sector. The fields are displayed in decimal.
- **Disk headers** show the recorded `Track/Cyl`. A `?` indicates invalid header padding. The decoder flags a mismatch between the header cylinder and the diagnostic cylinder. For ordinary disk contents, set **Diagnostic address in data words 0 and 1** to **no** to display the header cylinder in **Operations**.
- **Data words** shows all 256 12-bit words in four-digit octal. **CRC** displays the recorded bits in the byte order used by the Python script.

| First two data words (octal) | Sector | Side | Track/Cyl |
| --- | ---: | ---: | ---: |
| `0000 0040` | 0 | 0 | 1 |
| `0000 0110` | 8 | 0 | 2 |

To export octal words, set **Settings → Decoders → Annotation export format** to `%1`. Right-click the **Data words** row and choose **Export all annotations for this row**. **Binary Decoder Output** also exports complete read or write sectors as 256 unsigned little-endian 16-bit values per sector. [PulseView user manual](https://sigrok.org/doc/pulseview/0.4.2/manual.html)

## RK8-E connector pins

| Decoder input | Connector pin | Signal level |
| --- | --- | --- |
| READ CLK | J1-F | Active low |
| READ DATA | J1-D | Active low |
| WRITE | J2-KK | Active low |
| READ GATE | J1-L | Active low |
| WRITE GATE | J1-BB | Active low |

[DEC RK05 System Principles and Interface, tables 6-1 and 6-2](https://bitsavers.org/pdf/dec/disc/rk05/EY-D2055-WB-001_RK05_SPI.pdf)
