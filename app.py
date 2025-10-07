"""
Streamlit web interface for the Code Review Agent.
"""
import asyncio
import streamlit as st
from pathlib import Path
from typing import Optional

from src.agent import CodeReviewAgent
from src.config import config

# Page configuration
st.set_page_config(
    page_title="Agentic Code Reviewer",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
    }
    .stTextArea [data-baseweb=base-input] {
        min-height: 300px;
    }
    .issue-high { color: #ff4b4b; }
    .issue-medium { color: #ffa500; }
    .issue-low { color: #4b8df8; }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'review_results' not in st.session_state:
    st.session_state.review_results = None


def display_issue(issue: dict) -> None:
    """Display a single issue with appropriate styling."""
    severity = issue.get('severity', 'medium').lower()
    severity_icon = {
        'high': '🔴',
        'medium': '🟠',
        'low': '🔵'
    }.get(severity, '⚪')
    
    with st.expander(f"{severity_icon} {issue.get('title', 'Issue')}"):
        st.markdown(f"**Description:** {issue.get('description', 'No description')}")
        
        if 'code' in issue:
            st.code(issue['code'], language='python')
            
        if 'suggestion' in issue:
            st.markdown("**Suggestion:**")
            st.code(issue['suggestion'], language='python')


def main():
    """Main Streamlit application."""
    st.title("🤖 Agentic Code Reviewer")
    st.caption("Upload a file or paste your code to get an AI-powered code review")
    
    # Sidebar with settings
    with st.sidebar:
        st.header("Settings")
        
        # Provider (OpenRouter) and model controls
        st.caption("Provider: OpenRouter (OpenAI-compatible)")
        base_url = st.text_input(
            "Base URL",
            value=config.openai_base_url,
            help="OpenAI-compatible endpoint. For OpenRouter use https://openrouter.ai/api/v1"
        )
        # Popular OpenRouter model options (verified working models)
        available_models = [
            "mistralai/mistral-7b-instruct",
            "meta-llama/llama-3.1-8b-instruct:free",
            "google/gemini-flash-1.5",
            "anthropic/claude-3-haiku"
        ]
        # Ensure current config model appears in the list and is selected
        if config.openai_model not in available_models:
            available_models.insert(0, config.openai_model)
        selected_model = st.selectbox(
            "Model (OpenRouter)",
            options=available_models,
            index=available_models.index(config.openai_model)
        )
        # Apply selections to runtime config
        config.openai_base_url = base_url
        config.openai_model = selected_model
        
        # Analysis options
        st.subheader("Analysis Options")
        col1, col2, col3 = st.columns(3)
        with col1:
            security = st.checkbox("Security", value=config.analyses["security"].enabled)
        with col2:
            maintainability = st.checkbox("Maintainability", value=config.analyses["maintainability"].enabled)
        with col3:
            style = st.checkbox("Style", value=config.analyses["style"].enabled)
    
    # Main content area
    tab1, tab2 = st.tabs(["📝 Code Input", "📁 File Upload"])
    
    with tab1:
        code = st.text_area(
            "Paste your code here",
            height=300,
            placeholder="def example():\n    # Your code here\n    pass"
        )
        file_name = st.text_input("File name (for syntax highlighting)", value="example.py")
    
    with tab2:
        # Accept common extensions matching supported languages
        upload_types = ["py", "js", "ts", "java", "go"]
        uploaded_file = st.file_uploader("Or upload a file", type=upload_types)
        if uploaded_file is not None:
            code = uploaded_file.getvalue().decode("utf-8", errors="replace")
            file_name = uploaded_file.name
    
    # Review button
    if st.button("🔍 Review Code", type="primary", use_container_width=True):
        if not code:
            st.error("Please enter or upload some code to review.")
            return
            
        with st.spinner("Analyzing your code..."):
            try:
                agent = CodeReviewAgent()
                file_extension = Path(file_name).suffix[1:] if file_name else "py"
                # Run async review synchronously
                st.session_state.review_results = asyncio.run(
                    agent.review_code(code=code, file_extension=file_extension)
                )
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
    
    # Display results if available
    if st.session_state.review_results:
        st.divider()
        st.header("🔍 Review Results")
        
        if 'error' in st.session_state.review_results:
            st.error(st.session_state.review_results['error'])
            return
        
        # Display overall feedback (synthesized review)
        feedback = st.session_state.review_results.get('feedback', '')
        
        if feedback and feedback.strip():
            st.markdown("### 📝 AI-Generated Summary")
            st.markdown(feedback)
        
        # Display detailed analysis results in structured format
        if 'analysis_results' in st.session_state.review_results:
            st.divider()
            st.header("📊 Detailed Code Analysis")
            
            analysis_results = st.session_state.review_results['analysis_results']
            
            # Create tabs for each analysis category
            if analysis_results:
                tab_names = list(analysis_results.keys())
                tabs = st.tabs([f"📋 {category.title()}" for category in tab_names])
                
                for i, (category, analysis) in enumerate(analysis_results.items()):
                    with tabs[i]:
                        issues = analysis.get('issues', [])
                        
                        if not issues:
                            st.success(f"✅ No {category} issues found")
                        else:
                            st.markdown(f"**{len(issues)} issues found:**")
                            
                            for j, issue in enumerate(issues, 1):
                                title = issue.get('title', f'{category.title()} Issue {j}')
                                description = issue.get('description', 'No description available')
                                severity = issue.get('severity', 'medium').upper()
                                
                                # Clean up the description
                                description = description.replace('<s>', '').replace('</s>', '')
                                description = description.replace('[OUT]', '').replace('[/OUT]', '')
                                description = description.replace('` ``', '```').replace('`  ``', '```')
                                
                                # Severity styling
                                severity_colors = {
                                    'HIGH': '🔴',
                                    'MEDIUM': '🟠', 
                                    'LOW': '🔵'
                                }
                                severity_icon = severity_colors.get(severity, '⚪')
                                
                                st.markdown(f"#### {severity_icon} {title} `[{severity}]`")
                                st.markdown(description)
                                st.markdown("---")


if __name__ == "__main__":
    main()
