import streamlit as st
from google import genai
from google.genai.errors import APIError

# --- DASHBOARD SETUP ---
st.set_page_config(
    page_title="AI Authenticity Guardian (AAG)",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ AI Authenticity Guardian (AAG) Dashboard")
st.subheader("Product Listing Analysis for Analytical CRM")

# --- GEMINI CLIENT INITIALIZATION ---
# The API Key is loaded automatically from the Streamlit Secrets
try:
    # Initialize the client using the API key stored in Streamlit secrets
    # The key is accessed via st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    model = "gemini-2.5-flash"
except (KeyError, ValueError) as e:
    # Handle case where the secret key is missing or invalid
    st.error(f"Configuration Error: GEMINI_API_KEY not found in Streamlit Secrets. Please ensure you have set the secret.")
    st.stop()
except APIError as e:
    st.error(f"API Connection Error: Could not initialize Gemini Client. Details: {e}")
    st.stop()


# --- ANALYSIS LOGIC (CACHED) ---
@st.cache_data(show_spinner=False)
def analyze_listing(listing_text):
    """Analyzes a product listing using the Gemini API."""

    # --- Prompt Engineering ---
    prompt = f"""
    You are an AI Authenticity Guardian (AAG) for a premium e-commerce platform. Your role is to analyze product listings for authenticity and quality signals.

    Analyze the following product listing:
    ---
    {listing_text}
    ---

    Provide your analysis in the following structured JSON format:
    {{
      "authenticity_score": "X/10",
      "risk_level": "Low Risk" | "Medium Risk" | "High Risk",
      "reasons": [
        "Reason 1: Detail about why this affects the score.",
        "Reason 2: Detail about why this affects the score."
      ],
      "crm_action_recommendation": "A concise, single-sentence instruction for the CRM analyst."
    }}

    Rules:
    1. The authenticity_score must be X/10.
    2. The risk_level must be one of the three options provided.
    3. The output MUST be only the raw JSON object, nothing else.
    """

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )

        # The response text will be a JSON string, which we load
        import json
        return json.loads(response.text)

    except Exception as e:
        st.error(f"Gemini API Call Failed: {e}")
        return None


# --- USER INTERFACE & FLOW ---

product_listing = st.text_area(
    "Paste the New Product Listing Text Here:",
    height=250,
    placeholder="Example: 'A brand new, genuine leather handbag, hand-stitched in Italy. Serial number AB12345. Comes with a certificate of authenticity.'"
)

if st.button("Analyze Listing Authenticity"):
    if not product_listing:
        st.warning("Please paste a product listing to begin analysis.")
        st.stop()

    # Run analysis and display results
    with st.spinner("Running deep analysis with Gemini (this may take a few seconds)..."):
        analysis_result = analyze_listing(product_listing)

    if analysis_result:
        st.success("✅ Analysis Complete!")

        # Determine color for the risk level
        if analysis_result.get("risk_level") == "High Risk":
            color = "inverse"
            icon = "🚨"
        elif analysis_result.get("risk_level") == "Medium Risk":
            color = "off"
            icon = "⚠️"
        else:
            color = "normal"
            icon = "✅"

        # Display Metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                label="Authenticity Score", 
                value=analysis_result.get("authenticity_score", "N/A")
            )
        with col2:
            st.metric(
                label="Risk Level", 
                value=f"{icon} {analysis_result.get('risk_level', 'N/A')}", 
                delta=analysis_result.get("risk_level", "N/A"),
                delta_color=color
            )

        st.divider()

        # Display Reasoning
        st.subheader("🕵️ LLM Reasoning for Score")
        st.markdown(f"**Recommendation for CRM Analyst:** *{analysis_result.get('crm_action_recommendation', 'No recommendation.')}*")
        st.markdown("---")

        st.write("**Key Reasons:**")
        st.warning("\n".join([f"* {reason}" for reason in analysis_result.get("reasons", ["No specific reasons provided."])]))
