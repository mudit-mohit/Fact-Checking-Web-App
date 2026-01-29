import json
from typing import List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import os


@dataclass
class ReportClaim:
    """Standardized claim for reporting"""
    claim_text: str
    claim_type: str
    context: str
    page_number: int
    verdict: str              # 'verified', 'inaccurate', 'false'
    confidence_score: float
    explanation: str
    evidence_summary: str
    sources_count: int
    recommendation: str


class FactCheckReporter:
    """Generate fact-check reports (text + JSON only)"""
    
    VERDICT_MAPPING = {
        'verified': {
            'label': 'Verified',
            'icon': '✅',
            'color': 'green',
            'description': 'Claim is supported by evidence'
        },
        'inaccurate': {
            'label': 'Inaccurate',
            'icon': '⚠️',
            'color': 'orange',
            'description': 'Claim is misleading, partial, or outdated'
        },
        'false': {
            'label': 'False',
            'icon': '❌',
            'color': 'red',
            'description': 'Claim is contradicted or has no supporting evidence'
        }
    }
    
    def __init__(self, verification_results_path: str):
        self.results_path = verification_results_path
        self.verification_data = self._load_verification_data()
        self.report_claims: List[ReportClaim] = []
    
    def _load_verification_data(self) -> Dict:
        """Load verification results from JSON"""
        try:
            with open(self.results_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Verification file not found: {self.results_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in verification file: {self.results_path}")
    
    def _map_to_verdict(self, status: str, confidence: float) -> str:
        """
        Map raw verification status to final verdict
        More conservative mapping to match your app's display
        """
        status = status.lower()
        
        if status == 'verified':
            return 'verified'
        
        if status in ['contradicted', 'false']:
            return 'false' if confidence >= 0.65 else 'inaccurate'
        
        if status == 'partial':
            return 'inaccurate'
        
        # unverifiable / unknown / error cases
        return 'false' if confidence < 0.3 else 'inaccurate'
    
    def _generate_recommendation(self, verdict: str) -> str:
        recs = {
            'verified': 'No changes needed – claim is accurate.',
            'inaccurate': 'UPDATE or CLARIFY: Add context or correct the statement.',
            'false': 'REMOVE or STRONGLY CORRECT: Claim is not supported by evidence.'
        }
        return recs.get(verdict, 'Review manually.')
    
    def _summarize_evidence(self, evidence: List[Dict]) -> str:
        if not evidence:
            return "No relevant evidence found."
        
        lines = []
        for e in evidence[:3]:
            src = e.get('source', 'Unknown')
            snip = e.get('snippet', '').strip()[:120]
            lines.append(f"• {src}: {snip}...")
        return "\n".join(lines) or "Evidence summary not available."
    
    def process_verification_results(self) -> List[ReportClaim]:
        """Convert raw verification data to standardized report claims"""
        detailed = self.verification_data.get('detailed_results', [])
        
        for item in detailed:
            verdict = self._map_to_verdict(
                item.get('verification_status', 'unverifiable'),
                item.get('confidence_score', 0.0)
            )
            
            claim = ReportClaim(
                claim_text=item.get('claim_text', 'N/A'),
                claim_type=item.get('claim_type', 'Unknown'),
                context=item.get('claim_context', ''),
                page_number=item.get('page_number', -1),
                verdict=verdict,
                confidence_score=item.get('confidence_score', 0.0),
                explanation=item.get('analysis', 'No analysis available.'),
                evidence_summary=self._summarize_evidence(item.get('evidence', [])),
                sources_count=len(item.get('evidence', [])),
                recommendation=self._generate_recommendation(verdict)
            )
            self.report_claims.append(claim)
        
        return self.report_claims
    
    def generate_executive_summary(self) -> Dict[str, Any]:
        """Create summary metrics for display in app"""
        total = len(self.report_claims)
        if total == 0:
            return {
                'total_claims': 0,
                'verified': 0,
                'inaccurate': 0,
                'false': 0,
                'accuracy_rate': 0.0,
                'document_quality': 'UNKNOWN - No claims processed',
                'issues_requiring_action': 0,
                'high_priority_issues': []
            }
        
        counts = {'verified': 0, 'inaccurate': 0, 'false': 0}
        high_priority = []
        
        for c in self.report_claims:
            counts[c.verdict] += 1
            if c.verdict in ['inaccurate', 'false'] and c.confidence_score >= 0.65:
                high_priority.append({
                    'claim': c.claim_text,
                    'verdict': c.verdict,
                    'page': c.page_number,
                    'confidence': round(c.confidence_score, 2)
                })
        
        accuracy = (counts['verified'] / total) * 100
        
        return {
            'total_claims': total,
            'verified': counts['verified'],
            'inaccurate': counts['inaccurate'],
            'false': counts['false'],
            'accuracy_rate': round(accuracy, 1),
            'document_quality': self._assess_quality(accuracy),
            'issues_requiring_action': counts['inaccurate'] + counts['false'],
            'high_priority_issues': high_priority,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _assess_quality(self, accuracy: float) -> str:
        if accuracy >= 90: return "EXCELLENT - Minimal corrections needed"
        if accuracy >= 75: return "GOOD - Some corrections recommended"
        if accuracy >= 50: return "FAIR - Multiple corrections required"
        return "POOR - Significant revision needed"
    
    def generate_text_report(self, output_path: str = None) -> str:
        """Generate clean, human-readable text summary"""
        summary = self.generate_executive_summary()
        
        lines = []
        lines.append("═" * 70)
        lines.append("FACT-CHECK SUMMARY")
        lines.append("═" * 70)
        lines.append(f"Generated: {summary['timestamp']}")
        lines.append(f"Total Claims: {summary['total_claims']}")
        lines.append(f"Document Quality: {summary['document_quality']}")
        lines.append(f"Accuracy Rate: {summary['accuracy_rate']}%")
        lines.append("")
        
        lines.append("Verdict Breakdown:")
        lines.append(f"  ✅ Verified   : {summary['verified']} ({summary['verified']/summary['total_claims']*100:.1f}%)")
        lines.append(f"  ⚠️ Inaccurate : {summary['inaccurate']} ({summary['inaccurate']/summary['total_claims']*100:.1f}%)")
        lines.append(f"  ❌ False      : {summary['false']} ({summary['false']/summary['total_claims']*100:.1f}%)")
        lines.append("")
        
        lines.append(f"Issues Requiring Action: {summary['issues_requiring_action']}")
        
        if summary['high_priority_issues']:
            lines.append("\nHigh Priority Issues:")
            for i, issue in enumerate(summary['high_priority_issues'], 1):
                lines.append(f"  {i}. Page {issue['page']} | {issue['verdict'].upper()} | {issue['claim'][:80]}...")
        
        text = "\n".join(lines)
        
        if output_path:
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
        
        return text
    
    def generate_json_report(self, output_path: str = None) -> Dict:
        """Generate clean JSON summary + claims"""
        summary = self.generate_executive_summary()
        
        json_data = {
            'metadata': {
                'generated_at': summary['timestamp'],
                'total_claims': summary['total_claims']
            },
            'summary': {
                'document_quality': summary['document_quality'],
                'accuracy_rate_percent': summary['accuracy_rate'],
                'verified': summary['verified'],
                'inaccurate': summary['inaccurate'],
                'false': summary['false'],
                'issues_requiring_action': summary['issues_requiring_action']
            },
            'high_priority_issues': summary['high_priority_issues'],
            'claims': [asdict(c) for c in self.report_claims]
        }
        
        if output_path:
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        return json_data


# For manual testing
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python report_generator.py <verification.json> [output_dir]")
        sys.exit(1)
    
    reporter = FactCheckReporter(sys.argv[1])
    reporter.process_verification_results()
    
    summary = reporter.generate_executive_summary()
    print(json.dumps(summary, indent=2))