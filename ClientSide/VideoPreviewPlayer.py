import cv2
import tkinter as tk
from PIL import Image, ImageTk


class VideoPreviewPlayer:
    def __init__(self, label_widget):
        self.label = label_widget
        self.cap = None
        self.is_playing = False
        self.video_path = None
        self._job = None  # To track the root.after job

    def load(self, path):
        """Loads the video file but does not play yet."""
        self.stop()  # Ensure previous video is stopped
        self.video_path = path
        self.cap = cv2.VideoCapture(path)

    def play(self):
        """Starts the video loop."""
        if not self.cap or not self.cap.isOpened():
            return

        self.is_playing = True
        self._update_frame()

    def stop(self):
        """Stops playback and releases resources."""
        self.is_playing = False
        if self._job:
            self.label.after_cancel(self._job)
            self._job = None

        if self.cap:
            self.cap.release()
            self.cap = None

    def _update_frame(self):
        """Reads one frame and schedules the next one."""
        if not self.is_playing or not self.cap:
            return

        ret, frame = self.cap.read()

        if ret:
            # 1. Resize frame to fit preview area (e.g., 250x250)
            # You might want to calculate aspect ratio here for better quality
            frame = cv2.resize(frame, (250, 250))

            # 2. Convert Color (OpenCV uses BGR, Tkinter needs RGB)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 3. Convert to Tkinter Image
            img = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img)

            # 4. Update Label
            self.label.imgtk = imgtk  # Keep reference to avoid garbage collection
            self.label.configure(image=imgtk, text="")  # Remove text if any

            # 5. Schedule next frame (33ms approx 30 FPS)
            self._job = self.label.after(33, self._update_frame)
        else:
            # Video ended, loop it
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._job = self.label.after(33, self._update_frame)
