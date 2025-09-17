import threading
import importlib
import subprocess
import sys

# --- Auto-install missing dependencies ---
required_packages = ["pyvirtualcam>=0.14.0"]
for package in required_packages:
    pkg_name = package.split(">=")[0]
    try:
        importlib.import_module(pkg_name)
    except ImportError:
        print(f"[VirtualCamNode] Installing missing package: {package}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package])

# --- Now safe to import ---
import pyvirtualcam
import numpy as np

# --- Global state for continuous streaming ---
_stream_thread = None
_stream_running = False
_last_frame = None

class VirtualCamNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "fps": ("INT", {"default": 30, "min": 1, "max": 60}),
                "continuous": ("BOOLEAN", {"default": True}),
                "stop_stream": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "send_to_virtual_cam"
    CATEGORY = "SBCODE"

    def send_to_virtual_cam(self, image, fps, continuous, stop_stream):
        global _stream_thread, _stream_running, _last_frame

        # Prepare the frame as numpy
        img_np = (image[0].cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
        if img_np.shape[-1] == 4:
            img_np = img_np[:, :, :3]

        _last_frame = img_np  # store latest frame for thread loop

        if stop_stream:
            if _stream_running:
                print("[VirtualCamNode] Stopping virtual camera stream...")
                _stream_running = False
                if _stream_thread:
                    _stream_thread.join()
                    _stream_thread = None
                print("[VirtualCamNode] Stream stopped.")
            return (image,)

        if continuous:
            # Start streaming thread if not running
            if not _stream_running:
                _stream_running = True

                def stream_loop(frame_fps):
                    global _stream_running, _last_frame
                    try:
                        h, w, _ = _last_frame.shape
                        with pyvirtualcam.Camera(width=w, height=h, fps=frame_fps) as cam:
                            print(
                                f"[VirtualCamNode] Started virtual camera stream: {cam.device}")
                            while _stream_running:
                                if _last_frame is not None:
                                    cam.send(_last_frame)
                                cam.sleep_until_next_frame()
                    except Exception as e:
                        print(f"[VirtualCamNode] Error in streaming loop: {e}")
                    finally:
                        _stream_running = False
                        print("[VirtualCamNode] Streaming loop exited.")

                _stream_thread = threading.Thread(
                    target=stream_loop, args=(fps,), daemon=True)
                _stream_thread.start()
            else:
                # If already running, just update the frame
                pass

        else:
            # One-shot send
            h, w, _ = img_np.shape
            try:
                with pyvirtualcam.Camera(width=w, height=h, fps=fps) as cam:
                    print(
                        f"[VirtualCamNode] Sent single frame to virtual camera: {cam.device}")
                    cam.send(img_np)
                    cam.sleep_until_next_frame()
            except Exception as e:
                print(f"[VirtualCamNode] Error opening virtual camera: {e}")

        return (image,)


NODE_CLASS_MAPPINGS = {
    "VirtualCamNode": VirtualCamNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VirtualCamNode": "Virtual Camera Output"
}
