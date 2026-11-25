"""Text-prompted segmentation of statue renders: GroundingDINO (boxes) + SAM 2.1 (masks).

Models (Hugging Face, official repositories, loaded through transformers):
    IDEA-Research/grounding-dino-base     open-vocabulary detector
    facebook/sam2.1-hiera-large           promptable segmentation
Weights are cached in tools/polychromy_venv/models (HF_HOME is set by paint_statues.py).
"""

import numpy as np
import torch

DINO_ID = "IDEA-Research/grounding-dino-base"
SAM_ID = "facebook/sam2.1-hiera-large"


def device():
    return "mps" if torch.backends.mps.is_available() else "cpu"


class Segmenter:
    def __init__(self):
        from transformers import (AutoModelForZeroShotObjectDetection, AutoProcessor, Sam2Model,
                                  Sam2Processor)
        self.dev = device()
        self.dproc = AutoProcessor.from_pretrained(DINO_ID)
        self.dino = AutoModelForZeroShotObjectDetection.from_pretrained(DINO_ID).to(self.dev).eval()
        self.sproc = Sam2Processor.from_pretrained(SAM_ID)
        self.sam = Sam2Model.from_pretrained(SAM_ID).to(self.dev).eval()
        self._emb_key = None

    @torch.no_grad()
    def detect(self, image, prompt, threshold=0.2):
        inputs = self.dproc(images=image, text=[[prompt]], return_tensors="pt").to(self.dev)
        out = self.dino(**inputs)
        r = self.dproc.post_process_grounded_object_detection(
            out, inputs.input_ids, threshold=threshold, text_threshold=threshold,
            target_sizes=[image.size[::-1]])[0]
        return r["boxes"].cpu().numpy(), r["scores"].cpu().numpy()

    @torch.no_grad()
    def _embed(self, image, key):
        if self._emb_key != key:
            si = self.sproc(images=image, return_tensors="pt").to(self.dev)
            self._emb = self.sam.get_image_embeddings(si["pixel_values"])
            self._orig = si["original_sizes"]
            self._emb_key = key
        return self._emb

    @torch.no_grad()
    def masks_from_boxes(self, image, key, boxes):
        if len(boxes) == 0:
            return np.zeros((0,) + image.size[::-1], bool)
        emb = self._embed(image, key)
        si = self.sproc(images=image, input_boxes=[[list(map(float, b)) for b in boxes]], return_tensors="pt")
        out = self.sam(image_embeddings=emb, input_boxes=si["input_boxes"].to(self.dev), multimask_output=False)
        m = self.sproc.post_process_masks(out.pred_masks.cpu(), self._orig.cpu())[0][:, 0].numpy()
        return m > 0

    @torch.no_grad()
    def masks_from_points(self, image, key, points, labels):
        """One mask from positive (1) / negative (0) points."""
        emb = self._embed(image, key)
        si = self.sproc(images=image, input_points=[[[list(map(float, p)) for p in points]]],
                        input_labels=[[list(map(int, labels))]], return_tensors="pt")
        out = self.sam(image_embeddings=emb, input_points=si["input_points"].to(self.dev),
                       input_labels=si["input_labels"].to(self.dev), multimask_output=False)
        m = self.sproc.post_process_masks(out.pred_masks.cpu(), self._orig.cpu())[0][0, 0].numpy()
        return m > 0

    def segment(self, image, key, prompt, fg, threshold=0.2, max_box_frac=0.8, max_mask_frac=0.85,
                rel_keep=0.7, min_px=30):
        """Boxes for `prompt`, filtered, then SAM masks restricted to the statue silhouette `fg`.
        Boxes that cover most of the statue's bounding box are rejected: GroundingDINO answers an
        unknown phrase with a box around the whole figure.
        Returns list of (mask, score)."""
        ys, xs = np.where(fg)
        if len(xs) == 0:
            return []
        fx0, fx1, fy0, fy1 = xs.min(), xs.max(), ys.min(), ys.max()
        farea = float((fx1 - fx0 + 1) * (fy1 - fy0 + 1))
        boxes, scores = self.detect(image, prompt, threshold)
        keep = []
        for b, s in zip(boxes, scores):
            bx0, by0, bx1, by1 = b
            ix = max(0.0, min(bx1, fx1) - max(bx0, fx0))
            iy = max(0.0, min(by1, fy1) - max(by0, fy0))
            if ix * iy / farea > max_box_frac:
                continue
            keep.append((b, s))
        if not keep:
            return []
        smax = max(s for _, s in keep)
        keep = [(b, s) for b, s in keep if s >= rel_keep * smax]
        masks = self.masks_from_boxes(image, key, [b for b, _ in keep])
        res = []
        nfg = float(fg.sum())
        for m, (b, s) in zip(masks, keep):
            m = m & fg
            if m.sum() < min_px or m.sum() / nfg > max_mask_frac:
                continue
            res.append((m, float(s), b))
        return res
