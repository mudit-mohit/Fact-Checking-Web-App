import streamlit as st
import os
import json
import tempfile
from claim_extractor import LangChainClaimExtractor
from claim_verifier import EnhancedClaimVerifier
from report_generator import FactCheckReporter
from claim_verifier import VerificationResult

# Page configuration
st.set_page_config(
    page_title="Fact-Check App",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        text-align: center;
        margin: 0.5rem 0;
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    .metric-label {
        color: #666;
        font-size: 0.9rem;
        text-transform: uppercase;
    }
    .verified { color: #28a745; }
    .inaccurate { color: #ffc107; }
    .false { color: #dc3545; }
    .claim-card {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid;
    }
    .claim-card-verified {
        background: #d4edda;
        border-left-color: #28a745;
    }
    .claim-card-inaccurate {
        background: #fff3cd;
        border-left-color: #ffc107;
    }
    .claim-card-false {
        background: #f8d7da;
        border-left-color: #dc3545;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(to right, #dc3545, #ffc107, #28a745);
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    """Initialize session state variables"""
    if 'processed' not in st.session_state:
        st.session_state.processed = False
    if 'claims_data' not in st.session_state:
        st.session_state.claims_data = None
    if 'verification_data' not in st.session_state:
        st.session_state.verification_data = None
    if 'report_data' not in st.session_state:
        st.session_state.report_data = None

def display_metric(label, value, color_class=""):
    """Display a metric card"""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value {color_class}">{value}</div>
    </div>
    """, unsafe_allow_html=True)

def display_claim_card(claim, verdict_info):
    """Display a claim card with verdict"""
    card_class = f"claim-card-{claim['verdict']}"
    icon = verdict_info['icon']
    
    st.markdown(f"""
    <div class="claim-card {card_class}">
        <h4>{icon} {claim['claim_text']}</h4>
        <p><strong>Type:</strong> {claim['claim_type']} | <strong>Page:</strong> {claim['page_number']}</p>
        <p><em>"{claim['context'][:150]}..."</em></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Confidence bar
    confidence_pct = int(claim['confidence_score'] * 100)
    st.progress(claim['confidence_score'], text=f"Confidence: {confidence_pct}%")
    
    # Explanation and recommendation
    with st.expander("📊 Details"):
        st.write("**Explanation:**", claim['explanation'][:300] + "...")
        st.info(f"**→ {claim['recommendation']}**")

def process_pdf(uploaded_file, max_claims=None):
    """Process the uploaded PDF through the fact-checking pipeline"""
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Save uploaded file
        pdf_path = os.path.join(tmp_dir, uploaded_file.name)
        with open(pdf_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        
        claims_file = os.path.join(tmp_dir, 'claims.json')
        verification_file = os.path.join(tmp_dir, 'verification.json')
        
        try:
            # Step 1: Extract Claims
            st.info("📄 Step 1/3: Extracting claims from PDF...")
            progress_bar = st.progress(0)
            
            extractor = LangChainClaimExtractor(pdf_path)  
            claims = extractor.extract_all_claims()
            claims_data = extractor.export_to_json(claims_file)
            
            progress_bar.progress(33)
            st.success(f"✓ Extracted {claims_data.get('total_claims', 0)} claims")
            
            # Step 2: Verify Claims
            st.info("🔍 Step 2/3: Verifying claims against web data...")
            progress_bar.progress(35)
            
            verifier = EnhancedClaimVerifier()  
            claims_list = verifier.load_claims(claims_file)
            
            # Verify with progress updates
            total = len(claims_list) if not max_claims else min(max_claims, len(claims_list))
            
            for idx in range(total):
                verifier.verify_all_claims(claims_list, delay=1.5, max_claims=idx+1)
                progress = 35 + int((idx + 1) / total * 30)
                progress_bar.progress(progress)
            
            verifier.export_results(verification_file)
            
            progress_bar.progress(66)
            st.success(f"✓ Verified {total} claims")
            
            # Step 3: Generate Report
            st.info("📊 Step 3/3: Generating report...")
            progress_bar.progress(70)
            
            reporter = FactCheckReporter(verification_file)
            reporter.process_verification_results()
            report_data = reporter.generate_executive_summary()
            
            progress_bar.progress(100)
            st.success("✓ Report generated!")
            
            # Load data for display
            with open(verification_file, 'r', encoding='utf-8', errors='replace') as f:
                verification_data = json.load(f)
            
            return claims_data, verification_data, report_data, reporter
            
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            return None, None, None, None

def main():
    init_session_state()
    
    # Header
    st.markdown('<h1 class="main-header">📋 Fact-Check App</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Verify claims in your documents with local AI (Ollama) & web search</p>', unsafe_allow_html=True)
    
    # Sidebar – no API key needed anymore
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Max claims slider
        max_claims = st.slider(
            "Max claims to verify",
            min_value=1,
            max_value=50,
            value=5,
            step=1,
            help="Start small (e.g. 3–5) to test faster"
        )
        
        st.markdown("---")
        
        # Instructions 
        st.header("📖 How to Use")
        st.markdown("""
        1. **Upload PDF** - Drag and drop your document
        2. **Click Process** - Wait for local analysis 
        3. **Review Results** - Check flagged claims
        
        **Requirements:**
        - Ollama running locally with a model like `qwen2.5:14b` or `mistral:latest`
        - Tavily API key 
        
        **Verdicts:**
        - ✅ **Verified** - Accurate
        - ⚠️ **Inaccurate** - Needs update
        - ❌ **False** - No evidence
        """)
        
        st.markdown("---")
        st.caption("Built with Streamlit • Powered by Ollama + Tavily")
    
    # Main content
    if not st.session_state.processed:
        # Upload section
        st.header("📤 Upload Document")
        
        uploaded_file = st.file_uploader(
            "Drop your PDF here or click to browse",
            type=['pdf'],
            help="Upload a PDF document to fact-check"
        )
        
        if uploaded_file:
            st.success(f"✓ Loaded: {uploaded_file.name}")
            
            # Display file info
            col1, col2 = st.columns(2)
            with col1:
                st.metric("File Name", uploaded_file.name)
            with col2:
                st.metric("File Size", f"{uploaded_file.size / 1024:.1f} KB")
            
            # Process button
            if st.button("🚀 Start Fact-Checking", type="primary", use_container_width=True):
                with st.spinner("Processing your document..."):
                    claims_data, verification_data, report_data, reporter = process_pdf(
                        uploaded_file, max_claims
                    )
                    
                    if report_data:
                        st.session_state.claims_data = claims_data
                        st.session_state.verification_data = verification_data
                        st.session_state.report_data = report_data
                        st.session_state.reporter = reporter
                        st.session_state.processed = True
                        st.rerun()
        else:
            st.info("👆 Upload a PDF document to get started")
            
            with st.expander("📝 Example Documents"):
                st.markdown("""
                Try fact-checking these types of documents:
                - Blog posts with statistics
                - Quarterly reports with financial data
                - Research papers with dates and figures
                - Press releases with claims
                - Marketing materials with specs
                """)
    
    else:
        # Display results
        report_data = st.session_state.report_data
        verification_data = st.session_state.verification_data
        reporter = st.session_state.reporter
        
        # Summary metrics
        st.header("📊 Results Summary")
        
        # Quality grade 
        quality = report_data.get('document_quality', 'UNKNOWN - Report incomplete')
        if 'EXCELLENT' in quality:
            st.success(f"### {quality}")
        elif 'GOOD' in quality:
            st.info(f"### {quality}")
        elif 'FAIR' in quality:
            st.warning(f"### {quality}")
        else:
            st.error(f"### {quality}")
            st.warning("Verification didn't produce any results. Check Ollama is running and model is pulled.")
        
        # Metrics row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            display_metric("Total Claims", report_data.get('total_claims', 0))

        with col2:
            display_metric("Accuracy Rate", f"{report_data.get('accuracy_rate', 0)}%", "verified")

        with col3:
            display_metric("Issues Found", report_data.get('issues_requiring_action', 0), "inaccurate")

        with col4:
            display_metric("Verified", report_data.get('verified', 0), "verified")

        # Verdict breakdown – safe version
        st.markdown("---")
        st.header("📈 Verdict Breakdown")

        col1, col2, col3 = st.columns(3)

        with col1:
            verified = report_data.get('verified', 0)
            total = report_data.get('total_claims', 1)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">✅ Verified</div>
                <div class="metric-value verified">{verified}</div>
                <div class="metric-label">{verified / total * 100:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            inaccurate = report_data.get('inaccurate', 0)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">⚠️ Inaccurate</div>
                <div class="metric-value inaccurate">{inaccurate}</div>
                <div class="metric-label">{inaccurate / total * 100:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            false_claims = report_data.get('false', 0)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">❌ False</div>
                <div class="metric-value false">{false_claims}</div>
                <div class="metric-label">{false_claims / total * 100:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        # High priority issues – safe version
        high_priority = report_data.get('high_priority_issues', [])
        if high_priority:
            st.markdown("---")
            st.header(f"🚨 High Priority Issues ({len(high_priority)})")
            
            for issue in high_priority:
                icon = "⚠️" if issue.get('verdict') == 'inaccurate' else "❌"
                with st.container():
                    st.markdown(f"### {icon} {issue.get('claim', 'Unknown')}")
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Page:** {issue.get('page', 'N/A')}")
                    with col2:
                        st.metric("Confidence", f"{issue.get('confidence', 0):.0%}")
        else:
            st.info("No high priority issues detected (or verification didn't complete).")
        
        # Detailed claims with filters
        st.markdown("---")
        st.header("🔍 Detailed Claims")
        
        # Filter tabs
        verdict_filter = st.radio(
            "Filter by verdict:",
            ["All Claims", "✅ Verified", "⚠️ Inaccurate", "❌ False"],
            horizontal=True
        )
        
        # Get claims from reporter 
        all_claims = getattr(reporter, 'report_claims', [])
        
        # Filter claims
        if verdict_filter == "✅ Verified":
            filtered_claims = [c for c in all_claims if getattr(c, 'verdict', '') == 'verified']
        elif verdict_filter == "⚠️ Inaccurate":
            filtered_claims = [c for c in all_claims if getattr(c, 'verdict', '') == 'inaccurate']
        elif verdict_filter == "❌ False":
            filtered_claims = [c for c in all_claims if getattr(c, 'verdict', '') == 'false']
        else:
            filtered_claims = all_claims
        
        st.write(f"Showing {len(filtered_claims)} claims")
        
        # Display claims
        verdict_mapping = {
            'verified': {'icon': '✅', 'label': 'Verified'},
            'inaccurate': {'icon': '⚠️', 'label': 'Inaccurate'},
            'false': {'icon': '❌', 'label': 'False'}
        }
        
        for claim in filtered_claims:
            verdict = getattr(claim, 'verdict', 'unknown')
            verdict_info = verdict_mapping.get(verdict, {'icon': '❓', 'label': 'Unknown'})
            display_claim_card(vars(claim), verdict_info)
        
        # Download reports section
        st.markdown("---")
        st.header("💾 Download Reports")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Generate text report
            text_report = reporter.generate_text_report("/tmp/report.txt")
            with open("/tmp/report.txt", "r", encoding="utf-8", errors="replace") as f:
                text_content = f.read()

            st.download_button(
                "📄 Download Text Report",
                text_content,
                file_name="fact_check_report.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        with col2:
            # Generate JSON report
            json_report = reporter.generate_json_report("/tmp/report.json")
            with open("/tmp/report.json", "r", encoding="utf-8", errors="replace") as f:
                json_content = f.read()

            st.download_button(
                "📊 Download JSON Report",
                json_content,
                file_name="fact_check_report.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col3:
            # Generate HTML report
            html_report = reporter.generate_html_report("/tmp/report.html")
            with open("/tmp/report.html", "r", encoding="utf-8", errors="replace") as f:
                html_content = f.read()

            st.download_button(
                "🌐 Download HTML Report",
                html_content,
                file_name="fact_check_report.html",
                mime="text/html",
                use_container_width=True
            )
        
        # Reset button
        st.markdown("---")
        if st.button("🔄 Check Another Document", type="secondary", use_container_width=True):
            st.session_state.processed = False
            st.session_state.claims_data = None
            st.session_state.verification_data = None
            st.session_state.report_data = None
            st.rerun()

if __name__ == "__main__":
    main()