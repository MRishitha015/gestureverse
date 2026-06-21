# 🚀 GestureVerse: Anti-Gravity Neon Gesture Game

A real-time computer vision game that transforms hand movements into immersive gameplay using webcam-based gesture tracking.

GestureVerse combines MediaPipe hand tracking, OpenCV, and Pygame to create a futuristic anti-gravity experience where players control a glowing energy orb through natural hand gestures. The project demonstrates real-time computer vision, gesture recognition, physics simulation, and interactive game development.

---

## ✨ Features

### 🎮 Gesture-Based Controls

* Real-time hand tracking using MediaPipe
* Smooth fingertip-based object control
* Pinch gesture detection for boost actions
* Fist gesture recognition for pause mode
* Open-hand tracking for natural navigation

### 🌌 Immersive Visual Experience

* Cyberpunk-inspired neon interface
* Dynamic particle systems
* Glowing energy trails
* Animated collectibles
* Screen shake effects
* Combo-based visual feedback
* Futuristic HUD and overlays

### ⚡ Physics Engine

* Spring-based movement system
* Velocity damping and inertia
* Smooth interpolation
* Responsive anti-gravity mechanics
* Real-time collision detection

### 📈 Gameplay Systems

* Score tracking
* Combo multipliers
* Collectible spawning
* Dynamic difficulty progression
* Performance-optimized rendering

---

## 🛠️ Tech Stack

| Technology | Purpose                       |
| ---------- | ----------------------------- |
| Python     | Core application              |
| OpenCV     | Webcam capture and processing |
| MediaPipe  | Real-time hand tracking       |
| Pygame     | Rendering and game loop       |
| NumPy      | Mathematical computations     |

---

## 📦 Installation

### Clone Repository

```bash
git clone https://github.com/your-username/gestureverse.git
cd gestureverse
```

### Create Virtual Environment

```bash
python -m venv .venv
```

### Activate Environment

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Application

```bash
python main.py
```

---

## 🎯 Controls

| Gesture / Key | Action                   |
| ------------- | ------------------------ |
| Index Finger  | Move energy orb          |
| Pinch Gesture | Activate boost           |
| Open Hand     | Normal tracking mode     |
| Fist          | Pause movement           |
| W             | Toggle webcam background |
| R             | Reset score              |
| ESC           | Exit game                |

---

## 🏗️ Project Architecture

```text
gestureverse/
│
├── main.py
├── hand_tracker.py
├── game_objects.py
├── requirements.txt
└── README.md
```

### Core Components

#### Hand Tracker

* Gesture recognition
* Landmark extraction
* EMA smoothing
* Motion estimation

#### Game Objects

* Orb physics
* Particle systems
* Collectibles
* Combo mechanics

#### Main Engine

* Rendering loop
* Event handling
* UI management
* Performance optimization

---

## ⚙️ Configuration

| Parameter       | Description         |
| --------------- | ------------------- |
| CAMERA_INDEX    | Webcam selection    |
| FPS_TARGET      | Frame rate target   |
| ema_alpha       | Tracking smoothness |
| accel_factor    | Orb acceleration    |
| damping         | Velocity decay      |
| PINCH_THRESHOLD | Pinch sensitivity   |

---

## 🚀 Performance Optimizations

* Exponential Moving Average (EMA) smoothing
* Reduced tracking jitter
* Efficient frame processing
* Optimized particle rendering
* Stable 60 FPS gameplay target

---

## 🔍 Troubleshooting

### Camera Not Detected

Try changing:

```python
CAMERA_INDEX = 1
```

or

```python
CAMERA_INDEX = 2
```

### Low FPS

* Close applications using the webcam
* Reduce webcam resolution
* Disable webcam background rendering

### Gesture Detection Issues

* Improve lighting conditions
* Keep the full hand visible
* Maintain consistent distance from camera

---

## 🎓 Learning Outcomes

This project demonstrates:

* Computer Vision
* Human-Computer Interaction
* Real-Time Systems
* Physics-Based Simulation
* Gesture Recognition
* Game Development
* Software Architecture

---

## 📄 License

MIT License

Feel free to use, modify, and distribute this project for educational and personal purposes.
