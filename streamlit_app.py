import streamlit as st
import pandas as pd
import json
import os
from google import genai
from google.genai import types

# --- Configuration ---
GEMINI_MODEL = "gemini-2.5-flash"
EMAIL_RECIPIENT = "crm_team@yourcompany.com" # Replace with a test email address

# --- Streamlit Secrets for Email (You MUST set these in Streamlit Cloud secrets) ---
# We will use st.secrets to securely store email credentials later.
# For now, we'll set placeholders to prevent errors.
SMTP_SERVER = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = st.secrets.get("SMTP_PORT", 587)
SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "your_sender_email@gmail.com")
SENDER_PASSWORD = st.secrets.get("SENDER_PASSWORD", "your_app_password")

# --- DATA LOADING FUNCTION ---
@st.cache_data
def load_sample_data():
    """Loads the sample product data from CSV."""
    if os.path.exists("sample_products.csv"):
        # We explicitly define the data types to prevent Streamlit errors
        df = pd.read_csv("sample_products.csv", dtype={'Product_ID': str, 'Brand': str, 'Description': str, 'Price': int})
        return df
    else:
        st.error("🚨 **Error:** `sample_products.csv` not found. Please create the file and upload it to your repository.")
        return pd.DataFrame()

# --- GEMINI API SETUP ---
try:
    # Initialize the client using the API key stored in Streamlit secrets
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except KeyError:
    st.error("🚨 **Gemini API Key Missing:** Please add `GEMINI_API_KEY` to your Streamlit secrets.")
    client = None
except Exception as e:
    st.error(f"🚨 **Gemini Client Error:** {e}")
    client = None

# --- STREAMLIT APP LAYOUT ---

st.set_page_config(page_title="AAG: Similarity Guardian", layout="wide")
st.title("🛡️ AI Authenticity & Similarity Guardian (AAG)")
st.caption("Now checking new listings against your sample data using Gemini.")

# Load the data and display for reference
sample_data = load_sample_data()
if not sample_data.empty:
    st.subheader("Reference Data (Sample Products)")
    st.dataframe(sample_data, use_container_width=True, hide_index=True)
    st.markdown("---")
else:
    st.stop()


# --- INPUT FORM ---
st.subheader("Analyze a New Product Listing")
new_listing_name = st.text_input(
    "1. Enter New Product Name/Description:",
    value="VILVAH Milk Drops Brightening Serum (20ml) - ₹620",
    help="Enter the full listing title and size."
)
new_listing_price = st.number_input(
    "2. Enter New Product Price (₹):",
    min_value=1,
    value=620,
    help="Enter the selling price."
)


# --- GEMINI FUNCTION (SIMILARITY CHECK) ---

def run_similarity_analysis(data_df, new_name, new_price):
    """
    Constructs the prompt and calls the Gemini API to perform similarity analysis.
    """
    if not client:
        return None, "Gemini client not initialized."

    # 1. Prepare the Sample Data as a readable string for the model
    data_str = data_df.to_string(index=False)
    
    # 2. Define the Structured Output Schema
    # This forces the model to return data in a predictable, parseable JSON format.
    analysis_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "Similarity_Score_Percent": types.Type.INTEGER,
            "Risk_Level": types.Type.STRING,
            "Matching_Product_ID": types.Type.STRING,
            "Matching_Product_Description": types.Type.STRING,
            "Reasoning": types.Type.STRING,
            "Action_Recommendation": types.Type.STRING
        },
        required=["Similarity_Score_Percent", "Risk_Level", "Reasoning"]
    )

    # 3. Construct the System Instruction and Prompt
    system_instruction = (
        "You are an AI Product Duplication and Similarity Guardian. "
        "Your task is to compare a NEW listing against a list of EXISTING products. "
        "The comparison must primarily focus on the product name/description and price, "
        "and determine a similarity score (0-100%). A score over 75% is considered 'HIGH RISK' for duplication."
    )
    
    prompt = f"""
    --- EXISTING PRODUCT DATABASE ---
    {data_str}
    
    --- NEW PRODUCT LISTING ---
    Name/Description: {new_name}
    Price: {new_price}
    
    --- ANALYSIS INSTRUCTIONS ---
    1. Analyze the 'NEW PRODUCT LISTING' against all products in the 'EXISTING PRODUCT DATABASE'.
    2. Determine the single highest 'Similarity_Score_Percent' to any existing product. 
    3. Identify the 'Matching_Product_ID' and 'Matching_Product_Description' for the product with the highest score.
    4. Based on the Similarity Score:
       - 0-25%: Low Risk (New Product)
       - 26-75%: Medium Risk (Similar Product, review needed)
       - 76-100%: High Risk (Likely Duplicate, reject and send email)
    5. Provide a clear, concise 'Reasoning' and an 'Action_Recommendation'.
    6. Return the output ONLY as a single JSON object that strictly conforms to the provided schema.
    """
    
    # 4. Call the Gemini API with the structured response configuration
    with st.spinner("Running deep similarity analysis with Gemini..."):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=analysis_schema
                )
            )
            # The response.text is a JSON string conforming to the schema
            analysis_result = json.loads(response.text)
            return analysis_result, None
            
        except Exception as e:
            return None, f"Gemini API Call Failed: {e}"


# --- EMAIL FUNCTION (TO BE IMPLEMENTED) ---

def send_email_report(analysis_data):
    """Placeholder for the function to send the email."""
    
    if SENDER_EMAIL == "your_sender_email@gmail.com":
        st.warning("⚠️ **Email Setup Pending:** Skipping email. You need to configure `SENDER_EMAIL`, `SENDER_PASSWORD`, `SMTP_SERVER`, and `SMTP_PORT` in Streamlit secrets.")
        return False
        
    try:
        # NOTE: The actual email implementation will use the `smtplib` library.
        # This is a placeholder to show the required format.
        
        # Build the neat email body format
        report_body = f"""
        **AAG Similarity Report**
        
        * New Listing: {new_listing_name} (₹{new_listing_price})
        
        ---
        
        ## 🚨 Duplication Alert: {analysis_data['Risk_Level'].upper()} 🚨
        
        * **Similarity Score:** {analysis_data['Similarity_Score_Percent']}%
        * **Matching Product ID:** {analysis_data.get('Matching_Product_ID', 'N/A')}
        * **Reasoning:** {analysis_data['Reasoning']}
        * **Recommended Action:** {analysis_data['Action_Recommendation']}
        """

        # For now, just display the email body instead of sending
        st.success(f"✅ **Report Prepared for {EMAIL_RECIPIENT}:**")
        st.code(report_body)
        return True

    except Exception as e:
        st.error(f"❌ **Email Sending Failed:** {e}")
        return False


# --- BUTTON AND EXECUTION ---

if st.button("🔍 Run Similarity Check & Generate Report", type="primary"):
    if client:
        # 1. Run the analysis
        analysis_data, error = run_similarity_analysis(sample_data, new_listing_name, new_listing_price)
        
        # 2. Display results or error
        if analysis_data:
            st.markdown("---")
            st.subheader("✅ AI Similarity Guardian Report")
            
            # Determine background color based on risk level
            risk = analysis_data['Risk_Level'].lower()
            if risk == "high risk":
                st.error(f"### 🚨 {analysis_data['Risk_Level'].upper()} - Likely Duplicate Detected")
            elif risk == "medium risk":
                st.warning(f"### 🟠 {analysis_data['Risk_Level'].upper()} - Review Recommended")
            else:
                st.success(f"### 🟢 {analysis_data['Risk_Level'].upper()} - New Product")
            
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Similarity Score", f"{analysis_data['Similarity_Score_Percent']}%")
                st.metric("Matching Product ID", analysis_data.get('Matching_Product_ID', 'N/A'))
            with col2:
                st.metric("Matching Description", analysis_data.get('Matching_Product_Description', 'N/A'))
                st.metric("Recommended Action", analysis_data['Action_Recommendation'])

            st.markdown(f"**Detailed Reasoning:** {analysis_data['Reasoning']}")
            
            # 3. Check for the 75% threshold and send email
            if analysis_data['Similarity_Score_Percent'] >= 75:
                st.info("🎯 **Threshold Met:** Similarity score is 75% or higher. Preparing to send email alert.")
                send_email_report(analysis_data)
                
        elif error:
            st.error(f"Analysis failed: {error}")
    else:
        st.warning("Please resolve the Gemini API key issue before running analysis.")
