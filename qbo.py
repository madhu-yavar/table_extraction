import streamlit as st
import pandas as pd
import json
import re
from datetime import datetime
from PyPDF2 import PdfReader
from io import BytesIO
from langchain_google_genai import ChatGoogleGenerativeAI

gemini_api_key = ".."  # Replace with your actual API key


# App title and description
st.title("Wells Fargo Statement Processor")
st.markdown("Upload your bank statement PDF and reference files to get categorized transactions.")

# File upload section
st.sidebar.header("Upload Files")
pdf_file = st.sidebar.file_uploader("Bank Statement PDF", type=["pdf"])
vendor_file = st.sidebar.file_uploader("Vendor List (Excel)", type=["xls", "xlsx"])
chart_file = st.sidebar.file_uploader("Chart of Accounts (Excel)", type=["xls", "xlsx"])

def extract_raw_text(pdf_content):
    """Extracts text from PDF content (BytesIO)"""
    try:
        reader = PdfReader(pdf_content)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

def extract_json(s):
    """Extracts and fixes incomplete JSON arrays from Gemini response."""
    try:
        s = re.sub(r'```json\s*', '', s)
        s = re.sub(r'\s*```\s*', '', s)
        start = s.find('[')
        end = s.rfind(']') + 1
        if start == -1 or end == 0:
            return None
        json_str = s[start:end]
        if not json_str.strip().endswith(']'):
            json_str += ']'
        json_str = re.sub(r',\s*]', ']', json_str)
        json_str = re.sub(r',\s*}', '}', json_str)
        return json_str
    except Exception as e:
        st.error(f"JSON extraction error: {str(e)}")
        return None

def extract_transactions(text):
    """Extracts basic transaction details (Step 1)."""
    prompt = f"""
    Analyze this Wells Fargo bank statement text and extract transactions.
    Return a JSON array of objects with these EXACT keys:
    [
        {{
            "Date": "MM/DD/YYYY",
            "Description": "transaction details",
            "Deposits_Credits": number (0 if empty),
            "Withdrawals_Debits": number (0 if empty)
        }}
    ]

         Example:
    ```json
     [
       {{
            "Date": "11/01/2023",
            "Description": "Overdraft Fee for Transaction",
            "Deposits_Credits": 0,
            "Withdrawals_Debits": 35.00,

        }},
        {{
            "Date": "11/01/2023",
            "Description": "ATM Cash Deposit",
            "Deposits_Credits": 600.00,
            "Withdrawals_Debits": 0,

        }}
    ]
    Statement Text:
    {text[:15000]}
    """
    # try:
    #     gemini = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", google_api_key=gemini_api_key, temperature=0)
    #     response = gemini.invoke(prompt)
    #     json_data = response.content.strip()
    #     clean_json = extract_json(json_data)
    #     return pd.DataFrame(json.loads(clean_json)) if clean_json else pd.DataFrame()
    
    # except Exception as e:
    #     st.error(f"Transaction extraction failed: {str(e)}")
    #     return pd.DataFrame()

    try:
        gemini = ChatGoogleGenerativeAI(model="gemini-2.0-pro-exp-02-05", google_api_key=gemini_api_key, temperature=0)
        response = gemini.invoke(prompt)
        json_data = response.content.strip()
        clean_json = extract_json(json_data)
        df = pd.DataFrame(json.loads(clean_json)) if clean_json else pd.DataFrame()

        # Clean data
        numeric_cols = ['Deposits_Credits', 'Withdrawals_Debits']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
        df['Amount'] = df['Deposits_Credits'] - df['Withdrawals_Debits']

        # Date formatting
        df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')
        df = df[df['Date'].notna()]
        df['Date'] = df['Date'].dt.strftime('%m/%d/%Y')

        return df[['Date', 'Description', 'Amount', 'Deposits_Credits', 'Withdrawals_Debits']]
    except Exception as e:
        st.error(f"Transaction extraction failed: {str(e)}")
        return pd.DataFrame()

def classify_transactions(transactions_df, vendor_df, chart_df):
    """Classifies Vendor Name and Account for extracted transactions (Step 2)."""
    if transactions_df.empty:
        return transactions_df
    vendor_list = "\n".join([f"- {vendor}" for vendor in vendor_df['Payee'].dropna().unique()])
    chart_of_accounts = "\n".join([f"- {acc}" for acc in chart_df['Account'].unique()])


    prompt = f"""
    Understand the descriptions in transaction statement and match it with Exact account and vendor as per the list. 
    Stictly take the data from the {vendor_list} and {chart_of_accounts}. 
    Do not give the Description as such in the Vendor List and Accounts.
    Do not assume and write any vendors.

    Use this Vendor List:
    {vendor_list}
    Use this Chart of Accounts:
    {chart_of_accounts}
    Return a JSON array of objects with these EXACT keys:
    [
        {{
            "Description": "transaction details",
            "Vendor Name": "vendor name from Vendor List only",
            "Account": "account name from Chart of Accounts only"
        }}
    ]

    Rules:

    1. Match vendors and accounts EXACTLY to the provided lists
    2. If a vendor or account is not found in the provided lists, use "Unknown" for Vendor Name and "Other Expenses" for Account

     Example:
    ```json
     [
       {{
            "Description": "Overdraft Fee for Transaction",
            "Vendor Name": "Overdraft Fee",
            "Account": "Bank Charges & Fees"
        }},
        {{
            "Description": "ATM Cash Deposit",
            "Vendor Name": "ATM",
            "Account": "Cash on hand"
        }}
    ]
    Transactions:
    {transactions_df[['Description']].to_json(orient='records')}
    """
    try:
        gemini = ChatGoogleGenerativeAI(model="gemini-2.0-pro-exp-02-05", google_api_key=gemini_api_key, temperature=0)
        response = gemini.invoke(prompt)
        json_data = response.content.strip()
        clean_json = extract_json(json_data)
        classified_data = pd.DataFrame(json.loads(clean_json)) if clean_json else pd.DataFrame()
        return transactions_df.merge(classified_data, on='Description', how='left')
    except Exception as e:
        st.error(f"Classification failed: {str(e)}")
        return transactions_df

if pdf_file and vendor_file and chart_file:
    with st.spinner('Processing your files...'):
        try:
            pdf_content = pdf_file.read()
            vendor_df = pd.read_excel(vendor_file)
            chart_df = pd.read_excel(chart_file)
            raw_text = extract_raw_text(BytesIO(pdf_content))
            transactions_df = extract_transactions(raw_text)
            transactions_df = classify_transactions(transactions_df, vendor_df, chart_df)
            if not transactions_df.empty:
                st.dataframe(transactions_df)
                csv = transactions_df.to_csv(index=False).encode('utf-8')
                st.download_button("Download CSV", data=csv, file_name="classified_transactions.csv", mime="text/csv")
            else:
                st.error("No transactions found.")
        except Exception as e:
            st.error(f"Processing error: {str(e)}")
else:
    st.info("Please upload all three files to begin processing")

