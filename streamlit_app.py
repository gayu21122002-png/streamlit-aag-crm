import streamlit as st
import pandas as pd
import json
import os
import re 
from google import genai
from google.genai import types

# --- Configuration ---
GEMINI_MODEL = "gemini-2.5-flash"
EMAIL_RECIPIENT = "crm_team@yourcompany.com"

# --- Streamlit Secrets for Email (Placeholders) ---
SMTP_SERVER = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = st.secrets.get("SMTP_PORT", 587)
SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "your_sender_email@gmail.com")
SENDER_PASSWORD = st.secrets.get("SENDER_PASSWORD", "your_app_password")

# --- DATA CLEANING FUNCTION (RETAINS REGEX) ---
def clean_json_response(response_text: str) -> str:
    """
    Cleans the raw text response from the Gemini API to extract a pure JSON string.
    """
    # Pattern to find a JSON block wrapped in ```json ... ``` or just ``` ... ```
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if match:
        return match.group(1).strip()
    
    # Fallback: Find content between the first { and last }
    match = re.search(r'\{[\s\S]*\}', response_text.strip())
    if match:
        return match.group(0).strip()
    
    return response_text.strip()


# --- DATA LOADING FUNCTION ---
@st.cache_data
def load_sample_data():
    """Loads the sample product data from CSV."""
    if os.path.exists("sample_products.csv"):
        try:
            df = pd.read_csv("sample_products.csv", dtype={'Product_ID': str, 'Brand': str, 'Description': str, 'Price': int})
            return df
        except Exception as e:
            st.error(f"🚨 **Error reading CSV:** Check your `sample_products.csv` content. Error: {e}")
            return pd.DataFrame()
    else:
        st.error("🚨 **Error:** `sample_products.csv` not found. Please ensure it is committed to your repository.")
        return pd.DataFrame()

# --- GEMINI API SETUP ---
try:
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


# --- GEMINI FUNCTION (SIMILARITY CHECK) - NO RESPONSE_SCHEMA ---

def run_similarity_analysis(data_df, new_name, new_price):
    """
    Constructs the prompt and calls the Gemini API to perform similarity analysis.
    This version relies ONLY on the prompt for JSON output, removing the strict schema.
    """
    if not client:
        return None, "Gemini client not initialized."

    data_str = data_df.to_string(index=False)
    
    # 1. Define the desired JSON structure for the model
    json_format_example = {
        "Similarity_Score_Percent": "95",
        "Risk_Level": "HIGH RISK",
        "Matching_Product_ID": "P001",
        "Reasoning": "The new listing exactly matches the existing 'P001' item name and price."
    }

    # 2. Construct the System Instruction and Prompt - EXTREMELY STRICT
    system_instruction = (
        "You are an AI Product Duplication and Similarity Guardian. "
        "Your task is to compare a NEW listing against a list of EXISTING products. "
        "The comparison must determine a similarity score (0-100%). "
        "A score over 75% is 'HIGH RISK'. Your entire output MUST be a valid JSON object ONLY, "
        "without any introductory text, markdown wrappers (like ```json), or final remarks."
    )
    
    prompt = f"""
    --- EXISTING PRODUCT DATABASE ---
    {data_str}
    
    --- NEW PRODUCT LISTING ---
    Name/Description: {new_name}
    Price: {new_price}
    
    --- ANALYSIS INSTRUCTIONS ---
    1. Analyze the 'NEW PRODUCT LISTING' against all products in the 'EXISTING PRODUCT DATABASE'.
    2. Determine the single highest 'Similarity_Score_Percent' (as a number string, e.g., '95'). 
    3. Identify the 'Matching_Product_ID' for the product with the highest score. If no match is found, use 'N/A'.
    4. Based on the Similarity Score:
       - 0-25%: Low Risk
       - 26-75%: Medium Risk
       - 76-100%: High Risk
    5. Provide a clear, concise 'Reasoning' (1-2 sentences).
    6. Return the output in the EXACT JSON format shown below, and NO other text:
       {json.dumps(json_format_example, indent=2)}
    """
    
    # 3. Call the Gemini API without response_schema
    with st.spinner("Running deep similarity analysis with Gemini..."):
        try:
            # Removed response_schema and response_mime_type to use standard text generation
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                )
            )
            
            # CRITICAL FIX: Clean and Load the JSON string
            cleaned_json_str = clean_json_response(response.text)
            
            # This line will now handle the JSON parsing without Pydantic validation
            analysis_result = json.loads(cleaned_json_str)
            
            # Perform simple validation to ensure required fields exist
            required_keys = ["Similarity_Score_Percent", "Risk_Level", "Reasoning"]
            if not all(key in analysis_result for key in required_keys):
                 raise ValueError(f"Missing required fields in response: {analysis_result}")
                 
            return analysis_result, None
            
        except json.JSONDecodeError as e:
            st.error(f"❌ **JSON Parsing Failed:** The model's response could not be converted to JSON. Raw output: `{response.text}`")
            return None, f"JSONDecodeError: {e}"
        except ValueError as e:
            st.error(f"❌ **Data Validation Failed:** The model returned JSON, but it was incomplete. Error: {e}")
            return None, f"DataValidationError: {e}"
        except Exception as e:
            return None, f"Gemini API Call Failed: {e}"


# --- EMAIL FUNCTION (Placeholder) ---

def send_email_report(analysis_data, score):
    """Placeholder for the function to send the email."""
    
    if SENDER_EMAIL == "your_sender_email@gmail.com":
        st.warning("⚠️ **Email Setup Pending:** Skipping email. Configure email secrets to enable sending.")
        return False
        
    action_rec = 'APPROVE (New Product)'
    if score >= 75:
         action_rec = 'REJECT AND INVESTIGATE (High Similarity)'
    elif score >= 26:
         action_rec = 'REVIEW NAME/PRICE (Medium Similarity)'
    

    # Build the neat email body format
    report_body = f"""
    **AAG Similarity Report**
    
    * New Listing: {new_listing_name} (₹{new_listing_price})
    
    ---
    
    ## 🚨 Duplication Alert: {analysis_data['Risk_Level'].upper()} 🚨
    
    * **Similarity Score:** {score}%
    * **Matching Product ID:** {analysis_data.get('Matching_Product_ID', 'N/A')}
    * **Reasoning:** {analysis_data['Reasoning']}
    * **Recommended Action:** {action_rec}
    """

    st.success(f"✅ **Report Prepared for {EMAIL_RECIPIENT}:** (Simulated Send)")
    st.code(report_body)
    return True


# --- BUTTON AND EXECUTION ---

if st.button("🔍 Run Similarity Check & Generate Report", type="primary"):
    if client:
        # 1. Run the analysis
        analysis_data, error = run_similarity_analysis(sample_data, new_listing_name, new_listing_price)
        
        # 2. Display results or error
        if analysis_data:
            st.markdown("---")
            st.subheader("✅ AI Similarity Guardian Report")
            
            # --- Score Conversion ---
            try:
                score = int(analysis_data['Similarity_Score_Percent'].strip())
            except ValueError:
                st.error("Error: AI returned a score that is not a valid number. Defaulting to 0% score.")
                score = 0
            
            # Determine risk and action
            risk = analysis_data['Risk_Level'].lower()
            if risk == "high risk" or score >= 76:
                st.error(f"### 🚨 HIGH RISK - Likely Duplicate Detected")
                action_rec = "REJECT AND INVESTIGATE"
            elif risk == "medium risk" or score >= 26:
                st.warning(f"### 🟠 MEDIUM RISK - Review Recommended")
                action_rec = "REVIEW NAME/PRICE"
            else:
                st.success(f"### 🟢 LOW RISK - New Product")
                action_rec = "APPROVE"
            
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Similarity Score", f"{score}%")
                st.metric("Matching Product ID", analysis_data.get('Matching_Product_ID', 'N/A'))
            with col2:
                st.metric("Risk Level", analysis_data['Risk_Level'])
                st.metric("Recommended Action", action_rec)

            st.markdown(f"**Detailed Reasoning:** {analysis_data['Reasoning']}")
            
            # 3. Check for the 75% threshold and send email (Simulated)
            if score >= 75:
                st.info("🎯 **Threshold Met (>= 75%):** High similarity detected. Preparing to send email alert.")
                send_email_report(analysis_data, score)
                
        elif error:
            st.error(f"Analysis failed: {error}")
    else:
        st.warning("Please resolve the Gemini API key issue before running analysis.")
