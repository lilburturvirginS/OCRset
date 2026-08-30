#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab7_metrics.py - ไลบรารีวัดผล CER/WER สำหรับ Lab 7B
"""
from __future__ import annotations
import csv, re, unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable


def normalize(text: Any, level: str = "basic") -> str:
    if text is None:
        return ""
    s = unicodedata.normalize("NFC", str(text)).lower()
    if level == "strict":
        s = re.sub(r"\s+", "", s)
    else:
        s = re.sub(r"[\s\xa0]+", " ", s).strip()
    return s


def _edit_distance(a: list, b: list) -> int:
    m, n = len(a), len(b)
    if m < n:
        a, b = b, a
        m, n = n, m
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[:]
        dp[0] = i
        for j in range(1, n + 1):
            dp[j] = prev[j-1] if a[i-1] == b[j-1] else 1 + min(prev[j], dp[j-1], prev[j-1])
    return dp[n]


def cer(gt: str, pred: str, norm_level: str = "basic") -> float:
    g = normalize(gt, norm_level)
    p = normalize(pred, norm_level)
    if not g:
        return 0.0 if not p else 1.0
    return min(_edit_distance(list(g), list(p)) / len(g), 1.0)


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    thai = sum(1 for c in text if "\u0e00" <= c <= "\u0e7f")
    if thai > len(text) * 0.2:
        try:
            from pythainlp import word_tokenize
            return [t for t in word_tokenize(text, engine="newmm", keep_whitespace=False) if t.strip()]
        except Exception:
            pass
    return text.split()


def wer(gt: str, pred: str) -> float:
    g_words = _tokenize(normalize(gt, "basic"))
    p_words = _tokenize(normalize(pred, "basic"))
    if not g_words:
        return 0.0 if not p_words else 1.0
    return min(_edit_distance(g_words, p_words) / len(g_words), 1.0)


@dataclass
class FieldStat:
    label: str
    cer_sum: float = 0.0
    wer_sum: float = 0.0
    n: int = 0
    n_wer: int = 0
    errors: list = field(default_factory=list)

    def add(self, gt_val: Any, pred_val: Any, key: str, track_wer: bool = False) -> None:
        g = "" if gt_val is None else str(gt_val)
        p = "" if pred_val is None else str(pred_val)
        c = cer(g, p)
        self.cer_sum += c
        self.n += 1
        if track_wer:
            self.wer_sum += wer(g, p)
            self.n_wer += 1
        if c > 0.0 and len(self.errors) < 20:
            self.errors.append({"key": str(key)[:40], "gt": g[:100], "pred": p[:100], "cer": round(c, 4)})

    @property
    def avg_cer(self) -> float:
        return self.cer_sum / self.n if self.n else 0.0

    @property
    def avg_wer(self):
        return self.wer_sum / self.n_wer if self.n_wer else None


@dataclass
class AlignResult:
    matched: list
    missed: list
    spurious: list

    @property
    def precision(self) -> float:
        t = len(self.matched) + len(self.spurious)
        return len(self.matched) / t if t else 0.0

    @property
    def recall(self) -> float:
        t = len(self.matched) + len(self.missed)
        return len(self.matched) / t if t else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2*p*r/(p+r) if (p+r) else 0.0


def align_multipass(g_list: list, p_list: list, key_fns: list) -> AlignResult:
    matched, g_remaining, p_remaining = [], list(g_list), list(p_list)
    for key_fn in key_fns:
        if not g_remaining or not p_remaining:
            break
        p_index: dict = {}
        for p in p_remaining:
            p_index.setdefault(key_fn(p), []).append(p)
        used_ids: set = set()
        new_g = []
        for g in g_remaining:
            cands = [x for x in p_index.get(key_fn(g), []) if id(x) not in used_ids]
            if cands:
                matched.append((g, cands[0]))
                used_ids.add(id(cands[0]))
            else:
                new_g.append(g)
        g_remaining = new_g
        p_remaining = [p for p in p_remaining if id(p) not in used_ids]
    return AlignResult(matched=matched, missed=g_remaining, spurious=p_remaining)


def print_table(stats: dict, title: str = "") -> None:
    if title:
        print(f"\n{'─'*70}\n  {title}\n{'─'*70}")
    print(f"  {'Field':<30} {'CER':>7}  {'WER':>7}  {'N':>5}")
    print("  " + "─"*54)
    for s in stats.values():
        w = f"{s.avg_wer:.4f}" if s.avg_wer is not None else "  —    "
        print(f"  {s.label:<30} {s.avg_cer:7.4f}  {w:>7}  {s.n:5}")
    print()


def print_errors(stats: dict, limit: int = 2) -> None:
    for s in stats.values():
        if s.errors:
            print(f"\n  ตัวอย่างข้อผิดพลาด [{s.label}]:")
            for e in s.errors[:limit]:
                print(f"    {e['key']:<35}  CER={e['cer']:.3f}")
                print(f"      GT  : {e['gt'][:65]}")
                print(f"      Pred: {e['pred'][:65]}")


def stats_to_dict(stats: dict) -> dict:
    return {k: {"label": s.label, "avg_cer": round(s.avg_cer,6),
                "avg_wer": round(s.avg_wer,6) if s.avg_wer is not None else None,
                "n": s.n} for k,s in stats.items()}


def save_csv(stats: dict, path: str, extra: dict | None = None) -> None:
    rows = []
    for k, s in stats.items():
        row = {"field_key": k, "field_label": s.label,
               "avg_cer": round(s.avg_cer,6),
               "avg_wer": round(s.avg_wer,6) if s.avg_wer is not None else "",
               "n": s.n}
        if extra:
            row.update(extra)
        rows.append(row)
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
