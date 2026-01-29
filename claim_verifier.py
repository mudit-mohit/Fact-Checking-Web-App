import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from langchain_ollama import ChatOllama
from search_providers import TavilySearch, SearchResult, format_results_for_llm


@dataclass
class VerificationResult:
    """Represents the verification result for a claim"""
    claim_text: str
    claim_type: str
    claim_context: str
    page_number: int
    verification_status: str
    confidence_score: float
    evidence: List[Dict[str, str]]
    analysis: str
    search_queries_used: List[str]
    search_provider_used: str
    timestamp: str


class EnhancedClaimVerifier:
    """Verify claims using local Ollama LLM + Tavily search"""
    
    def __init__(self, search_provider: Optional[str] = None):
        # Local Ollama LLM
        self.llm = ChatOllama(
            model="mistral:latest",           
            temperature=0.0,
            format="json"                     
        )
        
        self.search = TavilySearch()  
        self.preferred_provider = search_provider
        self.verification_results: List[VerificationResult] = []
        
        self.search.print_status()
    
    def load_claims(self, json_path: str) -> List[Dict[str, Any]]:
        """Load extracted claims from JSON file"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['claims']
    
    def generate_search_queries(self, claim: Dict[str, Any]) -> List[str]:
        """Generate effective search queries for a claim"""
        claim_text = claim['text']
        context = claim['context']
        claim_type = claim['claim_type']
        
        queries = []
        
        # Base query
        queries.append(claim_text)
        
        # Context-enhanced query
        context_words = [w for w in context.split() if len(w) > 4][:5]
        if context_words:
            queries.append(f"{claim_text} {' '.join(context_words)}")
        
        # Type-specific query
        if claim_type == 'financial':
            queries.append(f"{claim_text} financial report SEC filing")
        elif claim_type == 'statistic':
            queries.append(f"{claim_text} statistics data report")
        elif claim_type == 'date':
            queries.append(f"{claim_text} date timeline event")
        
        return queries[:2]  
    
    def search_for_claim(self, claim: Dict[str, Any]) -> tuple[List[SearchResult], List[str]]:
        """Search web for evidence about a claim"""
        queries = self.generate_search_queries(claim)
        all_results = []
        used_queries = []
        
        for query in queries:
            print(f"    Query: {query}")
            results = self.search.search(query, max_results=3)
            
            if results:
                all_results.extend(results)
                used_queries.append(query)
                
                # Stop if we have enough results
                if len(all_results) >= 5:
                    break
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)
        
        return unique_results[:5], used_queries
    
    def verify_with_llm(self, claim: Dict[str, Any], search_results: List[SearchResult]) -> Dict[str, Any]:
        """Use local Ollama to analyze search results and verify claim"""
        
        claim_text = claim['text']
        claim_type = claim['claim_type']
        claim_context = claim['context']
        
        search_context = format_results_for_llm(search_results)
        
        prompt = f"""You are an expert fact-checker. Verify the following claim using the provided search results.

CLAIM TO VERIFY:
Text: {claim_text}
Type: {claim_type}
Context from document: {claim_context}

SEARCH RESULTS:
{search_context}

INSTRUCTIONS:
Based on the search results, determine if the claim is:
- VERIFIED: Strong evidence supports the claim
- CONTRADICTED: Evidence contradicts the claim
- PARTIAL: Claim is partially true or needs context
- UNVERIFIABLE: Insufficient evidence to determine

Provide your analysis in this JSON format:
{{
    "verification_status": "verified|contradicted|partial|unverifiable",
    "confidence_score": 0.0-1.0,
    "evidence": [
        {{
            "source": "source name or URL",
            "snippet": "relevant quote or information",
            "relevance": "how this relates to the claim"
        }}
    ],
    "analysis": "Your detailed analysis explaining the verification result"
}}

Be objective and thorough. Prioritize recent, authoritative sources."""

        try:
            response = self.llm.invoke(prompt)
            response_text = response.content
            
            # Parse JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)
                return result
            else:
                return {
                    "verification_status": "unverifiable",
                    "confidence_score": 0.0,
                    "evidence": [],
                    "analysis": response_text
                }
        
        except Exception as e:
            print(f"LLM verification error: {e}")
            return {
                "verification_status": "unverifiable",
                "confidence_score": 0.0,
                "evidence": [],
                "analysis": f"Error during verification: {str(e)}"
            }
    
    def verify_claim(self, claim: Dict[str, Any]) -> VerificationResult:
        """Verify a single claim using search and LLM analysis"""
        
        claim_text = claim['text']
        
        # Step 1: Search for evidence
        search_results, used_queries = self.search_for_claim(claim)
        
        provider_used = search_results[0].source if search_results else "None"
        
        # Step 2: Analyze with LLM
        if search_results:
            llm_result = self.verify_with_llm(claim, search_results)
        else:
            llm_result = {
                "verification_status": "unverifiable",
                "confidence_score": 0.0,
                "evidence": [],
                "analysis": "No search results found to verify this claim."
            }
        
        # Create verification result
        verification = VerificationResult(
            claim_text=claim_text,
            claim_type=claim['claim_type'],
            claim_context=claim['context'],
            page_number=claim['page_number'],
            verification_status=llm_result['verification_status'],
            confidence_score=llm_result['confidence_score'],
            evidence=llm_result['evidence'],
            analysis=llm_result['analysis'],
            search_queries_used=used_queries,
            search_provider_used=provider_used,
            timestamp=datetime.now().isoformat()
        )
        
        return verification
    
    def verify_all_claims(self, claims: List[Dict[str, Any]], 
                         delay: float = 2.0,
                         max_claims: Optional[int] = None) -> List[VerificationResult]:
        """Verify all claims with rate limiting"""
        
        claims_to_verify = claims[:max_claims] if max_claims else claims
        total = len(claims_to_verify)
        
        print(f"\n{'='*60}")
        print(f"VERIFYING {total} CLAIMS (Local Ollama + Tavily)")
        print(f"{'='*60}\n")
        
        for idx, claim in enumerate(claims_to_verify, 1):
            print(f"[{idx}/{total}] Verifying: {claim['text'][:50]}...")
            
            try:
                result = self.verify_claim(claim)
                self.verification_results.append(result)
                
                print(f"  Status: {result.verification_status.upper()}")
                print(f"  Confidence: {result.confidence_score:.2f}")
                print(f"  Provider: {result.search_provider_used}\n")
            
            except Exception as e:
                print(f"  Error: {str(e)}\n")
                result = VerificationResult(
                    claim_text=claim['text'],
                    claim_type=claim['claim_type'],
                    claim_context=claim['context'],
                    page_number=claim['page_number'],
                    verification_status='unverifiable',
                    confidence_score=0.0,
                    evidence=[],
                    analysis=f"Error: {str(e)}",
                    search_queries_used=[],
                    search_provider_used='None',
                    timestamp=datetime.now().isoformat()
                )
                self.verification_results.append(result)
            
            # Small delay to avoid overwhelming local Ollama
            if idx < total:
                time.sleep(delay)
        
        return self.verification_results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a summary report of verification results"""
        total_claims = len(self.verification_results)
        
        if total_claims == 0:
            return {"error": "No claims verified yet"}
        
        status_counts = {
            'verified': 0,
            'contradicted': 0,
            'partial': 0,
            'unverifiable': 0
        }
        
        provider_usage = {}
        high_confidence_verified = 0
        flagged_claims = []
        
        for result in self.verification_results:
            status = result.verification_status
            status_counts[status] = status_counts.get(status, 0) + 1
            
            provider = result.search_provider_used
            provider_usage[provider] = provider_usage.get(provider, 0) + 1
            
            if status == 'verified' and result.confidence_score >= 0.8:
                high_confidence_verified += 1
            
            if status in ['contradicted', 'partial'] and result.confidence_score >= 0.6:
                flagged_claims.append({
                    'claim': result.claim_text,
                    'status': status,
                    'page': result.page_number,
                    'confidence': result.confidence_score,
                    'analysis': result.analysis[:200] + '...'
                })
        
        verification_rate = (status_counts['verified'] / total_claims * 100) if total_claims > 0 else 0
        accuracy_score = ((status_counts['verified'] + status_counts['partial'] * 0.5) / total_claims * 100) if total_claims > 0 else 0
        
        return {
            'summary': {
                'total_claims_checked': total_claims,
                'verified': status_counts['verified'],
                'contradicted': status_counts['contradicted'],
                'partial': status_counts['partial'],
                'unverifiable': status_counts['unverifiable'],
                'verification_rate': round(verification_rate, 2),
                'accuracy_score': round(accuracy_score, 2),
                'high_confidence_verified': high_confidence_verified,
                'provider_usage': provider_usage
            },
            'flagged_claims': flagged_claims,
            'verification_timestamp': datetime.now().isoformat()
        }
    
    def export_results(self, output_path: str):
        """Export verification results to JSON"""
        report = self.generate_report()
        
        output_data = {
            'report': report,
            'detailed_results': [asdict(result) for result in self.verification_results]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nVerification results exported to: {output_path}")
        return output_data
    
    def print_summary(self):
        """Print a human-readable summary"""
        report = self.generate_report()
        
        if 'error' in report:
            print(report['error'])
            return
        
        summary = report['summary']
        
        print(f"\n{'='*60}")
        print("FACT-CHECK VERIFICATION REPORT (Local Ollama + Tavily)")
        print(f"{'='*60}\n")
        
        print(f"Total Claims Checked: {summary['total_claims_checked']}")
        print(f"Verification Rate: {summary['verification_rate']}%")
        print(f"Overall Accuracy Score: {summary['accuracy_score']}%\n")
        
        print("Breakdown:")
        total = summary['total_claims_checked']
        print(f"  ✓ Verified: {summary['verified']} ({summary['verified']/total*100:.1f}%)")
        print(f"  ✗ Contradicted: {summary['contradicted']} ({summary['contradicted']/total*100:.1f}%)")
        print(f"  ~ Partial: {summary['partial']} ({summary['partial']/total*100:.1f}%)")
        print(f"  ? Unverifiable: {summary['unverifiable']} ({summary['unverifiable']/total*100:.1f}%)")
        
        print(f"\nHigh-Confidence Verified: {summary['high_confidence_verified']}")
        
        print(f"\nSearch Provider Usage:")
        for provider, count in summary['provider_usage'].items():
            print(f"  • {provider}: {count} claims ({count/total*100:.1f}%)")


# Main execution
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python claim_verifier.py <claims_json> [output_json] [--max-claims N]")
        print("\nExample: python claim_verifier.py claims.json results.json --max-claims 5")
        sys.exit(1)
    
    claims_file = sys.argv[1]
    output_file = "verification_results.json"
    max_claims = None
    
    # Parse arguments
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--max-claims" and i + 1 < len(sys.argv):
            max_claims = int(sys.argv[i + 1])
            i += 2
        elif not sys.argv[i].startswith("--"):
            output_file = sys.argv[i]
            i += 1
        else:
            i += 1
    
    try:
        verifier = EnhancedClaimVerifier()
        claims = verifier.load_claims(claims_file)
        
        if max_claims:
            print(f"Limiting verification to first {max_claims} claims")
        
        verifier.verify_all_claims(claims, delay=2.0, max_claims=max_claims)
        verifier.print_summary()
        verifier.export_results(output_file)
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)