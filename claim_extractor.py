from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import json
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


# Pydantic models for structured output
class ExtractedClaim(BaseModel):
    """Structured claim extracted from document"""
    claim_text: str = Field(description="The actual claim or statement")
    claim_type: str = Field(description="Type: statistic, date, financial, or technical_spec")
    context: str = Field(description="Surrounding context from the document")
    confidence: str = Field(description="Confidence level: high, medium, or low")


class ClaimExtractionResult(BaseModel):
    """Result of claim extraction from a document chunk"""
    claims: List[ExtractedClaim] = Field(description="List of extracted claims")


@dataclass
class Claim:
    """Represents an extracted claim from the document"""
    claim_type: str
    text: str
    context: str
    page_number: int
    confidence: str


class LangChainClaimExtractor:
    """Extract verifiable claims from PDFs using LangChain + local Ollama"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.claims: List[Claim] = []
        
        # Local Ollama LLM 
        self.llm = ChatOllama(
            model="mistral:latest",           
            temperature=0.0,
            format="json"                     
        )
        
        # Text splitter for chunking documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        
        # Output parser for structured extraction
        self.parser = PydanticOutputParser(pydantic_object=ClaimExtractionResult)
        
        # Create extraction prompt
        self.extraction_prompt = PromptTemplate(
            template="""You are a claim extraction expert. Extract all verifiable claims from the following text.

A claim is a factual statement that can be verified, including:
- Statistics: percentages, numbers, growth rates, comparisons
- Dates: specific dates, years, quarters, timelines, deadlines
- Financial figures: revenues, costs, valuations, market caps, prices
- Technical specifications: measurements, capacities, speeds, sizes, specifications

For each claim, provide:
- claim_text: The exact claim or number
- claim_type: One of [statistic, date, financial, technical_spec]
- context: The sentence or phrase containing the claim
- confidence: high, medium, or low based on clarity

Text to analyze:
{text}

{format_instructions}

Extract all verifiable claims from the text above.""",
            input_variables=["text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        # Create extraction chain
        self.extraction_chain = self.extraction_prompt | self.llm | self.parser
    
    def load_document(self) -> List[Dict[str, Any]]:
        """Load PDF document using LangChain loader"""
        loader = PyPDFLoader(self.pdf_path)
        documents = loader.load()
        
        # Convert to list with page metadata
        pages_data = []
        for doc in documents:
            pages_data.append({
                'page_number': doc.metadata.get('page', 0) + 1,
                'text': doc.page_content,
                'metadata': doc.metadata
            })
        
        return pages_data
    
    def extract_claims_from_text(self, text: str, page_number: int) -> List[Claim]:
        """Extract claims from a text chunk using LangChain"""
        try:
            # Run extraction chain
            result = self.extraction_chain.invoke({"text": text})
            
            # Convert to Claim objects
            claims = []
            for extracted_claim in result.claims:
                claim = Claim(
                    claim_type=extracted_claim.claim_type,
                    text=extracted_claim.claim_text,
                    context=extracted_claim.context,
                    page_number=page_number,
                    confidence=extracted_claim.confidence
                )
                claims.append(claim)
            
            return claims
            
        except Exception as e:
            print(f"Error extracting claims: {e}")
            return []
    
    def extract_all_claims(self) -> List[Claim]:
        """Extract all claims from the PDF using LangChain"""
        # Load document
        pages_data = self.load_document()
        
        print(f"Processing {len(pages_data)} pages...")
        
        # Process each page
        for page_data in pages_data:
            text = page_data['text']
            page_num = page_data['page_number']
            
            if not text.strip():
                continue
            
            # Split text into chunks if needed
            if len(text) > 2000:
                chunks = self.text_splitter.split_text(text)
            else:
                chunks = [text]
            
            # Extract claims from each chunk
            for chunk in chunks:
                page_claims = self.extract_claims_from_text(chunk, page_num)
                self.claims.extend(page_claims)
            
            print(f"  Page {page_num}: {len([c for c in self.claims if c.page_number == page_num])} claims")
        
        return self.claims
    
    def deduplicate_claims(self) -> List[Claim]:
        """Remove duplicate claims"""
        seen = set()
        unique_claims = []
        
        for claim in self.claims:
            # Create a unique key
            key = (claim.claim_type, claim.text.lower().strip())
            if key not in seen:
                seen.add(key)
                unique_claims.append(claim)
        
        return unique_claims
    
    def export_to_json(self, output_path: str) -> Dict[str, Any]:
        """Export claims to JSON file"""
        unique_claims = self.deduplicate_claims()
        
        claims_dict = {
            'total_claims': len(unique_claims),
            'claims_by_type': {
                'statistics': len([c for c in unique_claims if c.claim_type == 'statistic']),
                'dates': len([c for c in unique_claims if c.claim_type == 'date']),
                'financial': len([c for c in unique_claims if c.claim_type == 'financial']),
                'technical_specs': len([c for c in unique_claims if c.claim_type == 'technical_spec'])
            },
            'claims': [asdict(claim) for claim in unique_claims]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(claims_dict, f, indent=2, ensure_ascii=False)
        
        return claims_dict
    
    def print_summary(self):
        """Print a summary of extracted claims"""
        unique_claims = self.deduplicate_claims()
        
        print(f"\n{'='*60}")
        print("CLAIM EXTRACTION SUMMARY (LangChain + Ollama)")
        print(f"{'='*60}\n")
        print(f"Total Claims Extracted: {len(unique_claims)}\n")
        
        by_type = {}
        for claim in unique_claims:
            by_type[claim.claim_type] = by_type.get(claim.claim_type, 0) + 1
        
        for claim_type, count in by_type.items():
            print(f"{claim_type.replace('_', ' ').title()}: {count}")
        
        print(f"\n{'='*60}\n")
        
        # Print examples
        for claim_type in by_type.keys():
            claims_of_type = [c for c in unique_claims if c.claim_type == claim_type][:3]
            if claims_of_type:
                print(f"\n{claim_type.replace('_', ' ').title()} Examples:")
                for claim in claims_of_type:
                    print(f"  • {claim.text}")
                    print(f"    Context: ...{claim.context[:80]}...")
                    print(f"    Page: {claim.page_number}\n")


# Main execution 
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python claim_extractor.py <path_to_pdf> [output_json]")
        print("\nExample: python claim_extractor.py document.pdf claims.json")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "extracted_claims.json"
    
    print(f"Extracting claims from: {pdf_path}")
    
    extractor = LangChainClaimExtractor(pdf_path)  
    claims = extractor.extract_all_claims()
    
    # Print summary
    extractor.print_summary()
    
    # Export to JSON
    result = extractor.export_to_json(output_path)
    
    print(f"\nClaims exported to: {output_path}")
    print(f"Total unique claims: {result['total_claims']}")