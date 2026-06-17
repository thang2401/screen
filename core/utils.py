import cv2
import numpy as np

class ImageUtils:
    @staticmethod
    def compute_delta(prev_img: np.ndarray, curr_img: np.ndarray, threshold: int = 30) -> np.ndarray:
        """
        Computes the delta between two images.
        Returns a mask where changes occurred.
        """
        if prev_img is None:
            return curr_img

        if prev_img.shape != curr_img.shape:
            return curr_img

        # Simple difference (can be optimized further with grid approaches)
        diff = cv2.absdiff(prev_img, curr_img)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        
        # Apply mask to current image, keep only changed pixels, rest is black
        res = cv2.bitwise_and(curr_img, curr_img, mask=mask)
        return res

    @staticmethod
    def extract_delta_grid(prev_img: np.ndarray, curr_img: np.ndarray, grid_size: int = 128) -> list:
        """
        Advanced Vectorized Delta Grid encoding.
        Uses pure Numpy matrix reshaping to find changed blocks instantly without python loops.
        """
        if prev_img is None or prev_img.shape != curr_img.shape:
            return [{'x': 0, 'y': 0, 'w': curr_img.shape[1], 'h': curr_img.shape[0], 'data': curr_img}]
            
        changes = []
        h, w = curr_img.shape[:2]
        
        # 1. Vectorized Absolute Difference
        diff = cv2.absdiff(prev_img, curr_img)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        
        # 2. Pad images so dimensions are perfectly divisible by grid_size
        pad_h = (grid_size - h % grid_size) % grid_size
        pad_w = (grid_size - w % grid_size) % grid_size
        
        if pad_h > 0 or pad_w > 0:
            mask_padded = np.pad(mask, ((0, pad_h), (0, pad_w)), mode='constant', constant_values=0)
            curr_padded = np.pad(curr_img, ((0, pad_h), (0, pad_w), (0, 0)), mode='edge')
        else:
            mask_padded = mask
            curr_padded = curr_img
            
        # 3. Fast Vectorized Block Evaluation using Reshape and Any()
        rows = mask_padded.shape[0] // grid_size
        cols = mask_padded.shape[1] // grid_size
        
        # Reshape to (rows, grid_size, cols, grid_size)
        mask_4d = mask_padded.reshape(rows, grid_size, cols, grid_size)
        
        # Check if any pixel in each block is > 0
        changed_blocks = mask_4d.any(axis=(1, 3))
        
        # 4. Extract indices of ONLY the blocks that changed
        changed_row_indices, changed_col_indices = np.where(changed_blocks)
        num_blocks = len(changed_row_indices)
        
        if num_blocks == 0:
            return changes
            
        # TỐI ƯU VIDEO: Nối các khối thành 1 Bounding Box lớn nếu có quá nhiều khối thay đổi (> 10 khối ~ 8% màn hình)
        # Việc này giảm số lượng lệnh ctx.drawImage() trên Web từ hàng chục lệnh xuống còn 1 lệnh duy nhất, 
        # giúp Browser không bị quá tải GC (Garbage Collection) và duy trì mượt mà 60 FPS.
        if num_blocks > 10:
            min_r, max_r = int(np.min(changed_row_indices)), int(np.max(changed_row_indices))
            min_c, max_c = int(np.min(changed_col_indices)), int(np.max(changed_col_indices))
            
            y = min_r * grid_size
            x = min_c * grid_size
            end_y = min((max_r + 1) * grid_size, h)
            end_x = min((max_c + 1) * grid_size, w)
            
            changes.append({
                'x': x, 'y': y,
                'w': end_x - x, 'h': end_y - y,
                'data': curr_img[y:end_y, x:end_x]
            })
            return changes
        
        # 5. Extract blocks (only iterating over changed ones)
        for r, c in zip(changed_row_indices, changed_col_indices):
            y, x = r * grid_size, c * grid_size
            
            # Clamp back to original unpadded dimensions
            end_y = min(y + grid_size, h)
            end_x = min(x + grid_size, w)
            
            # Avoid sending zero-width/height blocks due to padding clipping
            if y >= h or x >= w:
                continue
                
            grid_data = curr_padded[y:end_y, x:end_x]
            changes.append({
                'x': int(x), 'y': int(y),
                'w': int(end_x - x), 'h': int(end_y - y),
                'data': grid_data
            })
                    
        return changes
