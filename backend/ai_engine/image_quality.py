"""
Image Quality Assessment Module - DermaCare AI
===============================================
Evaluates skin lesion images for diagnostic quality.
Implements the 'Gate' logic for Gated Multimodal Architecture.
"""

import base64
import io
import logging
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("DermaCare_AI.image_quality")

class QualityLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NON_DIAGNOSTIC = "non_diagnostic"

@dataclass
class ImageQualityResult:
    quality_level: QualityLevel
    brightness_score: float  # 0.0 - 1.0
    contrast_score: float   # 0.0 - 1.0
    sharpness_score: float  # 0.0 - 1.0
    overall_score: float    # 0.0 - 1.0
    is_skin_like: bool      # True if image appears to be skin/flesh
    is_dermoscopic: bool     # True if dermoscopic image detected
    warnings: list
    recommendations: list

class ImageQualityAnalyzer:
    """
    Analyzes lesion images for diagnostic quality.
    Used as the 'Gate' in Gated Multimodal Architecture.
    """
    
    BRIGHTNESS_THRESHOLD_HIGH = 0.7
    BRIGHTNESS_THRESHOLD_LOW = 0.2
    CONTRAST_THRESHOLD = 0.15
    SHARPNESS_THRESHOLD = 0.3
    
    NON_SKIN_PATTERNS = [
        "fabric", "rug", "carpet", "textile", "clothing",
        "wood", "metal", "plastic", "paper", "wall",
        "sky", "grass", "water", "building", "furniture"
    ]
    
    SKIN_LIKE_COLORS = {
        "pinkish": (255, 182, 193),
        "reddish": (255, 100, 100),
        "brownish": (139, 90, 43),
        "tan": (210, 180, 140),
    }
    
    def __init__(self):
        self.analysis_count = 0
    
    def analyze_image(self, image_data: str) -> ImageQualityResult:
        """
        Main entry point for image quality analysis.
        
        Args:
            image_data: Base64 encoded image string or file path
            
        Returns:
            ImageQualityResult with quality assessment
        """
        self.analysis_count += 1
        
        try:
            if image_data.startswith("data:image"):
                image_data = image_data.split(",")[1]
            
            image_bytes = base64.b64decode(image_data)
            scores = self._calculate_quality_scores(image_bytes)
            
            brightness = scores["brightness"]
            contrast = scores["contrast"]
            sharpness = scores["sharpness"]
            is_skin = scores["is_skin_like"]
            is_dermo = scores["is_dermoscopic"]
            
            overall = (brightness * 0.3 + contrast * 0.3 + sharpness * 0.4)
            
            warnings = []
            recommendations = []
            
            if brightness < self.BRIGHTNESS_THRESHOLD_LOW:
                warnings.append("Image is too dark - may affect visibility of lesion details")
                recommendations.append("Retake photo with better lighting")
            elif brightness > self.BRIGHTNESS_THRESHOLD_HIGH:
                warnings.append("Image may be overexposed")
                recommendations.append("Avoid direct flash, use diffused lighting")
            
            if contrast < self.CONTRAST_THRESHOLD:
                warnings.append("Low contrast - lesion edges may be unclear")
                recommendations.append("Ensure good lighting to highlight lesion borders")
            
            if sharpness < self.SHARPNESS_THRESHOLD:
                warnings.append("Image appears blurry")
                recommendations.append("Hold camera steady, ensure focus is correct")
            
            if not is_skin:
                warnings.append("Image does not appear to contain skin tissue")
                recommendations.append("Ensure the lesion/affected area is clearly visible")
            
            if is_dermo:
                recommendations.append("Dermoscopic image detected - excellent for analysis")
            
            quality_level = self._determine_quality_level(
                overall, brightness, contrast, sharpness, is_skin
            )
            
            return ImageQualityResult(
                quality_level=quality_level,
                brightness_score=brightness,
                contrast_score=contrast,
                sharpness_score=sharpness,
                overall_score=overall,
                is_skin_like=is_skin,
                is_dermoscopic=is_dermo,
                warnings=warnings,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Image quality analysis failed: {e}")
            return self._create_default_result()
    
    def _calculate_quality_scores(self, image_bytes: bytes) -> Dict[str, float]:
        """
        Calculate individual quality metrics for the image.
        Uses PIL for basic image analysis.
        """
        try:
            from PIL import Image
            import numpy as np
            
            img = Image.open(io.BytesIO(image_bytes))
            
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            img_array = np.array(img)
            
            brightness = self._calculate_brightness(img_array)
            contrast = self._calculate_contrast(img_array)
            sharpness = self._calculate_sharpness(img_array)
            is_skin = self._detect_skin_tone(img_array)
            is_dermo = self._detect_dermoscopic(img_array)
            
            return {
                "brightness": brightness,
                "contrast": contrast,
                "sharpness": sharpness,
                "is_skin_like": is_skin,
                "is_dermoscopic": is_dermo
            }
            
        except ImportError:
            logger.warning("PIL not available, using heuristic scoring")
            return self._heuristic_scoring()
        except Exception as e:
            logger.error(f"Quality scoring failed: {e}")
            return self._heuristic_scoring()
    
    def _calculate_brightness(self, img_array) -> float:
        """Calculate average brightness (0.0 - 1.0)"""
        try:
            import numpy as np
            gray = np.mean(img_array, axis=2)
            mean_brightness = np.mean(gray) / 255.0
            return float(mean_brightness)
        except:
            return 0.5
    
    def _calculate_contrast(self, img_array) -> float:
        """Calculate local contrast (0.0 - 1.0)"""
        try:
            import numpy as np
            gray = np.mean(img_array, axis=2)
            std_dev = np.std(gray) / 255.0
            return min(float(std_dev * 5), 1.0)
        except:
            return 0.3
    
    def _calculate_sharpness(self, img_array) -> float:
        """Estimate sharpness using edge detection"""
        try:
            import numpy as np
            from scipy import ndimage
            
            gray = np.mean(img_array, axis=2)
            
            sobel_x = ndimage.sobel(gray, axis=0)
            sobel_y = ndimage.sobel(gray, axis=1)
            gradient_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
            
            sharpness = np.mean(gradient_magnitude) / 255.0
            return min(float(sharpness * 3), 1.0)
        except:
            try:
                import numpy as np
                gray = np.mean(img_array, axis=2).astype(float)
                laplacian_var = np.var(np.diff(gray, axis=0)) + np.var(np.diff(gray, axis=1))
                return min(float(laplacian_var / 1000), 1.0)
            except:
                return 0.5
    
    def _detect_skin_tone(self, img_array) -> bool:
        """Detect if image contains skin-like colors"""
        try:
            import numpy as np
            
            r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
            
            skin_mask = (
                (r > 95) & (g > 40) & (b > 20) &
                (r > g) & (r > b) &
                (r - g > 15) & (r - b > 15)
            )
            
            skin_ratio = np.sum(skin_mask) / (img_array.shape[0] * img_array.shape[1])
            
            return skin_ratio > 0.05
            
        except:
            return True
    
    def _detect_dermoscopic(self, img_array) -> bool:
        """Detect if image appears to be a dermoscopic/close-up image"""
        try:
            import numpy as np
            
            aspect_ratio = img_array.shape[1] / img_array.shape[0]
            
            uniform_region_ratio = self._check_uniformity(img_array)
            
            has_circular_pattern = self._detect_circular_patterns(img_array)
            
            if uniform_region_ratio > 0.3 or has_circular_pattern:
                return True
            
            return False
            
        except:
            return False
    
    def _check_uniformity(self, img_array) -> float:
        """Check for uniform lighting typical of dermoscopy"""
        try:
            import numpy as np
            corners = [
                img_array[:50, :50],
                img_array[:50, -50:],
                img_array[-50:, :50],
                img_array[-50:, -50:]
            ]
            
            center = img_array[
                img_array.shape[0]//4:3*img_array.shape[0]//4,
                img_array.shape[1]//4:3*img_array.shape[1]//4
            ]
            
            corner_means = [np.mean(c) for c in corners]
            center_mean = np.mean(center)
            
            variance = np.var(corner_means + [center_mean])
            
            return min(float(variance / 10000), 1.0)
        except:
            return 0.0
    
    def _detect_circular_patterns(self, img_array) -> bool:
        """Simple detection of circular patterns (dermoscopy artifact)"""
        try:
            import numpy as np
            gray = np.mean(img_array, axis=2)
            
            center_y, center_x = gray.shape[0]//2, gray.shape[1]//2
            y, x = np.ogrid[:gray.shape[0], :gray.shape[1]]
            
            mask = (x - center_x)**2 + (y - center_y)**2 < (min(gray.shape)//3)**2
            
            center_region = gray[mask]
            outer_region = gray[~mask]
            
            if len(center_region) > 0 and len(outer_region) > 0:
                center_mean = np.mean(center_region)
                outer_mean = np.mean(outer_region)
                
                if abs(center_mean - outer_mean) > 20:
                    return True
            
            return False
        except:
            return False
    
    def _heuristic_scoring(self) -> Dict[str, float]:
        """Fallback scoring when image processing fails"""
        return {
            "brightness": 0.5,
            "contrast": 0.4,
            "sharpness": 0.5,
            "is_skin_like": True,
            "is_dermoscopic": False
        }
    
    def _determine_quality_level(
        self, 
        overall: float, 
        brightness: float, 
        contrast: float, 
        sharpness: float,
        is_skin: bool
    ) -> QualityLevel:
        """Determine quality level based on scores"""
        
        if not is_skin:
            return QualityLevel.NON_DIAGNOSTIC
        
        if overall >= 0.7 and brightness >= 0.3 and sharpness >= 0.4:
            return QualityLevel.HIGH
        
        if overall >= 0.4 and brightness >= 0.2 and sharpness >= 0.25:
            return QualityLevel.MEDIUM
        
        return QualityLevel.LOW
    
    def _create_default_result(self) -> ImageQualityResult:
        """Create default result for failed analysis"""
        return ImageQualityResult(
            quality_level=QualityLevel.LOW,
            brightness_score=0.5,
            contrast_score=0.3,
            sharpness_score=0.4,
            overall_score=0.4,
            is_skin_like=True,
            is_dermoscopic=False,
            warnings=["Image quality could not be assessed"],
            recommendations=["Ensure clear, well-lit image of the lesion"]
        )
    
    def should_use_multimodal(self, quality_result: ImageQualityResult) -> Tuple[bool, str]:
        """
        Determine if multimodal (image + metadata) approach should be used.
        Returns (use_multimodal, reason)
        """
        if quality_result.quality_level == QualityLevel.NON_DIAGNOSTIC:
            return False, "non_skin_image"
        
        if quality_result.quality_level == QualityLevel.LOW:
            return False, "low_image_quality"
        
        if quality_result.overall_score < 0.5:
            return False, "marginal_quality"
        
        return True, "good_quality"
    
    def get_multimodal_weights(
        self, 
        quality_result: ImageQualityResult,
        has_history: bool = False
    ) -> Dict[str, float]:
        """
        Calculate dynamic weights for multimodal fusion based on image quality.
        When quality is low, metadata weighs more heavily.
        """
        base_weights = {
            "image": 0.6,
            "metadata": 0.4
        }
        
        if quality_result.quality_level == QualityLevel.HIGH:
            return {"image": 0.75, "metadata": 0.25}
        
        if quality_result.quality_level == QualityLevel.MEDIUM:
            if has_history:
                return {"image": 0.5, "metadata": 0.5}
            return {"image": 0.6, "metadata": 0.4}
        
        if quality_result.quality_level == QualityLevel.LOW:
            if has_history:
                return {"image": 0.25, "metadata": 0.75}
            return {"image": 0.3, "metadata": 0.7}
        
        if quality_result.quality_level == QualityLevel.NON_DIAGNOSTIC:
            return {"image": 0.0, "metadata": 1.0}
        
        return base_weights


analyzer = ImageQualityAnalyzer()

def analyze_lesion_image(image_data: str) -> ImageQualityResult:
    """Convenience function for image quality analysis."""
    return analyzer.analyze_image(image_data)
