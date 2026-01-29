import streamlit as st
import os
import json
import tempfile
import shutil  # ← new import for copying files
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

# Custom CSS (unchanged)
st.markdown("""
<style>
    .main-header { font-size: 3rem; font-weight: bold; text-align: center; margin-bottom: 0.5rem; }
    .sub-header { text-align: center; color: #666; margin-bottom: 2rem; }
    .metric-card { background: #f0f2f6; padding: 1.5rem; border-radius: 0.5rem; text-align: center; margin: 0.5rem 0; }
    .metric-value { font-size: 2.5rem; font-weight: bold; margin: 0.5rem 0; }
    .metric-label { color: #666; font-size: 0.9rem; text-transform: uppercase; }
    .verified { color: #28a745; }
    .inaccurate { color: #ffc107; }
    .false { color: #dc3545; }
    .claim-card { padding: 1rem; border-radius: 0.5rem; margin: 0.5rem 0; border-left: 4px solid; }
    .claim-card-verified { background: #d4edda; border-left-color: #28a745; }
    .claim-card-inaccurate { background: #fff3cd; border-left-color: #ffc107; }
    .claim-card-false { background: #f8d7da; border-left-color: #dc3545; }
    .stProgress > div > div > div > div { background: linear-gradient(to right, #dc3545, #ffc107, #28a745); }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    if 'processed' not in st.session_state:
        st.session_state.processed = False
    if 'claims_data' not in st.session_state:
        st.session_state.claims_data = None
    if 'verification_data' not in st.session_state:
        st.session_state.verification_data = None
    if 'report_data' not in st.session_state:
        st.session_state.report_data = None
    if 'reporter' not in st.session_state:
        st.session_state.reporter = None

def display_metric(label, value, color_class=""):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value {color_class}">{value}</div>
    </div>
    """, unsafe_allow_html=True)

def process_pdf(uploaded_file, max_claims=None):
    # Persistent location for verification file (outside temp dir)
    verification_file = "verification_results.json"  # saved in current working directory

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = os.path.join(tmp_dir, uploaded_file.name)
        claims_file = os.path.join(tmp_dir, 'claims.json')
        tmp_verification = os.path.join(tmp_dir, 'tmp_verification.json')  # temp location inside temp dir

        try:
            # Save uploaded PDF
            with open(pdf_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            progress_bar = st.progress(0)
            st.info("📄 Step 1/3: Extracting claims from PDF...")
            
            extractor = LangChainClaimExtractor(pdf_path)
            claims = extractor.extract_all_claims()
            claims_data = extractor.export_to_json(claims_file)
            
            progress_bar.progress(33)
            st.success(f"✓ Extracted {claims_data.get('total_claims', 0)} claims")
            
            # Step 2: Verify
            st.info("🔍 Step 2/3: Verifying claims against web data...")
            progress_bar.progress(40)
            
            verifier = EnhancedClaimVerifier()
            claims_list = verifier.load_claims(claims_file)
            
            # Run verification once
            verification_results = verifier.verify_all_claims(
                claims_list,
                delay=1.5,
                max_claims=max_claims
            )
            
            # Export to temporary file first
            verifier.export_results(tmp_verification)
            
            # Copy to persistent location before temp dir disappears
            if os.path.exists(tmp_verification):
                shutil.copy(tmp_verification, verification_file)
            else:
                st.error("Verification export failed – no file created inside temp dir.")
                return None, None, None, None
            
            # Final safety check
            if not os.path.exists(verification_file):
                st.error(f"Could not save verification file to {verification_file}")
                return None, None, None, None
            
            num_verified = len(verification_results)
            progress_bar.progress(70)
            st.success(f"✓ Verified {num_verified} claims")
            
            # Step 3: Generate Report
            st.info("📊 Step 3/3: Generating report...")
            progress_bar.progress(75)
            
            reporter = FactCheckReporter(verification_file)
            reporter.process_verification_results()
            report_data = reporter.generate_executive_summary()
            
            progress_bar.progress(100)
            st.success("✓ Report generated!")
            
            # Load verification data for display
            with open(verification_file, 'r', encoding='utf-8', errors='replace') as f:
                verification_data = json.load(f)
            
            return claims_data, verification_data, report_data, reporter
            
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            import traceback
            st.code(traceback.format_exc(), language="python")
            return None, None, None, None

def main():
    init_session_state()
    
    st.markdown('<h1 class="main-header">📋 Fact-Check App</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Verify claims in your documents with AI & web search</p>', unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("⚙️ Settings")
        max_claims = st.slider(
            "Max claims to verify",
            min_value=1,
            max_value=50,
            value=5,
            step=1,
            help="Start small (e.g. 3–5) to test faster"
        )
        st.markdown("---")
        st.header("📖 How to Use")
        st.markdown("""
        1. Upload PDF  
        2. Click **Start Fact-Checking**  
        3. Wait for analysis & review results
        """)
        st.markdown("---")
        st.caption("Powered by Mistral + Tavily")

    if not st.session_state.processed:
        st.header("📤 Upload Document")
        uploaded_file = st.file_uploader("Drop your PDF here", type=['pdf'])
        
        if uploaded_file:
            st.success(f"✓ Loaded: {uploaded_file.name}")
            col1, col2 = st.columns(2)
            col1.metric("File Name", uploaded_file.name)
            col2.metric("Size", f"{uploaded_file.size / 1024:.1f} KB")
            
            if st.button("🚀 Start Fact-Checking", type="primary", use_container_width=True):
                with st.spinner("Processing document..."):
                    result = process_pdf(uploaded_file, max_claims)
                    if result and result[0] is not None:
                        claims_data, verification_data, report_data, reporter = result
                        st.session_state.claims_data = claims_data
                        st.session_state.verification_data = verification_data
                        st.session_state.report_data = report_data
                        st.session_state.reporter = reporter
                        st.session_state.processed = True
                        st.rerun()
        else:
            st.info("👆 Upload a PDF to begin")
    else:
        report_data = st.session_state.report_data
        reporter = st.session_state.reporter
        
        st.header("📊 Results Summary")
        
        quality = report_data.get('document_quality', 'UNKNOWN')
        if 'EXCELLENT' in quality.upper():
            st.success(f"### Document Quality: {quality}")
        elif 'GOOD' in quality.upper():
            st.info(f"### Document Quality: {quality}")
        elif 'FAIR' in quality.upper():
            st.warning(f"### Document Quality: {quality}")
        else:
            st.error(f"### Document Quality: {quality}")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1: display_metric("Total Claims", report_data.get('total_claims', 0))
        with col2: display_metric("Accuracy Rate", f"{report_data.get('accuracy_rate', 0)}%", "verified")
        with col3: display_metric("Issues Found", report_data.get('issues_requiring_action', 0), "inaccurate")
        with col4: display_metric("Verified", report_data.get('verified', 0), "verified")
        
        st.markdown("---")
        st.header("🔍 Detailed Claims")
        st.info("Detailed claim display coming soon – currently showing summary only.")
        
        st.markdown("---")
        st.header("💾 Download Reports")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📄 Text Report"):
                st.info("Text report generation not fully implemented yet.")
        with col2:
            if st.button("📊 JSON Report"):
                st.info("JSON report generation not fully implemented yet.")
        with col3:
            if st.button("🌐 HTML Report"):
                st.info("HTML report generation not fully implemented yet.")
        
        if st.button("🔄 Check Another Document", type="secondary"):
            for key in ['processed', 'claims_data', 'verification_data', 'report_data', 'reporter']:
                if key in st.session_state:
                    del st.session_state[key]
            # Optional: delete verification_results.json if you want clean start
            if os.path.exists("verification_results.json"):
                os.remove("verification_results.json")
            st.rerun()

if __name__ == "__main__":
    main()