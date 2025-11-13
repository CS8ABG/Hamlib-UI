# Hamlib UI

**Hamlib UI** is a user-friendly GUI for managing [Hamlib](https://hamlib.org/) installations and running `rigctld`, `rotctld`, and `ampctld` on Windows. It allows you to download the latest Hamlib release, list supported radios, rotors, and amplifiers, and configure and run the Hamlib daemons with ease.

---

## Features

- Download and install the latest Hamlib release directly from GitHub.
- List all supported radios, rotors, and amplifiers.
- Configure serial ports, TCP ports, CI-V addresses, and PTT settings.
- Start and stop `rigctld`, `rotctld`, and `ampctld` from the GUI.
- Show real-time output from running processes.
- Save and restore your last configuration automatically.

---

### Windows Executable

Download the latest executable from the [releases page](https://github.com/CS8ABG/Hamlib-UI/releases). No Python installation is required.  

1. Download `HamlibUI.exe`.
2. Run the executable.
3. The application will create a `hamlib` folder in the same directory for the Hamlib binaries.


## Supported Platforms

* Windows 10 / 11 (64-bit recommended)

---


## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## Author

**Bruno, CS8ABG**

---

## Notes

* The GUI automatically detects available serial ports.
* The downloaded Hamlib release is stored in the `hamlib` folder in the same directory as the executable.
* Configuration settings are saved automatically and restored on the next launch.


