import mss
import numpy as np
import cv2

class ScreenCapture:
    def __init__(self):
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1] # Primary monitor
        self.max_width = 1920 

    def capture(self) -> np.ndarray:
        sct_img = self.sct.grab(self.monitor)
        
        
        img = np.frombuffer(sct_img.bgra, dtype=np.uint8).reshape((sct_img.height, sct_img.width, 4))
        
     
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        h, w = img.shape[:2]
        if w > self.max_width:
            new_w, new_h = self.max_width, int(h * (self.max_width / w))
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR) # INTER_LINEAR cho tốc độ xử lý nhanh hơn rất nhiều, giảm giật lag
            
        return img
