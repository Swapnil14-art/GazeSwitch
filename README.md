# GazeControl

A gaze-tracking application that enables eye-gaze-based window focusing and control. GazeControl uses computer vision to track your eye movements in real-time and automatically switches focus between windows based on where you're looking, with intelligent adaptive learning.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [How It Works](#how-it-works)
<!-- - [System Requirements](#system-requirements) -->
- [Installation](#installation)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
  - [Calibration](#calibration)
  - [Hotkeys](#hotkeys)
  - [Camera Selection](#camera-selection)
  - [Adaptive Dwell Learning](#adaptive-dwell-learning)
- [Usage Guide](#usage-guide)
<!-- - [Supported Platforms](#supported-platforms) -->
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

## Overview

GazeControl is an eye-tracking input method that lets you control your computer with your gaze. It detects where you’re looking on the screen and automatically focuses the corresponding window. This is particularly useful for:

- Users with mobility limitations who benefit from hands-free control
- Multi-window workflows where you frequently switch between applications
- Accessibility enhancement for standard computer use
- Research and accessibility applications

The system combines advanced eye-tracking algorithms with adaptive learning to provide a personalised experience that improves over time based on your natural gaze behaviour.

## Features

### Core Functionality
- **Real-time Gaze Tracking**: Continuous eye-movement detection using webcam video
- **Automatic Window Focusing**: Smart window focus based on gaze position
- **Multi-camera Support**: Works with various USB cameras and built-in webcams
- **Cross-platform**: Runs on Windows and Linux

### Intelligent Control
- **Adaptive Dwell Learning**: The system automatically adjusts dwell time based on your behaviour:
  - Increases dwell time when you accidentally trigger focus too early (regret feedback)
  - Decreases dwell time as you successfully hold focus on intended windows (success feedback)
  - Ranges from 0.2s to 1.2s, converging to your optimal threshold

- **Manual Override Hotkey**: Bypass timing checks to immediately focus the current gaze target
- **Window Cycling**: Forward and backward navigation through overlapping windows at the same gaze position
- **Typing Detection**: Automatically disables gaze focus during typing to prevent interference
- **Hotkey Customization**: Configure hotkeys for all features via the system tray menu

### User Interface
- **System Tray Integration**: Lightweight menu-bar icon for quick access to all controls
- **Easy Calibration**: Simple calibration process for accurate eye tracking setup
- **Video Device Selection**: Choose between multiple cameras from the menu
- **Real-time Feedback**: Visual indicators during calibration and events
- **Release Camera**: Frees the camera, allowing other applications to use it. Available from the system tray when tracking is paused and the camera is in use.

## How It Works

### Eye Tracking Pipeline

1. **Video Capture**: Live video stream is captured from the selected camera
2. **Face Detection**: The system locates your face and extracts eye region(s)
3. **Gaze Estimation**: Advanced neural networks predict where on the screen you're looking
4. **Window Mapping**: Gaze coordinates are matched to the target window at that position
5. **Focus Decision**: The focus is applied based on dwell time and adaptive learning
6. **Feedback Processing**: User behaviour is analysed to improve future focus timing

### Dwell Time and Adaptive Learning

GazeControl uses an intelligent dwell-time system:

- **Dwell Time**: The duration your gaze must remain on a window before automatic focus triggers
- **Initial Dwell**: Default 0.5 seconds, but configurable based on your preference
- **Regret Events**: When you quickly correct focus after an automatic focus (too early), the dwell time increases
- **Success Events**: When you hold focus on a window longer than expected, the dwell time decreases
- **Convergence**: The system adapts to find the optimal dwell time matching your natural behaviour

Example: If you find automatic focus is triggering too aggressively, the system detects your quick corrections and increases dwell time. Conversely, if focusing is too slow, the system detects successful long holds and decreases dwell time.

### Hotkey System

Three customizable hotkeys control the system:

| Function | Default | Purpose |
|----------|---------|---------|
| **Manual Override** | Alt+\\ | Immediately focus the current gaze target, bypassing dwell checks |
| **Cycle Windows Forward** | Alt+] | Cycle through overlapping windows at the same gaze position |
| **Cycle Windows Reverse** | Alt+[ | Cycle backward through overlapping windows |

<!-- ## System Requirements

### Hardware
- **Processor**: Modern CPU (Intel i5/AMD Ryzen 5 or better)
- **Memory**: 4GB RAM minimum (8GB recommended)
- **Camera**: USB webcam or built-in camera with minimum 720p resolution
- **Display**: 1920x1080 or higher recommended

### Software

**Windows 10/11**:
- Python 3.8 or higher
- Windows 10 or later
- OpenCV compatible drivers

**macOS 10.13+**:
- Python 3.8 or higher
- Xcode command line tools
- Camera permission granted

**Linux (Ubuntu 18.04+, Fedora 30+, etc)**:
- Python 3.8 or higher
- X11 display server
- Camera device permissions -->

## Installation

### Quick Start (Windows)

If you have a compiled executable, simply run `GazeControl.exe`.

### From Source

#### Windows

1. **Clone the repository**:
   ```bash
   git clone https://github.com/maciejrytlewski/GazeControl.git
   cd GazeControl
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python main.py
   ```

#### Linux (Ubuntu/Debian)

1. **Install system dependencies**:
   ```bash
   sudo apt update
   sudo apt install -y \
      python3 python3-venv \
      python3-opencv \
      python3-gi \
      python3-pystray \
      libayatana-appindicator3-1
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/maciejrytlewski/GazeControl.git
   cd GazeControl
   ```

3. **Create a virtual environment (with system packages)**:
   ```bash
   python -m venv --system-site-packages venv
   source venv/bin/activate
   ```

4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Remove conflicting OpenCV packages**:
   ```bash
   pip uninstall -y opencv-python opencv-contrib-python
   ```

6. **Run the application**:
   ```bash
   python main.py
   ```

The application icon should appear in your system tray.

### Building a Standalone Executable

To create a standalone executable (Windows):

```bash
pip install pyinstaller
make build
```

The executable will be in the `dist/` directory.

## Getting Started

### First Launch

1. **Start the application**: Run the executable or `python main.py`
2. **Locate the tray icon**: It appears in your system tray (bottom-right on Windows, top-right on macOS/Linux)
3. **Right-click the icon**

### Initial Setup Checklist

- [ ] Grant camera permissions (macOS/Linux may prompt)
- [ ] Verify your camera is listed and selected in "Select Camera"
- [ ] Run calibration ("Calibrate" in the menu)
- [ ] Adjust hotkeys if desired

## Configuration

### Calibration

Calibration is essential for accurate gaze tracking. The system learns the relationship between your eye appearance and screen position.

#### How to Calibrate

1. Open the system tray menu
2. Click "Calibrate"
3. A calibration window will appear with reference points
4. Follow the on-screen instructions:
   - Look at each marker carefully
   - Keep your head relatively still
   - Try to look at the center of each target point
   - The calibration typically takes 1-2 minutes
5. Once complete, the model is saved for future sessions

#### Tips for Successful Calibration

- **Lighting**: Ensure good lighting on your face
- **Distance**: Sit at your normal working distance (typically 50-70cm from screen)
- **Head Position**: Keep your head in a natural, comfortable position
- **Eye Openness**: Make sure your eyes are fully open and visible
- **Glasses/Contacts**: Wear the same glasses/contacts you'll use while working
- **No Movement**: Minimise head movement during calibration
- **Multiple Calibrations**: If tracking accuracy drops, recalibrate (different conditions or lighting can affect performance)

#### Recalibration

If tracking accuracy degrades after extended use, recalibrate:
- Conditions change (lighting, camera position, glasses changed)
- System shows poor focus timing
- Different users are using the system

### Hotkeys

#### Viewing Current Hotkeys

Open the system tray menu → "Configure Hotkeys" to see current bindings.

#### Changing Hotkeys

1. Open system tray menu
2. Select "Configure Hotkeys"
3. Click the hotkey you want to change
4. A dialog will appear prompting you to press the new key combination
5. Press your desired key combination, key by key
6. The hotkey is saved immediately

#### Supported Key Combinations

- Single keys: `a`, `b`, `1`, `2`, etc.
- Modifiers: `<ctrl>`, `<alt>`, `<shift>`, `<cmd>`
- Special keys: Press and the system will recognize most common keys
- Examples:
  - `<alt>+\`
  - `<ctrl>+<shift>+f`
  - `<cmd>+space` (macOS)

### Camera Selection

To use a different camera:

1. Open system tray menu
2. Select "Select Camera"
3. Choose your desired camera from the list
4. The camera switches immediately
5. You may need to recalibrate if camera position/angle differs

### Adaptive Dwell Learning

Adaptive dwell learning operates automatically in the background. Here's how to work with it:

#### Understanding Dwell Learning

The system adapts by monitoring your behaviour:

- **Regret Event**: You use the manual override hotkey within 1.0s after automatic focus
  - Indicates: Focus triggered too early
  - Response: Dwell time increases (up to 1.2s)

- **Success Event**: You keep focus on a window for 2+ seconds after automatic focus
  - Indicates: Focus was well-timed
  - Response: Dwell time decreases (down to 0.2s)

- **Convergence**: The system reaches your optimal dwell time (usually 0.3-0.7s)

#### Monitoring Dwell Adaptation

The current dwell time is stored in your configuration file. To view it, you can check the config file in:
- **Windows**: `%APPDATA%/Local/GazeControl/config.json`
- **macOS**: `~/Library/Application Support/GazeControl/config.json`
- **Linux**: `~/.config/GazeControl/config.json`

#### Manual Dwell Adjustment

If you want to start with a different initial dwell time:

1. Locate your config file (see paths above)
2. Edit `config.json` and add/modify:
   ```json
   {
     "adaptive_dwell": 0.6
   }
   ```
3. Restart the application

Valid range: 0.2 (fast) to 1.2 (slow) seconds

## Usage Guide

### Basic Workflow

1. **Start Tracking**: Open tray menu → "Start Tracking"
   - Tray icon menu should show live eye tracking
   - Status updates in real-time

2. **Look at a Window**: Gaze at the window you want to focus
   - Wait for dwell time to elapse (typically 0.5s initially)
   - Window automatically comes to focus

3. **Type Normally**: Typing detection prevents accidental refocus
   - Focus stays on your current window while typing
   - Normal typing productivity flow maintained

4. **Switch Windows**:
   - **Automatic**: Look at another window, wait for dwell
   - **Manual Override**: Use Alt+\ hotkey to focus instantly
   - **Cycle**: Use Alt+] or Alt+[ to cycle between overlapping windows

5. **Stop Tracking**: Tray menu → "Stop Tracking"
   - Camera and tracking stop immediately
   - Minimal CPU/GPU usage when stopped

6. **Releasing the Camera (Optional)**: Tray menu → "Release Camera"
   - If you want to let another application access your camera while GazeControl isn’t tracking
   - The camera is freed without stopping the app entirely

### Advanced Usage

#### Using Manual Override

The manual override (Alt+\ by default) is useful for:
- Focusing instantly without waiting for dwell time
- Bypassing focus checks during dwell learning
- Providing explicit feedback to the system (triggers regret learning)

#### Window Cycling

When windows overlap at the same screen position:
1. Look at the overlapping region
2. Use Alt+] to cycle forward through windows
3. Use Alt+[ to cycle backward

<!-- #### Multi-Monitor Setup

GazeControl works across multiple monitors:
- Gaze coordinates span all displays
- Focus applies to the window under the gaze position
- Seamless multi-monitor window management -->

<!-- ## Supported Platforms

### Windows 10/11
- Full feature support
- System tray integration
- Hardware acceleration available
- Tested: Windows 11

### macOS 10.13+
- Requires camera permission grant
- System tray in menu bar
- Optimized for Apple-style window management
- Tested: macOS 11 Big Sur through 13 Ventura

### Linux (Ubuntu 18.04+, Fedora 30+)
- X11 display server required (Wayland support limited)
- System tray requires compatible desktop environment
- Works on: Ubuntu, Fedora, Debian, Linux Mint, etc. -->

## Troubleshooting

### Issue: "Camera Not Found"

**Symptoms**: Application shows no camera options, or camera selection is empty.

**Solutions**:
1. Verify camera is plugged in and recognized by OS
2. Check camera permissions:
   - **Windows**: Settings → Privacy & Security → Camera
   - **macOS**: System Preferences → Security & Privacy → Camera
   - **Linux**: User must be in `video` group: `sudo usermod -aG video $USER`
3. Restart the application after granting permissions
4. Try a different USB port (if using external camera)
5. Test camera with system utility (Windows Camera app, Photo Booth on macOS)

### Issue: Poor Tracking Accuracy

**Symptoms**: Gaze pointer is inaccurate, doesn't match where you're looking.

**Solutions**:
1. **Recalibrate**: This is the most effective solution
   - Open menu → Calibrate
   - Follow all calibration tips carefully
2. **Improve Lighting**:
   - Ensure bright, even lighting on your face
   - Avoid bright backlight or reflection on glasses
3. **Camera Positioning**:
   - Camera should be on-angle to your face (slightly below eye level)
   - Avoid extreme angles
4. **Check Eye Visibility**:
   - Ensure eyes are clearly visible to camera
   - Wipe glasses/camera lens clean
   - Adjust fringe if obstructing eyes

### Issue: Focus Triggering Too Often (or Too Rarely)

**Symptoms**: Windows focus automatically when you don't want them (or never focus).

**Solutions**:
1. **Too Aggressive** (focusing too much):
   - Initially caused by low dwell time
   - The system should auto-adapt when you use manual override
   - Use Alt+\ when focus is unwanted (teaches regret)
2. **Not Aggressive Enough** (never focuses):
   - Dwell time may be too high
   - Try manual override (Alt+\) to trigger focus
   - If manual override works, system will learn to decrease dwell
3. **Manual Adjustment**:
   - Edit config.json and set `adaptive_dwell` to 0.4 (faster) or 0.7 (slower)
   - Restart application

<!-- ### Issue: Application Won't Start

**Symptoms**: App crashes on launch or shows error dialog.

**Solutions**:
1. **Check Python Installation**:
   ```bash
   python --version
   ```
   Should show 3.8+
2. **Verify Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Check Logs**:
   - Logs saved to:
     - **Windows**: `%APPDATA%/Local/GazeControl/logs/`
     - **macOS**: `~/Library/Application Support/GazeControl/logs/`
     - **Linux**: `~/.local/share/GazeControl/logs/`
4. **Update Graphics Drivers**:
   - OpenCV requires recent GPU drivers
   - Update from manufacturer website -->

<!-- ### Issue: High CPU Usage

**Symptoms**: Application uses excessive CPU even when idle.

**Solutions**:
1. Stop tracking when not needed (menu → "Stop Tracking")
2. Check monitor refresh rate (60Hz vs 144Hz impacts CPU)
3. Ensure no other apps are competing for camera
4. Try lower resolution camera mode if available -->

### Issue: Hotkey Not Working

**Symptoms**: Manual override or cycling hotkeys don't respond.

**Solutions**:
1. **Check Hotkey Configuration**:
   - Open menu → "Configure Hotkeys"
   - Verify the hotkeys are displayed correctly
2. **Global Hotkey Conflicts**:
   - Some apps (games, IDEs) may intercept hotkeys
   - Reconfigure to unique combination
   - Try: Alt+Scrolllock, Ctrl+Shift+Grave, etc.
3. **Restart Tracking**:
   - Stop and restart tracking from menu
4. **Linux X11 Focus**:
   - Hotkeys only work when a window has focus
   - This is X11 limitation

## Advanced Configuration

### Configuration File

GazeControl stores settings in `config.json`:

**Location**:
- Windows: `%APPDATA%/Local/GazeControl/config.json`
- macOS: `~/Library/Application Support/GazeControl/config.json`
- Linux: `~/.local/share/GazeControl/config.json`

**Example Config**:
```json
{
  "camera_name": "USB Camera",
  "manual_override_hotkey": "<alt>+\\",
  "cycle_windows_hotkey": "<alt>+]",
  "cycle_windows_reverse_hotkey": "<alt>+[",
  "adaptive_dwell": 0.52
}
```

**Options**:
- `camera_name` (str): Name of selected camera device
- `manual_override_hotkey` (str): Hotkey combination for manual override
- `cycle_windows_hotkey` (str): Hotkey for forward cycling
- `cycle_windows_reverse_hotkey` (str): Hotkey for reverse cycling
- `adaptive_dwell` (float): Current adaptive dwell time (0.2-1.2s)

### Logging

Debug logs help troubleshoot issues.

**Log Location**:
- Windows: `%APPDATA%/Local/GazeControl/logs/gaze_control.log`
- macOS: `~/Library/Application Support/GazeControl/logs/gaze_control.log`
- Linux: `~/.local/share/GazeControl/logs/gaze_control.log`

**Log Rotation**: Logs rotate at 5MB, keeping 3 backup files.

**Enable Debug Logging** (modify main.py):
```python
root.setLevel(logging.DEBUG)  # Already set in default install
```

<!-- ### Switching Gaze Estimation Models

GazeControl includes two gaze estimation backends:

1. **EyeTrax** (Default): Fast, optimized for webcam input
2. **GazeFollower**: High accuracy, larger models

To switch models, edit [trackers/base_tracker.py] (in the GazeTracker class initialization):
```python
# Change from:
self.estimator: BaseTracker = EyeTraxWrapper()
# To:
self.estimator: BaseTracker = GazeFollowerWrapper()
```

Then restart the application.

--- -->

## Support and Contributing

For issues, questions, or feature requests, please refer to the project repository or contact me.

## License

See [LICENSE](LICENSE) file for details.

---

**Last Updated**: 2026
**Version**: 1.0