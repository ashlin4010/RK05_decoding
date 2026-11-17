# RK05_decoding
This Repo contains notes and tools I have made to debug issues with the RK05 emulator and RK8 controller.

## Installing a PulseView protocol decoder

From PowerShell, run:

```powershell
.\protocol_decoders\install-decoder.ps1 falling_edge_data
```

Replace `falling_edge_data` with another folder name in `protocol_decoders`, or
provide an absolute folder path. The destination defaults to
`C:\Program Files\PulseView-win64-portable\share\libsigrokdecode\decoders`.
Run PowerShell as administrator if you do not have permission to write there.
For a different installation, use `-Destination 'C:\path\to\decoders'`.
Existing files with the same names are overwritten; other existing files are
left in place. Restart PulseView to load the decoder.
