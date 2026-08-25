"""
Memory Confidence Scorer
Evaluates reliability of stored knowledge before reuse.
"""

from datetime import datetime


class ConfidenceScorer:
    def score(self, item):
        confidence = item.get("confidence", 0.5)
        uses = item.get("uses", 0)
        verified = item.get("verified", False)

        if verified:
            confidence += 0.2
        confidence += min(uses * 0.01, 0.2)

        return min(round(confidence, 3), 1.0)

    def evaluate(self, item):
        return {
            "score": self.score(item),
            "evaluated_at": datetime.utcnow().isoformat(),
            "recommended": self.score(item) >= 0.7,
        }
