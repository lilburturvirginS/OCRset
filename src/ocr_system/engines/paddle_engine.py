import cv2
import numpy as np
from .base import BaseOCREngine
from ocr_system.schemas import OCRLine


class PaddleOCREngine(BaseOCREngine):
    name = "paddle"

    def __init__(self, lang: str = "th"):
        from paddleocr import PaddleOCR
        self.model = PaddleOCR(
            lang=lang,
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def recognize(self, image: np.ndarray, page: int | None = None) -> list[OCRLine]:
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        result = self.model.ocr(image)
        lines: list[OCRLine] = []

        for res in result or []:
            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            boxes = res.get("rec_polys", res.get("dt_polys", []))

            for text, score, box in zip(texts, scores, boxes):
                box_list = box.tolist() if hasattr(box, "tolist") else box
                lines.append(
                    OCRLine(
                        text=text,
                        confidence=float(score),
                        box=box_list,
                        engine=self.name,
                        page=page,
                    )
                )

        return lines