import json
from typing import List, Dict, Any, Optional
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
    verdict: str
    confidence_score: float
    explanation: str
    evidence_summary: str
    sources_count: int
    recommendation: str


class FactCheckReporter:
    """Generate comprehensive fact-check reports"""
    
    VERDICT_MAPPING = {
        'verified': {
            'label': 'Verified',
            'icon': '✅',
            'color': 'green',
            'description': 'Claim matches current data and is accurate'
        },
        'inaccurate': {
            'label': 'Inaccurate',
            'icon': '⚠️',
            'color': 'orange',
            'description': 'Claim is outdated, misleading, or partially incorrect'
        },
        'false': {
            'label': 'False',
            'icon': '❌',
            'color': 'red',
            'description': 'No evidence found or claim is demonstrably incorrect'
        }
    }
    
    def __init__(self, verification_results_path: str):
        """Initialize reporter with verification results"""
        self.results_path = verification_results_path
        self.verification_data = self._load_verification_data()
        self.report_claims: List[ReportClaim] = []
        
    def _load_verification_data(self) -> Dict:
        """Load verification results from JSON"""
        with open(self.results_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _map_to_verdict(self, verification_status: str, confidence: float) -> str:
        """
        Map verification status to clear verdict
        
        Rules:
        - verified (high confidence) → Verified
        - contradicted → Inaccurate or False (depends on confidence)
        - partial → Inaccurate
        - unverifiable (low evidence) → False
        """
        if verification_status == 'verified':
            return 'verified'
        
        elif verification_status == 'contradicted':
            # High confidence contradiction = clearly wrong data
            if confidence >= 0.7:
                return 'inaccurate'
            else:
                return 'false'
        
        elif verification_status == 'partial':
            # Partial truths are inaccurate/misleading
            return 'inaccurate'
        
        elif verification_status == 'unverifiable':
            # Can't find evidence = treat as false
            return 'false'
        
        else:
            return 'false'
    
    def _generate_recommendation(self, verdict: str, claim_text: str) -> str:
        """Generate actionable recommendation based on verdict"""
        recommendations = {
            'verified': 'No action needed. Claim is accurate.',
            'inaccurate': f'UPDATE: Review and correct this claim. Provide current data or add context.',
            'false': f'REMOVE or VERIFY: This claim lacks evidence. Remove or find supporting sources.'
        }
        return recommendations.get(verdict, 'Review this claim manually.')
    
    def _summarize_evidence(self, evidence_list: List[Dict]) -> str:
        """Create a concise evidence summary"""
        if not evidence_list:
            return "No evidence found in web search."
        
        summaries = []
        for ev in evidence_list[:3]: 
            source = ev.get('source', 'Unknown source')
            snippet = ev.get('snippet', '')[:100]
            summaries.append(f"• {source}: {snippet}...")
        
        return "\n".join(summaries)
    
    def process_verification_results(self) -> List[ReportClaim]:
        """Process verification results into standardized report claims"""
        detailed_results = self.verification_data.get('detailed_results', [])
        
        for result in detailed_results:
            verdict = self._map_to_verdict(
                result['verification_status'],
                result['confidence_score']
            )
            
            report_claim = ReportClaim(
                claim_text=result['claim_text'],
                claim_type=result['claim_type'],
                context=result['claim_context'],
                page_number=result['page_number'],
                verdict=verdict,
                confidence_score=result['confidence_score'],
                explanation=result['analysis'],
                evidence_summary=self._summarize_evidence(result['evidence']),
                sources_count=len(result['evidence']),
                recommendation=self._generate_recommendation(verdict, result['claim_text'])
            )
            
            self.report_claims.append(report_claim)
        
        return self.report_claims
    
    def generate_executive_summary(self) -> Dict[str, Any]:
        """Generate executive summary with key metrics"""
        total = len(self.report_claims)
        if total == 0:
            return {'error': 'No claims to report'}
        
        verdict_counts = {
            'verified': 0,
            'inaccurate': 0,
            'false': 0
        }
        
        high_priority_issues = []
        
        for claim in self.report_claims:
            verdict_counts[claim.verdict] += 1
            
            # Flag high-priority issues 
            if claim.verdict in ['inaccurate', 'false'] and claim.confidence_score >= 0.7:
                high_priority_issues.append({
                    'claim': claim.claim_text,
                    'verdict': claim.verdict,
                    'page': claim.page_number,
                    'confidence': claim.confidence_score
                })
        
        accuracy_rate = (verdict_counts['verified'] / total * 100) if total > 0 else 0
        
        return {
            'total_claims': total,
            'verified': verdict_counts['verified'],
            'inaccurate': verdict_counts['inaccurate'],
            'false': verdict_counts['false'],
            'accuracy_rate': round(accuracy_rate, 2),
            'document_quality': self._assess_document_quality(accuracy_rate),
            'high_priority_issues': high_priority_issues,
            'issues_requiring_action': verdict_counts['inaccurate'] + verdict_counts['false'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _assess_document_quality(self, accuracy_rate: float) -> str:
        """Assess overall document quality"""
        if accuracy_rate >= 90:
            return "EXCELLENT - Minimal corrections needed"
        elif accuracy_rate >= 75:
            return "GOOD - Some corrections recommended"
        elif accuracy_rate >= 50:
            return "FAIR - Multiple corrections required"
        else:
            return "POOR - Significant revision needed"
    
    def generate_text_report(self, output_path: str):
        """Generate human-readable text report"""
        summary = self.generate_executive_summary()
        
        report_lines = []
        report_lines.append("="*80)
        report_lines.append("FACT-CHECK REPORT")
        report_lines.append("="*80)
        report_lines.append("")
        report_lines.append(f"Generated: {summary['timestamp']}")
        report_lines.append(f"Total Claims Analyzed: {summary['total_claims']}")
        report_lines.append("")
        
        # Executive Summary
        report_lines.append("="*80)
        report_lines.append("EXECUTIVE SUMMARY")
        report_lines.append("="*80)
        report_lines.append("")
        report_lines.append(f"Document Quality: {summary['document_quality']}")
        report_lines.append(f"Accuracy Rate: {summary['accuracy_rate']}%")
        report_lines.append(f"Issues Requiring Action: {summary['issues_requiring_action']}")
        report_lines.append("")
        
        # Verdict Breakdown
        report_lines.append("Verdict Breakdown:")
        report_lines.append(f"  ✅ Verified: {summary['verified']} ({summary['verified']/summary['total_claims']*100:.1f}%)")
        report_lines.append(f"  ⚠️  Inaccurate: {summary['inaccurate']} ({summary['inaccurate']/summary['total_claims']*100:.1f}%)")
        report_lines.append(f"  ❌ False: {summary['false']} ({summary['false']/summary['total_claims']*100:.1f}%)")
        report_lines.append("")
        
        # High Priority Issues
        if summary['high_priority_issues']:
            report_lines.append("="*80)
            report_lines.append(f"HIGH PRIORITY ISSUES ({len(summary['high_priority_issues'])})")
            report_lines.append("="*80)
            report_lines.append("")
            
            for idx, issue in enumerate(summary['high_priority_issues'], 1):
                icon = self.VERDICT_MAPPING[issue['verdict']]['icon']
                report_lines.append(f"{idx}. {icon} [{issue['verdict'].upper()}] {issue['claim']}")
                report_lines.append(f"   Page: {issue['page']} | Confidence: {issue['confidence']:.2f}")
                report_lines.append("")
        
        # Detailed Findings by Verdict
        for verdict_key in ['false', 'inaccurate', 'verified']:
            claims_by_verdict = [c for c in self.report_claims if c.verdict == verdict_key]
            
            if claims_by_verdict:
                verdict_info = self.VERDICT_MAPPING[verdict_key]
                report_lines.append("")
                report_lines.append("="*80)
                report_lines.append(f"{verdict_info['icon']} {verdict_info['label'].upper()} CLAIMS ({len(claims_by_verdict)})")
                report_lines.append("="*80)
                report_lines.append("")
                
                for idx, claim in enumerate(claims_by_verdict, 1):
                    report_lines.append(f"{idx}. {claim.claim_text}")
                    report_lines.append(f"   Type: {claim.claim_type} | Page: {claim.page_number}")
                    report_lines.append(f"   Context: {claim.context[:100]}...")
                    report_lines.append(f"   Confidence: {claim.confidence_score:.2f}")
                    report_lines.append(f"   Explanation: {claim.explanation[:200]}...")
                    report_lines.append(f"   Sources: {claim.sources_count}")
                    report_lines.append(f"   → {claim.recommendation}")
                    report_lines.append("")
        
        # Action Items
        report_lines.append("")
        report_lines.append("="*80)
        report_lines.append("RECOMMENDED ACTIONS")
        report_lines.append("="*80)
        report_lines.append("")
        
        action_count = 1
        for claim in self.report_claims:
            if claim.verdict in ['false', 'inaccurate']:
                report_lines.append(f"{action_count}. Page {claim.page_number}: {claim.claim_text}")
                report_lines.append(f"   Action: {claim.recommendation}")
                report_lines.append("")
                action_count += 1
        
        if action_count == 1:
            report_lines.append("No actions required - all claims verified!")
        
        report_lines.append("")
        report_lines.append("="*80)
        report_lines.append("END OF REPORT")
        report_lines.append("="*80)
        
        # Write to file
        report_text = "\n".join(report_lines)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        return report_text
    
    def generate_json_report(self, output_path: str):
        """Generate structured JSON report"""
        summary = self.generate_executive_summary()
        
        json_report = {
            'metadata': {
                'report_type': 'fact_check_report',
                'generated_at': summary['timestamp'],
                'version': '1.0'
            },
            'executive_summary': summary,
            'claims_by_verdict': {
                'verified': [asdict(c) for c in self.report_claims if c.verdict == 'verified'],
                'inaccurate': [asdict(c) for c in self.report_claims if c.verdict == 'inaccurate'],
                'false': [asdict(c) for c in self.report_claims if c.verdict == 'false']
            },
            'all_claims': [asdict(c) for c in self.report_claims]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        
        return json_report
    
    def generate_html_report(self, output_path: str):
        """Generate interactive HTML report"""
        summary = self.generate_executive_summary()
        
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fact-Check Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }}
        
        h2 {{
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
            padding-left: 10px;
            border-left: 4px solid #3498db;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .metric-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 2px solid #e9ecef;
        }}
        
        .metric-value {{
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }}
        
        .metric-label {{
            color: #6c757d;
            font-size: 14px;
            text-transform: uppercase;
        }}
        
        .verdict-verified {{ color: #27ae60; }}
        .verdict-inaccurate {{ color: #f39c12; }}
        .verdict-false {{ color: #e74c3c; }}
        
        .quality-excellent {{ background: #d4edda; color: #155724; }}
        .quality-good {{ background: #d1ecf1; color: #0c5460; }}
        .quality-fair {{ background: #fff3cd; color: #856404; }}
        .quality-poor {{ background: #f8d7da; color: #721c24; }}
        
        .claim-card {{
            background: #f8f9fa;
            border-left: 4px solid #dee2e6;
            padding: 20px;
            margin: 15px 0;
            border-radius: 4px;
        }}
        
        .claim-card.verified {{
            border-left-color: #27ae60;
            background: #f0f9f4;
        }}
        
        .claim-card.inaccurate {{
            border-left-color: #f39c12;
            background: #fef9f0;
        }}
        
        .claim-card.false {{
            border-left-color: #e74c3c;
            background: #fef5f5;
        }}
        
        .claim-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        
        .claim-text {{
            font-size: 18px;
            font-weight: 600;
            color: #2c3e50;
        }}
        
        .verdict-badge {{
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        
        .badge-verified {{
            background: #27ae60;
            color: white;
        }}
        
        .badge-inaccurate {{
            background: #f39c12;
            color: white;
        }}
        
        .badge-false {{
            background: #e74c3c;
            color: white;
        }}
        
        .claim-meta {{
            color: #6c757d;
            font-size: 14px;
            margin: 10px 0;
        }}
        
        .claim-context {{
            background: white;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
            font-style: italic;
            color: #555;
        }}
        
        .recommendation {{
            background: #e7f3ff;
            border-left: 3px solid #3498db;
            padding: 10px;
            margin-top: 10px;
            font-weight: 500;
        }}
        
        .filter-buttons {{
            margin: 20px 0;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        
        .filter-btn {{
            padding: 10px 20px;
            border: 2px solid #3498db;
            background: white;
            color: #3498db;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }}
        
        .filter-btn:hover {{
            background: #3498db;
            color: white;
        }}
        
        .filter-btn.active {{
            background: #3498db;
            color: white;
        }}
        
        .confidence-bar {{
            background: #e9ecef;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin: 10px 0;
        }}
        
        .confidence-fill {{
            height: 100%;
            background: linear-gradient(to right, #e74c3c, #f39c12, #27ae60);
            transition: width 0.3s;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 Fact-Check Report</h1>
        <p style="color: #6c757d; margin-bottom: 30px;">Generated: {summary['timestamp']}</p>
        
        <div class="summary-grid">
            <div class="metric-card quality-{summary['document_quality'].split(' - ')[0].lower()}">
                <div class="metric-label">Document Quality</div>
                <div class="metric-value" style="font-size: 20px;">{summary['document_quality']}</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Total Claims</div>
                <div class="metric-value">{summary['total_claims']}</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Accuracy Rate</div>
                <div class="metric-value verdict-verified">{summary['accuracy_rate']}%</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Verified</div>
                <div class="metric-value verdict-verified">{summary['verified']}</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Inaccurate</div>
                <div class="metric-value verdict-inaccurate">{summary['inaccurate']}</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">False</div>
                <div class="metric-value verdict-false">{summary['false']}</div>
            </div>
        </div>
        
        <h2>Filter Claims</h2>
        <div class="filter-buttons">
            <button class="filter-btn active" onclick="filterClaims('all')">All Claims</button>
            <button class="filter-btn" onclick="filterClaims('verified')">✅ Verified</button>
            <button class="filter-btn" onclick="filterClaims('inaccurate')">⚠️ Inaccurate</button>
            <button class="filter-btn" onclick="filterClaims('false')">❌ False</button>
        </div>
        
        <h2>Detailed Findings</h2>
        <div id="claims-container">
"""
        
        # Add claim cards
        for claim in self.report_claims:
            verdict_info = self.VERDICT_MAPPING[claim.verdict]
            confidence_pct = int(claim.confidence_score * 100)
            
            html_template += f"""
            <div class="claim-card {claim.verdict}" data-verdict="{claim.verdict}">
                <div class="claim-header">
                    <div class="claim-text">{verdict_info['icon']} {claim.claim_text}</div>
                    <span class="verdict-badge badge-{claim.verdict}">{verdict_info['label']}</span>
                </div>
                
                <div class="claim-meta">
                    <strong>Type:</strong> {claim.claim_type} | 
                    <strong>Page:</strong> {claim.page_number} | 
                    <strong>Sources:</strong> {claim.sources_count}
                </div>
                
                <div class="claim-context">
                    "{claim.context[:150]}..."
                </div>
                
                <div style="margin: 10px 0;">
                    <small style="color: #6c757d;">Confidence: {confidence_pct}%</small>
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: {confidence_pct}%;"></div>
                    </div>
                </div>
                
                <div style="margin: 10px 0;">
                    <strong>Explanation:</strong> {claim.explanation[:200]}...
                </div>
                
                <div class="recommendation">
                    <strong>→</strong> {claim.recommendation}
                </div>
            </div>
"""
        
        html_template += """
        </div>
    </div>
    
    <script>
        function filterClaims(verdict) {
            const cards = document.querySelectorAll('.claim-card');
            const buttons = document.querySelectorAll('.filter-btn');
            
            // Update button states
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            // Filter cards
            cards.forEach(card => {
                if (verdict === 'all' || card.dataset.verdict === verdict) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }
    </script>
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_template)
        
        return html_template
    
    def print_summary(self):
        """Print console summary"""
        summary = self.generate_executive_summary()
        
        print("\n" + "="*80)
        print("FACT-CHECK REPORT SUMMARY")
        print("="*80 + "\n")
        
        print(f"Document Quality: {summary['document_quality']}")
        print(f"Accuracy Rate: {summary['accuracy_rate']}%")
        print(f"Total Claims: {summary['total_claims']}")
        print(f"Issues Requiring Action: {summary['issues_requiring_action']}\n")
        
        print("Verdict Breakdown:")
        print(f"  ✅ Verified: {summary['verified']} ({summary['verified']/summary['total_claims']*100:.1f}%)")
        print(f"  ⚠️  Inaccurate: {summary['inaccurate']} ({summary['inaccurate']/summary['total_claims']*100:.1f}%)")
        print(f"  ❌ False: {summary['false']} ({summary['false']/summary['total_claims']*100:.1f}%)\n")
        
        if summary['high_priority_issues']:
            print(f"⚠️  HIGH PRIORITY: {len(summary['high_priority_issues'])} issues require immediate attention")


# Main execution
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python report_generator.py <verification_results.json> [output_dir]")
        print("\nGenerates comprehensive reports in multiple formats:")
        print("  - Text report (human-readable)")
        print("  - JSON report (machine-readable)")
        print("  - HTML report (interactive)")
        print("\nExample: python report_generator.py verification_results.json reports/")
        sys.exit(1)
    
    results_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "fact_check_reports"
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Loading verification results from: {results_file}")
    
    try:
        reporter = FactCheckReporter(results_file)
        reporter.process_verification_results()
        
        # Print console summary
        reporter.print_summary()
        
        # Generate all report formats
        print(f"\nGenerating reports in: {output_dir}/")
        
        text_report = os.path.join(output_dir, "fact_check_report.txt")
        json_report = os.path.join(output_dir, "fact_check_report.json")
        html_report = os.path.join(output_dir, "fact_check_report.html")
        
        reporter.generate_text_report(text_report)
        print(f"  ✓ Text report: {text_report}")
        
        reporter.generate_json_report(json_report)
        print(f"  ✓ JSON report: {json_report}")
        
        reporter.generate_html_report(html_report)
        print(f"  ✓ HTML report: {html_report}")
        
        print("\n✅ All reports generated successfully!")
        print(f"\nOpen the HTML report in your browser:")
        print(f"  file://{os.path.abspath(html_report)}")
        
    except FileNotFoundError:
        print(f"ERROR: File '{results_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)