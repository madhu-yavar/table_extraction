import streamlit as st
import requests
import json
import pdfplumber
import pandas as pd
from io import BytesIO


API_URL = "https://api.deepseek.com/v1/chat/completions"  

# ✅ Set Streamlit Page Layout
st.set_page_config(page_title="GKM- QBO - Statement Processor", page_icon="📄", layout="wide")


# ✅ Add Custom Logo
logo_path = "/Users/yavar/Desktop/EDA BOT/yavarlogo.png"
st.image(logo_path, width=80)  # Increased size for better visibility

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



# ✅ App Title & Disclaimer
st.markdown("""
    <style>
        .title-container {
            text-align: center;
            padding: 10px 0;
        }
        .title {
            font-size: 34px;
            font-weight: bold;
            color: #004AAD; /* Professional Dark Blue */
            text-shadow: 2px 2px 3px rgba(0, 0, 0, 0.2);
            margin-bottom: 3px;
        }
        .tagline {
            font-size: 13px;
            font-weight: 400;
            color: #666; /* Lighter Gray for Subtle Look */
            font-style: italic;
            margin-top: 3px;
        }
        .divider {
            width: 80px;
            height: 3px;
            background: linear-gradient(to right, #004AAD, #1976D2);
            margin: 5px auto;
            border-radius: 6px;
        }
    </style>
    
    <div class="title-container">
        <h1 class="title">GKM- QBO - Statement Processor</h1>
        <div class="divider"></div>
        <p class="tagline">Extract & categorize transactions with AI</p>
    </div>
""", unsafe_allow_html=True)



st.markdown("""
    <style>
        .custom-warning {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 12px;
            background-color: #FFDADA; /* Light Red Background */
            color: #8B0000; /* Dark Red Text */
            font-size: 15px;
            font-weight: 600;
            border-radius: 8px;
            border-left: 6px solid #D32F2F; /* Strong Red Accent */
            text-align: center;
            margin: 15px 0;
            box-shadow: 0px 2px 6px rgba(0, 0, 0, 0.1);
        }
        .warning-icon {
            font-size: 18px;
            margin-right: 10px;
        }
    </style>
    
    <div class="custom-warning">
        <span class="warning-icon">⚠️</span> 
        <span>Please <b>mask any Personally Identifiable Information (PII)</b> before uploading the PDF.</span>
    </div>
""", unsafe_allow_html=True)



st.markdown("""
    <div style="height: 4px; 
                background: linear-gradient(to right, #1976D2, #32CD32, #FFA500, #FF4500);
                margin-top: 10px; margin-bottom: 10px;">
    </div>
""", unsafe_allow_html=True)

# ✅ DeepSeek API Configuration

# ✅ Sidebar API Key Input
st.sidebar.markdown("<div class='sidebar-title'>🔑 Enter DeepSeek API Key</div>", unsafe_allow_html=True)
API_KEY = st.sidebar.text_input("API Key", type="password", help="Enter your DeepSeek API key securely.")

# ✅ Store API Key in Session State
if API_KEY:
    st.session_state["API_KEY"] = API_KEY
elif "API_KEY" in st.session_state:
    API_KEY = st.session_state["API_KEY"]
else:
    st.sidebar.warning("⚠️ Please enter your DeepSeek API key.")

# ✅ Sidebar Styling (Ensures Proper Alignment & Modern Look)
st.sidebar.markdown("""
    <style>
        /* Sidebar Title */
        .sidebar-title {
            font-size: 20px;
            font-weight: bold;
            color: white;
            background-color: #1976D2;
            padding: 12px;
            text-align: center;
            border-radius: 8px;
            margin-bottom: 10px;
        }

        /* Upload Box */
        .upload-box {
            border: 2px dashed #1976D2;
            padding: 15px;
            border-radius: 8px;
            background-color: #ffffff;
            text-align: center;
            font-size: 16px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }

        /* Process Button */
        .stButton>button {
            background-color: #1976D2;
            color: white;
            font-size: 18px;
            font-weight: bold;
            padding: 10px;
            border-radius: 8px;
            width: 100%;
            text-align: center;
            border: none;
        }
        .stButton>button:hover {
            background-color: #0D47A1;
        }

    </style>
""", unsafe_allow_html=True)



# ✅ Sidebar Title
st.sidebar.markdown("<div class='sidebar-title'>📂 Upload Your Files</div>", unsafe_allow_html=True)

# 📄 PDF Upload Box
st.sidebar.markdown("<div class='upload-box'>📄 Upload a PDF Bank Statement</div>", unsafe_allow_html=True)
pdf_file = st.sidebar.file_uploader("", type=["pdf"], key="pdf_upload", label_visibility="collapsed")

# 📂 Vendor List Upload Box
st.sidebar.markdown("<div class='upload-box'>📂 Upload a Vendor List (CSV or Excel)</div>", unsafe_allow_html=True)
vendor_file = st.sidebar.file_uploader("", type=["csv", "xls", "xlsx"], key="vendor_upload", label_visibility="collapsed")

# ✅ Process Button (Modern Look)
process_button = st.sidebar.button("🚀 Process Document")


# ✅ Session State for Persisting Transactions
if "transactions" not in st.session_state:
    st.session_state.transactions = None

# ✅ Extract Text from PDF
def extract_text_from_pdf(pdf_file):
    """Extracts text from each page of a PDF file and returns a list of pages."""
    text_pages = []
    with pdfplumber.open(BytesIO(pdf_file.read())) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_pages.append(text.strip())  # Store cleaned text per page
    return text_pages

# ✅ Process and Categorize Transactions

def process_and_categorize(text, vendor_list):
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

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "stream": False
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        try:
            json_data = response.json()["choices"][0]["message"]["content"]
            json_data = json_data.strip("```json").strip("```")  # Clean markdown artifacts
            return json.loads(json_data)  # Convert to Python list
        except Exception as e:
            st.error(f"❌ Error processing DeepSeek response: {e}")
            return []
    else:
        st.error(f"❌ API call failed: {response.status_code} - {response.text}")
        return []




# ✅ Load Vendor List
def load_vendor_list(vendor_file):
    """Loads vendor list from CSV or Excel and returns a list."""
    if vendor_file.name.endswith(".csv"):
        return pd.read_csv(vendor_file)["Payee"].tolist()
    else:
        return pd.read_excel(vendor_file)["Payee"].tolist()

# ✅ Feedback Collection
def save_feedback(feedback_data):
    feedback_file = "feedback_log.csv"
    df_feedback = pd.DataFrame(feedback_data, columns=["Date", "Description", "Correct Vendor", "AI Vendor", "Comments"])
    if os.path.exists(feedback_file):
        df_feedback.to_csv(feedback_file, mode='a', header=False, index=False)
    else:
        df_feedback.to_csv(feedback_file, index=False)

# ✅ Main Processing Logic
if process_button and pdf_file:
    with st.spinner("⏳ Extracting text from PDF..."):
        text_pages = extract_text_from_pdf(pdf_file)  # Extract each page separately

    all_transactions = []  # Store transactions from all pages
    if text_pages:
        progress_bar = st.progress(0)
        vendor_list = load_vendor_list(vendor_file) if vendor_file else []

        for i, page_text in enumerate(text_pages):
            st.markdown(f"""
                    <div style="
                        padding: 8px; 
                        background-color: #f1f3f4; /* Light Gray Background */
                        color: #333; /* Dark Gray Text */
                        font-size: 15px; 
                        font-weight: 500; 
                        border-radius: 4px;
                        text-align: center;
                        margin: 10px 0;">
                        📄 Processing Page {i + 1} of {len(text_pages)}...
                    </div>
                """, unsafe_allow_html=True)

            transactions = process_and_categorize(page_text, vendor_list)  # Process & categorize
            all_transactions.extend(transactions)  # Merge results
            progress_bar.progress((i + 1) / len(text_pages))

        if all_transactions:
            st.success("✅ Transactions extracted & categorized successfully!")

            # Store Transactions in Session State
            st.session_state.transactions = pd.DataFrame(all_transactions)

# ✅ Display Transactions (Persistent)
# # ✅ Display Transactions (Persistent)
if st.session_state.transactions is not None:
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
    correct_deposits = st.number_input("Deposits_Credits", value=filtered_row["Deposits_Credits"], step=0.01, help="Update deposit amount if incorrect")
    correct_withdrawals = st.number_input("Withdrawals_Debits", value=filtered_row["Withdrawals_Debits"], step=0.01, help="Update withdrawal amount if incorrect")
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
