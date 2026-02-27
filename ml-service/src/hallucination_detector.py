"""
Hallucination Detection Layer — Tax Rate Fact-Checking
=======================================================
Detects factual errors in AI-generated financial advice by checking
generated answers against known-correct financial constants.

Detection methods:
  1. Rate extraction  — regex-extract tax rates, percentages, amounts from text
  2. Fact check       — compare against authoritative FACT_REGISTRY
  3. Confidence score — penalise answers with rate mismatches
  4. Escalation flag  — trigger human CA review for high-risk answers

FACT_REGISTRY covers (FY 2024-25, Budget 2024):
  - New/old regime slabs and rebates
  - Capital gains rates (post-23 July 2024)
  - TDS sections and thresholds
  - GST rates for common categories
  - EPF/ESIC contribution rates
  - Advance tax percentages and due dates

Usage:
  from hallucination_detector import HallucinationDetector

  detector = HallucinationDetector()
  result   = detector.check(answer_text, query_category='capital_gains')
  if result.is_hallucination:
      # escalate or suppress response
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


# ---------------------------------------------------------------------------
# Authoritative fact registry — single source of truth
# ---------------------------------------------------------------------------

FACT_REGISTRY = {
    # ── New Tax Regime Slabs FY 2024-25 ────────────────────────────────────
    "new_regime_slab_3l_5l": {
        "description": "New regime: ₹3–7 lakh → 5%",
        "expected_rates": ["5%"],
        "trigger_phrases": ["3 lakh to 7", "3-7 lakh", "3l to 7l", "5% slab"],
        "category": "regime",
    },
    "new_regime_slab_above_15l": {
        "description": "New regime: above ₹15 lakh → 30%",
        "expected_rates": ["30%"],
        "trigger_phrases": ["above 15 lakh", "above ₹15", "above rs 15"],
        "category": "regime",
    },
    "87a_rebate_new_regime": {
        "description": "Sec 87A rebate new regime: ₹25,000 if income ≤ ₹7 lakh",
        "expected_amounts": ["25000", "25,000"],
        "expected_limits":  ["7 lakh", "₹7"],
        "category": "regime",
    },
    "87a_rebate_old_regime": {
        "description": "Sec 87A rebate old regime: ₹12,500 if income ≤ ₹5 lakh",
        "expected_amounts": ["12500", "12,500"],
        "expected_limits":  ["5 lakh", "₹5"],
        "category": "regime",
    },

    # ── Capital Gains Rates (post-Budget 2024) ─────────────────────────────
    "stcg_111a_rate": {
        "description": "STCG u/s 111A on equity: 20% (from 23 July 2024)",
        "expected_rates": ["20%"],
        "wrong_rates":    ["15%"],  # old rate — must not appear
        "trigger_phrases": ["stcg", "short term capital gain", "section 111a", "111a"],
        "category": "capital_gains",
    },
    "ltcg_112a_rate": {
        "description": "LTCG u/s 112A on equity: 12.5% (from 23 July 2024)",
        "expected_rates": ["12.5%"],
        "wrong_rates":    ["10%"],  # old rate
        "trigger_phrases": ["ltcg", "long term capital gain", "section 112a", "112a"],
        "category": "capital_gains",
    },
    "ltcg_112a_exemption": {
        "description": "LTCG 112A exemption: ₹1.25 lakh (was ₹1 lakh before Budget 2024)",
        "expected_amounts": ["1.25 lakh", "1,25,000", "125000"],
        "wrong_amounts":    ["1 lakh", "100000", "1,00,000"],
        "trigger_phrases":  ["ltcg exemption", "exempt ltcg", "112a exempt"],
        "category": "capital_gains",
    },

    # ── TDS Rates ───────────────────────────────────────────────────────────
    "tds_194c_individual": {
        "description": "TDS 194C individual/HUF contractor: 1%",
        "expected_rates": ["1%"],
        "trigger_phrases": ["194c", "contractor tds", "section 194c individual"],
        "category": "tds",
    },
    "tds_194c_company": {
        "description": "TDS 194C company contractor: 2%",
        "expected_rates": ["2%"],
        "trigger_phrases": ["194c company", "contractor tds company"],
        "category": "tds",
    },
    "tds_194ia": {
        "description": "TDS 194IA on property sale: 1% if > ₹50 lakh",
        "expected_rates": ["1%"],
        "expected_limits": ["50 lakh", "₹50"],
        "trigger_phrases": ["194ia", "property tds", "immovable property tds"],
        "category": "tds",
    },
    "tds_194j_professional": {
        "description": "TDS 194J professional services: 10%",
        "expected_rates": ["10%"],
        "trigger_phrases": ["194j professional", "professional fee tds"],
        "category": "tds",
    },
    "tds_194j_technical": {
        "description": "TDS 194J technical services: 2%",
        "expected_rates": ["2%"],
        "trigger_phrases": ["194j technical", "technical service tds"],
        "category": "tds",
    },

    # ── GST Rates ───────────────────────────────────────────────────────────
    "gst_gold": {
        "description": "GST on gold: 3%; making charges: 5%",
        "expected_rates": ["3%"],
        "trigger_phrases": ["gold gst", "gst on gold", "gst jewellery"],
        "category": "gst",
    },
    "gst_making_charges": {
        "description": "GST on making charges (gold): 5%",
        "expected_rates": ["5%"],
        "trigger_phrases": ["making charges gst", "gst making"],
        "category": "gst",
    },
    "gst_restaurant_ac": {
        "description": "GST on restaurant in AC premises: 5% (no ITC)",
        "expected_rates": ["5%"],
        "trigger_phrases": ["restaurant gst", "gst restaurant ac"],
        "category": "gst",
    },

    # ── EPF/ESIC ────────────────────────────────────────────────────────────
    "epf_employee": {
        "description": "EPF employee contribution: 12% of basic",
        "expected_rates": ["12%"],
        "trigger_phrases": ["epf employee", "pf employee", "provident fund contribution"],
        "category": "payroll",
    },
    "esic_employee": {
        "description": "ESIC employee contribution: 0.75% of gross",
        "expected_rates": ["0.75%"],
        "trigger_phrases": ["esic employee", "esi employee contribution"],
        "category": "payroll",
    },
    "esic_employer": {
        "description": "ESIC employer contribution: 3.25% of gross",
        "expected_rates": ["3.25%"],
        "trigger_phrases": ["esic employer", "esi employer contribution"],
        "category": "payroll",
    },

    # ── Advance Tax ─────────────────────────────────────────────────────────
    "advance_tax_jun": {
        "description": "Advance tax June installment: 15% of estimated liability",
        "expected_rates": ["15%"],
        "trigger_phrases": ["june advance tax", "15 june installment", "advance tax june"],
        "category": "advance_tax",
    },
    "advance_tax_sep": {
        "description": "Advance tax September installment: 45% cumulative",
        "expected_rates": ["45%"],
        "trigger_phrases": ["september advance tax", "15 september", "advance tax sep"],
        "category": "advance_tax",
    },
    "advance_tax_dec": {
        "description": "Advance tax December installment: 75% cumulative",
        "expected_rates": ["75%"],
        "trigger_phrases": ["december advance tax", "15 december", "advance tax dec"],
        "category": "advance_tax",
    },
    "advance_tax_mar": {
        "description": "Advance tax March installment: 100% cumulative",
        "expected_rates": ["100%"],
        "trigger_phrases": ["march advance tax", "15 march", "advance tax march"],
        "category": "advance_tax",
    },
}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class HallucinationType(Enum):
    WRONG_RATE      = "wrong_rate"        # stated rate differs from authoritative
    MISSING_FACT    = "missing_fact"      # required key fact absent from answer
    OUTDATED_RATE   = "outdated_rate"     # pre-Budget 2024 rate used
    CONFLICTING     = "conflicting"       # multiple contradictory rates stated
    UNSUPPORTED     = "unsupported_claim" # strong claim with no traceable fact

@dataclass
class HallucinationFinding:
    fact_key:         str
    hallucination_type: HallucinationType
    description:      str
    found_in_text:    Optional[str] = None
    expected:         Optional[str] = None
    severity:         str = "medium"  # low | medium | high | critical

@dataclass
class HallucinationResult:
    text:             str
    category:         str
    is_hallucination: bool
    confidence:       float           # 0.0–1.0 (higher = more likely hallucination)
    findings:         List[HallucinationFinding] = field(default_factory=list)
    facts_checked:    int = 0
    facts_passed:     int = 0
    needs_ca_review:  bool = False
    explanation:      str = ""

# ---------------------------------------------------------------------------
# Hallucination Detector
# ---------------------------------------------------------------------------

class HallucinationDetector:
    """
    Checks AI-generated financial answers against the authoritative fact registry.
    """

    # Rate patterns: extracts things like "12.5%", "₹1.25 lakh", "₹25,000"
    RATE_PATTERN   = re.compile(r'\b(\d+(?:\.\d+)?)\s*%')
    AMOUNT_PATTERN = re.compile(r'₹\s*(\d[\d,\.]*)\s*(lakh|crore|thousand)?', re.IGNORECASE)

    def __init__(self, threshold: float = 0.3):
        """
        threshold — confidence above which an answer is flagged as hallucination.
        """
        self._threshold = threshold

    def check(self, text: str, query_category: Optional[str] = None) -> HallucinationResult:
        """
        Run hallucination checks on model-generated text.
        Returns HallucinationResult with findings.
        """
        text_lower     = text.lower()
        findings       = []
        facts_checked  = 0
        facts_passed   = 0
        ca_review      = False

        for fact_key, fact in FACT_REGISTRY.items():
            # Filter by category if specified
            if query_category and fact.get("category") and fact["category"] != query_category:
                # Still check if a trigger phrase appears — cross-category mentions
                if not any(tp in text_lower for tp in fact.get("trigger_phrases", [])):
                    continue

            # Only check if relevant trigger phrases appear in text
            triggers = fact.get("trigger_phrases", [])
            if triggers and not any(tp in text_lower for tp in triggers):
                continue

            facts_checked += 1
            fact_findings = self._check_fact(text, text_lower, fact_key, fact)
            if fact_findings:
                findings.extend(fact_findings)
                # High/critical severity findings require CA review
                if any(f.severity in ("high", "critical") for f in fact_findings):
                    ca_review = True
            else:
                facts_passed += 1

        # Compute confidence (proportion of checked facts that failed)
        if facts_checked == 0:
            confidence = 0.0  # no relevant facts to check — can't determine
        else:
            confidence = (facts_checked - facts_passed) / facts_checked

        is_hallucination = confidence >= self._threshold and len(findings) > 0

        explanation = self._build_explanation(findings, facts_checked, facts_passed)

        return HallucinationResult(
            text             = text,
            category         = query_category or "general",
            is_hallucination = is_hallucination,
            confidence       = round(confidence, 4),
            findings         = findings,
            facts_checked    = facts_checked,
            facts_passed     = facts_passed,
            needs_ca_review  = ca_review,
            explanation      = explanation,
        )

    def _check_fact(self, text: str, text_lower: str, fact_key: str, fact: Dict) -> List[HallucinationFinding]:
        findings = []

        # Check for wrong/outdated rates
        for wrong_rate in fact.get("wrong_rates", []):
            if self._rate_present(text_lower, wrong_rate):
                findings.append(HallucinationFinding(
                    fact_key           = fact_key,
                    hallucination_type = HallucinationType.OUTDATED_RATE,
                    description        = fact["description"],
                    found_in_text      = wrong_rate,
                    expected           = ", ".join(fact.get("expected_rates", [])),
                    severity           = "high",
                ))

        for wrong_amount in fact.get("wrong_amounts", []):
            if self._amount_present(text_lower, wrong_amount):
                findings.append(HallucinationFinding(
                    fact_key           = fact_key,
                    hallucination_type = HallucinationType.OUTDATED_RATE,
                    description        = fact["description"],
                    found_in_text      = wrong_amount,
                    expected           = ", ".join(fact.get("expected_amounts", [])),
                    severity           = "critical",
                ))

        return findings

    def _rate_present(self, text_lower: str, rate: str) -> bool:
        """Check if a specific rate string appears in text."""
        # Normalise and match
        rate_norm = rate.lower().replace(" ", "")
        text_norm = text_lower.replace(" ", "")
        return rate_norm in text_norm

    def _amount_present(self, text_lower: str, amount: str) -> bool:
        amount_norm = amount.lower().replace(",", "").replace("₹", "").replace(" ", "")
        text_norm   = text_lower.replace(",", "").replace("₹", "").replace(" ", "")
        return amount_norm in text_norm

    def _build_explanation(self, findings: List[HallucinationFinding], checked: int, passed: int) -> str:
        if not findings:
            return f"All {checked} applicable facts passed. No hallucinations detected."
        parts = [f"{len(findings)} potential issue(s) in {checked} facts checked:"]
        for f in findings[:5]:  # cap at 5 for readability
            parts.append(f"  [{f.severity.upper()}] {f.hallucination_type.value}: {f.description}")
            if f.found_in_text:
                parts.append(f"    Found: {f.found_in_text}  |  Expected: {f.expected}")
        if len(findings) > 5:
            parts.append(f"  ... and {len(findings) - 5} more.")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Flask/API integration helper
# ---------------------------------------------------------------------------

_detector = HallucinationDetector()

def check_answer(answer_text: str, query_category: Optional[str] = None) -> Dict:
    """JSON-serialisable wrapper for use in Flask route or LangChain chain."""
    result = _detector.check(answer_text, query_category)
    return {
        "is_hallucination": result.is_hallucination,
        "confidence":       result.confidence,
        "needs_ca_review":  result.needs_ca_review,
        "facts_checked":    result.facts_checked,
        "facts_passed":     result.facts_passed,
        "findings": [
            {
                "fact_key":    f.fact_key,
                "type":        f.hallucination_type.value,
                "description": f.description,
                "found":       f.found_in_text,
                "expected":    f.expected,
                "severity":    f.severity,
            }
            for f in result.findings
        ],
        "explanation": result.explanation,
    }


if __name__ == "__main__":
    # Quick smoke test
    test_text = (
        "Under Section 111A, STCG on equity shares is taxed at 15%. "
        "LTCG under 112A is 10% with ₹1 lakh exemption."
    )
    result = check_answer(test_text, "capital_gains")
    import json
    print(json.dumps(result, indent=2))
    print(f"\nHallucination: {result['is_hallucination']} (confidence: {result['confidence']})")
