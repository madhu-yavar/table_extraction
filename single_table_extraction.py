import streamlit as st
import pandas as pd
import json
import datetime
import pdfplumber
from io import BytesIO
from PyPDF2 import PdfReader
import requests
from langchain_google_genai import ChatGoogleGenerativeAI
import re
import csv


# ✅ Set Streamlit Page Layout
st.set_page_config(page_title="GKM- QBO - Statement Processor", page_icon="📄", layout="wide")

# ✅ Add Logo in Sidebar
logo_path = "/Users/yavar/Desktop/EDA BOT/yavarlogo.png"  
st.sidebar.image(logo_path, width=100)

def save_feedback(feedback_entry, filename="feedback_log.csv"):
    """Saves feedback data to a CSV file."""
    headers = ["Date", "Document", "Description", "Corrected Vendor", "Original Vendor", "Deposits_Credits", "Withdrawals_Debits", "Comments"]

    # ✅ Open CSV in append mode
    with open(filename, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        # ✅ Write headers only if file is empty
        if file.tell() == 0:
            writer.writerow(headers)

        # ✅ Write feedback data
        writer.writerow(feedback_entry)

# ✅ App Title & Disclaimer
st.markdown("""
    <div style="text-align: center; padding: 10px 0;">
        <h1 style="font-size: 32px; font-weight: bold; color: #004AAD; text-shadow: 2px 2px 3px rgba(0, 0, 0, 0.2);">GKM- QBO - Statement Processor</h1>
        <div style="width: 80px; height: 3px; background: linear-gradient(to right, #004AAD, #1976D2); margin: 5px auto; border-radius: 6px;"></div>
        <p style="font-size: 13px; font-weight: 400; color: #666; font-style: italic;">Extract & categorize transactions with AI</p>
    </div>
""", unsafe_allow_html=True)

st.markdown("""
    <div style="
        padding: 10px;
        background-color: #FFDADA;
        color: #8B0000;
        font-size: 15px;
        font-weight: 600;
        border-radius: 8px;
        border-left: 6px solid #D32F2F;
        text-align: center;
        margin: 15px 0;
        box-shadow: 0px 2px 6px rgba(0, 0, 0, 0.1);">
        ⚠️ Please mask any <b>Personally Identifiable Information (PII)</b> before uploading the PDF.
    </div>
""", unsafe_allow_html=True)

# ✅ Push Copyright Notice to the Bottom
st.markdown("""
    <style>
        .footer {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: #F8F9FA;
            padding: 10px;
            text-align: center;
            font-size: 14px;
            font-weight: bold;
            color: #555;
            border-top: 2px solid #1976D2;
        }
    </style>
    <div class="footer">© 2025 Copyright Yavar TechWorks Pte Ltd., All rights reserved.</div>
""", unsafe_allow_html=True)


# ✅ Sidebar Section
st.sidebar.header("Select AI Model")
ai_model = st.sidebar.radio("Choose AI Model", ["DeepSeek", "Gemini"], horizontal=True)
api_key = st.sidebar.text_input("🔑 Enter API Key", type="password")
pdf_file = st.sidebar.file_uploader("📄 Upload a Transation Statement (PDF)", type=["pdf"])
vendor_file = st.sidebar.file_uploader("📂 Upload a Vendor List (CSV or Excel)", type=["csv", "xls", "xlsx"])
process_button = st.sidebar.button("🚀 Process Document")

# ✅ Initialize Session State
if "transactions" not in st.session_state:
    st.session_state.transactions = None

# ✅ Extract Text from PDF (DeepSeek)
def extract_text_from_pdf(pdf_file):
    text_pages = []
    with pdfplumber.open(BytesIO(pdf_file.read())) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_pages.append(text.strip())
    return text_pages

# ✅ Extract Raw Text for Gemini
def extract_raw_text(pdf_content):
    try:
        reader = PdfReader(pdf_content)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

# ✅ Load Vendor List
def load_vendor_list(vendor_file):
    if vendor_file is not None:
        if vendor_file.name.endswith(".csv"):
            return pd.read_csv(vendor_file)["Payee"].tolist()
        else:
            return pd.read_excel(vendor_file)["Payee"].tolist()
    return []



def extract_json_from_gemini(response_text):
    """Extracts the first valid JSON block from the Gemini response and ensures numeric fields are never null."""
    try:
        # Remove markdown code block formatting (```json ... ```)
        response_text = re.sub(r"```json\s*", "", response_text)
        response_text = re.sub(r"\s*```", "", response_text)

        # Locate the first JSON array
        start = response_text.find("[")
        end = response_text.rfind("]") + 1  # Last closing bracket

        if start == -1 or end == 0:
            return None  # No JSON found

        json_str = response_text[start:end]

        # Fix potential formatting issues
        json_str = re.sub(r',\s*]', ']', json_str)  # Fix trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)

        transactions = json.loads(json_str)  # Convert to Python list

        # ✅ Ensure numeric fields are not None (convert None/null to 0)
        for tx in transactions:
            tx["Deposits_Credits"] = tx.get("Deposits_Credits", 0) or 0  # Default to 0 if missing or None
            tx["Withdrawals_Debits"] = tx.get("Withdrawals_Debits", 0) or 0  # Default to 0 if missing or None

        return transactions

    except json.JSONDecodeError as e:
        st.error(f"❌ JSON parsing failed: {str(e)}")
        return None



# ✅ Process Transactions with AI Model
def process_and_categorize(text, vendor_list, api_key, ai_model):
    """Processes transactions and categorizes them in one API call."""
    prompt = f"""
    Extract structured transactions from the bank statement and match them to vendors.

    **STRICT RULES:**
    - Use vendor names **ONLY** from this list:
      {json.dumps(vendor_list, indent=2)}
    - Do **NOT** assume vendors. If no match is found, return **"Unknown"**.
    - Do **NOT** modify transaction descriptions.
    - Return **pure JSON output** ONLY. No explanations, no additional text.

    **Statement Text:**
    {text}

    **Output Format (ONLY JSON)**
    ```json
    [
        {{"Date": "MM/DD/YYYY", "Description": "transaction details", "Deposits_Credits": number, "Withdrawals_Debits": number, "Vendor Name": "matched vendor"}},
        {{"Date": "MM/DD/YYYY", "Description": "another transaction", "Deposits_Credits": number, "Withdrawals_Debits": number, "Vendor Name": "matched vendor"}}
    ]
    ```

    **Example:**
    ```json
    [
        {{
            "Date": "11/01/2023",
            "Description": "Overdraft Fee for a Transaction Posted on 10/31 $143.00 Dell",
            "Deposits_Credits": 0,
            "Withdrawals_Debits": 35.00,
            "Vendor Name": "Overdraft Fee"
        }},
        {{
            "Date": "11/01/2023",
            "Description": "ATM Cash Deposit on 11/01 1530 Heitman St Fort Myers FL",
            "Deposits_Credits": 600.00,
            "Withdrawals_Debits": 0,
            "Vendor Name": "ATM"
        }}
    ]
    ```
    """

    if ai_model == "DeepSeek":
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload)

        if response.status_code == 200:
            try:
                json_data = response.json()["choices"][0]["message"]["content"]
                return json.loads(json_data.strip("```json").strip("```"))
            except Exception as e:
                st.error(f"❌ Error processing DeepSeek response: {e}")
                return []
        else:
            st.error(f"❌ API call failed: {response.status_code} - {response.text}")
            return []

    elif ai_model == "Gemini":
        gemini = ChatGoogleGenerativeAI(model="gemini-2.0-pro-exp-02-05", google_api_key=api_key, temperature=0)

        try:
            response = gemini.invoke(prompt)

            if not response or not response.content.strip():
                st.error("❌ Gemini API returned an empty response. Please check your API key and try again.")
                return []

            # Debugging: Show Raw API Response
            #st.text_area("🔍 Gemini Raw Response", response.content, height=200)

            # Extract clean JSON
            transactions = extract_json_from_gemini(response.content)

            if not transactions:
                st.error("❌ Failed to extract valid JSON from Gemini response.")
                return []

            return transactions

        except Exception as e:
            st.error(f"❌ Unexpected Gemini API error: {str(e)}")
            return []


# ✅ Main Processing Logic
if process_button and pdf_file and vendor_file:
    vendor_list = load_vendor_list(vendor_file)

    with st.spinner("⏳ Extracting text..."):
        text_pages = extract_text_from_pdf(pdf_file) if ai_model == "DeepSeek" else extract_text_from_pdf(pdf_file)  # Gemini should also process per page

    all_transactions = []
    progress_bar = st.progress(0)

    for i, page_text in enumerate(text_pages):
        st.info(f"📄 Processing Page {i + 1} of {len(text_pages)}...")
        transactions = process_and_categorize(page_text, vendor_list, api_key, ai_model)
        all_transactions.extend(transactions)  # Append transactions from each page
        progress_bar.progress((i + 1) / len(text_pages))

    if all_transactions:
        st.session_state.transactions = pd.DataFrame(all_transactions)
        st.success("✅ Transactions extracted & categorized successfully!")

# ✅ Ensure transactions exist in session state
if "transactions" not in st.session_state:
    st.session_state.transactions = None

# ✅ Display Transactions (Persistent)
if st.session_state.transactions is not None and not st.session_state.transactions.empty:
    df = st.session_state.transactions

    # ✅ Styled Transactions Table
    st.markdown("<h4 style='color: #1976D2; font-weight: bold;'>📋 Processed Transactions</h4>", unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)

    # ✅ Feedback Section
    st.markdown("<hr style='border: 1px solid #ddd;'>", unsafe_allow_html=True)
    st.markdown("<h5 style='color: #444;'>📝 Provide Feedback</h5>", unsafe_allow_html=True)

    selected_desc = st.selectbox("Select a Transaction to Correct", df["Description"].unique(), help="Choose a transaction from the list")

    # Retrieve selected transaction details
    filtered_row = df[df["Description"] == selected_desc].iloc[0]

    # Editable Fields
    correct_vendor = st.text_input("Correct Vendor", filtered_row["Vendor Name"], help="Enter the correct vendor name")
    correct_deposits = st.number_input("Deposits_Credits", value=float(filtered_row["Deposits_Credits"]), step=0.01, help="Update deposit amount if incorrect")
    correct_withdrawals = st.number_input("Withdrawals_Debits", value=float(filtered_row["Withdrawals_Debits"]), step=0.01, help="Update withdrawal amount if incorrect")
    comments = st.text_area("Additional Comments (Optional)", help="Provide any additional feedback")

    # ✅ Columns for Buttons (Side-by-Side Layout)
    col1, col2 = st.columns([1, 1.2])  # Adjusted width for better alignment

    with col1:
        submit_feedback = st.button("✅ Submit Feedback", help="Submit your feedback")

    with col2:
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇ Download CSV", csv_data, "transactions.csv", "text/csv", help="Download the updated transactions")

    # ✅ Feedback Submission Logic
    if submit_feedback:
        feedback_entry = [[datetime.date.today(), selected_desc, correct_vendor, filtered_row["Vendor Name"], correct_deposits, correct_withdrawals, comments]]
        save_feedback(feedback_entry)

        # Update Transactions in Session State
        df.loc[df["Description"] == selected_desc, ["Vendor Name", "Deposits_Credits", "Withdrawals_Debits"]] = correct_vendor, correct_deposits, correct_withdrawals
        st.session_state.transactions = df

        st.success("✅ Feedback submitted successfully!")

# else:
#     st.info("📢 No transactions available. Please process a document first.")
