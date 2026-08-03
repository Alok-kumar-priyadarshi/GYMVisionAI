# Exercise Detector Engine

## Overview

The Exercise Detector Engine is responsible for analyzing human pose landmarks,
counting repetitions, detecting exercise stages, validating movement quality,
and producing structured feedback for supported exercises.

Each supported exercise has its own detector implementation.

```
MediaPipe Pose
        │
        ▼
33 Pose Landmarks
        │
        ▼
Exercise Detector
        │
        ▼
Exercise Metrics
        │
        ▼
Rep Counter
        │
        ▼
Form Validation
        │
        ▼
Live Feedback
```

The detector layer is the core of GymTrainerCoach's real-time analysis system.

---

# Architecture

Every detector inherits from the common base class.

```
BaseExercise
      │
      ├── PushUpDetector
      ├── BodyweightSquatDetector
      ├── PlankDetector
      ├── BurpeesDetector
      ├── RussianTwistsDetector
      ├── ...
      └── WallSitDetector
```

The base class provides common utilities including:

- Angle calculation
- Landmark extraction
- Shared runtime state
- Helper methods

Each detector contains only the exercise-specific logic.

---

# Detector Lifecycle

Every detector follows the same lifecycle.

```
Create Detector

↓

reset()

↓

Receive MediaPipe Landmarks

↓

process()

↓

Return Detection Result

↓

Repeat
```

---

# Detector Interface

Every detector inherits from:

```python
class BaseExercise:
```

and implements:

```python
reset()

process(landmarks)
```

Callers use `analyze(landmarks)`, provided by `BaseExercise`, which validates the
frame and normalises `process()` output into the `DetectorResult` contract.

```python
from app.engines.exercise import DetectorRegistry

detector = DetectorRegistry.create("push_ups")
result = detector.analyze(landmarks)
```

---

# reset()

Resets the detector before starting a new exercise session.

Typical responsibilities include:

- Reset repetition count
- Reset stage
- Reset internal state variables

Example:

```python
detector.reset()
```

---

# process()

Called once for every incoming camera frame.

Input:

- MediaPipe pose landmarks

Responsibilities:

- Calculate joint angles
- Detect exercise phase
- Count repetitions
- Validate form
- Produce exercise metrics

Returns a structured result.

Example:

```python
{
    "reps": 12,
    "stage": "down",
    "feedback": [],
    "metrics": {}
}
```

---

# Internal Responsibilities

Each detector is responsible for:

- Landmark validation
- Joint angle calculations
- Stage detection
- Rep counting
- Form validation
- Exercise-specific feedback

No detector should perform:

- Database operations
- API communication
- UI rendering
- AI prompt generation

These responsibilities belong to higher application layers.

---

# Exercise Categories

The current implementation supports 29 exercises.

`arm_circles_detector.py` is present but unregistered: Arm Circles is not a
supported exercise in Version 1. See `docs/12_reference/01_SUPPORTED_EXERCISES.md`.

## Warm-up

- Jumping Jacks
- High Knees
- Butt Kicks
- Hip Circles

---

## Lower Body

- Bodyweight Squats
- Sumo Squats
- Forward Lunges
- Reverse Lunges
- Side Lunges
- Glute Bridges
- Single-leg Glute Bridges
- Wall Sit
- Calf Raises
- Step-ups

---

## Upper Body

- Push-ups
- Knee Push-ups
- Incline Push-ups
- Pike Push-ups
- Triceps Dips

---

## Core

- Plank
- Side Plank
- Bicycle Crunches
- Mountain Climbers
- Dead Bug
- Bird Dog
- Leg Raises
- Russian Twists
- Flutter Kicks

Plank, Side Plank and Wall Sit are hold-based. They report `stage` only; hold
duration is accumulated by the exercise session service, which owns the clock.

---

## Full Body

- Burpees

---

# Design Principles

Every detector should:

- Detect only one exercise
- Have a single responsibility
- Be independent from other detectors
- Use BaseExercise utilities whenever possible
- Return a consistent output structure

---

# Future Improvements

Future versions may introduce:

- Shared movement analyzers
- Configurable thresholds
- Multi-person tracking
- Dynamic calibration
- Personalized form correction
- Exercise-specific AI coaching