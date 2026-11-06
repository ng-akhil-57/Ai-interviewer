"""
cheat_detector.py  — v4 (MediaPipe 0.10.30+ fixed)
====================================================
Removed: mediapipe.framework import (not available in 0.10.30+)
Uses only: mediapipe.tasks.python.vision API
"""

import cv2
import base64
import numpy as np
import urllib.request
import os
from dataclasses import dataclass
from typing import Optional

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision


# ──────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────

@dataclass
class CheatEvent:
    type:     str
    message:  str
    severity: str


@dataclass
class FrameResult:
    event:           CheatEvent
    annotated_b64:   Optional[str] = None
    face_confidence: float = 0.0


# ──────────────────────────────────────────────────────────────
# Oval colours (BGR for OpenCV)
# ──────────────────────────────────────────────────────────────

OVAL_COLORS = {
    "ok":             (74,  222, 128),
    "looking_away":   (251, 191,  36),
    "no_face":        (239,  68,  68),
    "multiple_faces": (239,  68,  68),
    "error":          (148, 163, 184),
}

SEVERITY_THICKNESS = {"low": 2, "medium": 3, "high": 4}


# ──────────────────────────────────────────────────────────────
# Model download helper
# ──────────────────────────────────────────────────────────────

def _download(url: str, dest: str):
    if not os.path.exists(dest):
        print(f"[CheatDetector] Downloading {dest}...")
        urllib.request.urlretrieve(url, dest)
        print(f"[CheatDetector] {dest} ready.")


# ──────────────────────────────────────────────────────────────
# Detector
# ──────────────────────────────────────────────────────────────

class CheatDetector:

    def __init__(self):
        self.cheat_log    = []
        self._frame_count = 0
        self._detector    = None
        self._landmarker  = None
        self._init_error  = None
        self._setup()

    def _setup(self):
        try:
            det_model = "face_detector.tflite"
            lm_model  = "face_landmarker.task"

            _download(
                "https://storage.googleapis.com/mediapipe-models/"
                "face_detector/blaze_face_short_range/float16/1/"
                "blaze_face_short_range.tflite",
                det_model
            )
            _download(
                "https://storage.googleapis.com/mediapipe-models/"
                "face_landmarker/face_landmarker/float16/1/"
                "face_landmarker.task",
                lm_model
            )

            # Face detector
            det_opts = mp_vision.FaceDetectorOptions(
                base_options=mp_python.BaseOptions(
                    model_asset_path=det_model
                ),
                min_detection_confidence=0.5,
            )
            self._detector = mp_vision.FaceDetector.create_from_options(det_opts)

            # Face landmarker
            lm_opts = mp_vision.FaceLandmarkerOptions(
                base_options=mp_python.BaseOptions(
                    model_asset_path=lm_model
                ),
                num_faces=2,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
            )
            self._landmarker = mp_vision.FaceLandmarker.create_from_options(lm_opts)

            print("[CheatDetector] ✅ Ready")

        except Exception as e:
            self._init_error = str(e)
            print(f"[CheatDetector] ❌ Setup failed: {e}")

    # ── I/O ───────────────────────────────────────────────────

    def decode_frame(self, b64_frame: str) -> np.ndarray:
        _, data   = b64_frame.split(",", 1) if "," in b64_frame else ("", b64_frame)
        img_bytes = base64.b64decode(data)
        arr       = np.frombuffer(img_bytes, dtype=np.uint8)
        frame     = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("cv2.imdecode returned None")
        return frame

    def encode_frame(self, frame: np.ndarray, quality: int = 80) -> str:
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            return ""
        return "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")

    # ── Oval overlay ──────────────────────────────────────────

    def _draw_oval_overlay(self, frame: np.ndarray, event: CheatEvent, confidence: float) -> np.ndarray:
        out  = frame.copy()
        h, w = out.shape[:2]
        cx, cy = w // 2, int(h * 0.46)
        rx, ry = int(w * 0.38), int(h * 0.46)

        color     = OVAL_COLORS.get(event.type, OVAL_COLORS["ok"])
        thickness = SEVERITY_THICKNESS.get(event.severity, 2)

        overlay = out.copy()
        for extra in [14, 8, 3]:
            cv2.ellipse(overlay, (cx, cy), (rx + extra, ry + extra),
                        0, 0, 360, color, thickness + 2)
        cv2.addWeighted(overlay, 0.55, out, 0.45, 0, out)
        cv2.ellipse(out, (cx, cy), (rx, ry), 0, 0, 360, color, thickness)

        mask     = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(mask, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)
        vignette = np.zeros_like(out)
        out = np.where(mask[..., None] == 0,
                       cv2.addWeighted(out, 0.55, vignette, 0.45, 0), out)

        dot_x, dot_y = cx, cy + ry + 18
        cv2.circle(out, (dot_x, dot_y), 8, color, -1)
        cv2.circle(out, (dot_x, dot_y), 8, (255, 255, 255), 1)

        font  = cv2.FONT_HERSHEY_SIMPLEX
        label = event.message[:52]
        (tw, _), _ = cv2.getTextSize(label, font, 0.48, 1)
        tx, ty = cx - tw // 2, dot_y + 22
        cv2.putText(out, label, (tx+1, ty+1), font, 0.48, (0,0,0), 2, cv2.LINE_AA)
        cv2.putText(out, label, (tx, ty),     font, 0.48, color,   1, cv2.LINE_AA)

        bar_x, bar_y, bar_w, bar_h = 12, 12, 120, 6
        cv2.rectangle(out, (bar_x, bar_y), (bar_x+bar_w, bar_y+bar_h), (30,30,30), -1)
        filled = int(bar_w * min(1.0, confidence))
        if filled > 0:
            cv2.rectangle(out, (bar_x, bar_y), (bar_x+filled, bar_y+bar_h), color, -1)
        cv2.putText(out, f"conf {int(confidence*100)}%",
                    (bar_x, bar_y+bar_h+14), font, 0.38, (180,180,180), 1, cv2.LINE_AA)

        return out

    # ── Core analysis ─────────────────────────────────────────

    def analyse_frame(self, b64_frame: str) -> FrameResult:
        self._frame_count += 1

        if self._init_error or not self._detector:
            event = CheatEvent("error", "Detector not ready", "low")
            return FrameResult(event=event)

        try:
            frame = self.decode_frame(b64_frame)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception:
            event = CheatEvent("error", "Could not decode frame", "low")
            return FrameResult(event=event)

        confidence = 0.0

        try:
            # ── Create MediaPipe image (no framework import needed) ──
            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb
            )

            # ── Face detection ────────────────────────────────
            det_result = self._detector.detect(mp_image)
            detections = det_result.detections if det_result else []

            if not detections:
                event = CheatEvent("no_face",
                                   "No face detected — please stay in frame",
                                   "high")
                self.cheat_log.append(event)
                ann = self._draw_oval_overlay(frame, event, confidence)
                return FrameResult(event=event,
                                   annotated_b64=self.encode_frame(ann),
                                   face_confidence=confidence)

            if len(detections) > 1:
                event = CheatEvent("multiple_faces",
                                   "Multiple faces detected in frame",
                                   "high")
                self.cheat_log.append(event)
                ann = self._draw_oval_overlay(frame, event, confidence)
                return FrameResult(event=event,
                                   annotated_b64=self.encode_frame(ann),
                                   face_confidence=confidence)

            # Confidence from single detection
            if det_result.detections[0].categories:
                confidence = det_result.detections[0].categories[0].score

            # ── Gaze check ────────────────────────────────────
            if self._landmarker:
                lm_result = self._landmarker.detect(mp_image)
                if lm_result and lm_result.face_landmarks:
                    lm  = lm_result.face_landmarks[0]
                    h_f, w_f = frame.shape[:2]

                    nose_x      = lm[1].x   * w_f
                    left_eye_x  = lm[33].x  * w_f
                    right_eye_x = lm[263].x * w_f
                    eye_center  = (left_eye_x + right_eye_x) / 2
                    face_width  = abs(right_eye_x - left_eye_x)
                    offset      = abs(nose_x - eye_center) / (face_width + 1e-6)

                    if offset > 0.35:
                        direction = "left" if nose_x < eye_center else "right"
                        event = CheatEvent(
                            "looking_away",
                            f"Looking {direction} — please face the camera",
                            "medium",
                        )
                        self.cheat_log.append(event)
                        ann = self._draw_oval_overlay(frame, event, confidence)
                        return FrameResult(event=event,
                                           annotated_b64=self.encode_frame(ann),
                                           face_confidence=confidence)

        except Exception as e:
            print(f"[CheatDetector] Analysis error: {e}")
            event = CheatEvent("error", "Analysis error", "low")
            ann   = self._draw_oval_overlay(frame, event, confidence)
            return FrameResult(event=event,
                               annotated_b64=self.encode_frame(ann),
                               face_confidence=confidence)

        event = CheatEvent("ok", "All clear", "low")
        ann   = self._draw_oval_overlay(frame, event, confidence)
        return FrameResult(event=event,
                           annotated_b64=self.encode_frame(ann),
                           face_confidence=confidence)

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict:
        counts = {}
        for ev in self.cheat_log:
            counts[ev.type] = counts.get(ev.type, 0) + 1

        high_count = sum(1 for e in self.cheat_log if e.severity == "high")
        risk = "High" if high_count >= 10 else "Medium" if high_count >= 4 else "Low"

        return {
            "total_events"     : len(self.cheat_log),
            "event_counts"     : counts,
            "high_severity"    : high_count,
            "risk_level"       : risk,
            "frames_processed" : self._frame_count,
            "log"              : [
                {"type": e.type, "message": e.message, "severity": e.severity}
                for e in self.cheat_log[-20:]
            ],
        }

    def reset(self):
        self.cheat_log    = []
        self._frame_count = 0


# Singleton
detector = CheatDetector()