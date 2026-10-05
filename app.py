import io
import json
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="OrderFlow AI", page_icon="📦", layout="wide")

# --- DATA SCHEMA FOR STRUCTURED OUTPUT ---
class OrderItem(BaseModel):
    item_name: str = Field(description="Name or description of the product ordered")
    quantity: int = Field(description="Quantity ordered", default=1)
    unit_price: float = Field(description="Price per single item in PKR", default=0.0)

class ExtractedOrder(BaseModel):
    customer_name: str = Field(description="Full name of customer")
    phone_number: str = Field(description="Contact phone or mobile number")
    delivery_address: str = Field(description="Complete street, house, and city address")
    items: List[OrderItem] = Field(description="List of all products and quantities")
    payment_method: str = Field(description="COD, Bank Transfer, JazzCash, etc.", default="COD")
    notes: str = Field(description="Delivery landmarks or special requests", default="None")

# --- PDF GENERATOR ENGINE ---
# Helper to strip emojis and non-standard symbols that crash PDF generation
def clean_text(text) -> str:
    if not text:
        return ""
    return str(text).encode("ascii", "ignore").decode("ascii").strip()

# --- PDF GENERATOR ENGINE ---
def create_pdf_invoice(order_data: dict, order_id: str = "1001") -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Header Banner
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, 750, "ORDER INVOICE & DISPATCH SLIP")
    p.setFont("Helvetica", 10)
    payment_info = clean_text(order_data.get('payment_method', 'COD'))
    p.drawString(50, 735, f"Invoice #: ORD-{order_id}  |  Payment Mode: {payment_info}")
    p.line(50, 725, 550, 725)
    
    # Customer Details
    p.setFont("Helvetica-Bold", 11)
    p.drawString(50, 700, "Customer Information:")
    p.setFont("Helvetica", 10)
    p.drawString(50, 685, f"Name: {clean_text(order_data.get('customer_name'))}")
    p.drawString(50, 670, f"Phone: {clean_text(order_data.get('phone_number'))}")
    p.drawString(50, 655, f"Address: {clean_text(order_data.get('delivery_address'))}")
    p.drawString(50, 640, f"Notes: {clean_text(order_data.get('notes', 'None'))}")
    
    # Line Items Table Header
    y = 605
    p.line(50, y + 15, 550, y + 15)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y, "Item Description")
    p.drawString(320, y, "Qty")
    p.drawString(390, y, "Price (PKR)")
    p.drawString(480, y, "Subtotal (PKR)")
    p.line(50, y - 8, 550, y - 8)
    
    # Line Items Rows
    y -= 25
    p.setFont("Helvetica", 10)
    total_bill = 0.0
    for item in order_data.get("items", []):
        unit_price = float(item.get("unit_price", 0.0))
        qty = int(item.get("quantity", 1))
        subtotal = qty * unit_price
        total_bill += subtotal
        
        item_title = clean_text(item.get("item_name", ""))[:35]
        p.drawString(50, y, item_title)
        p.drawString(325, y, str(qty))
        p.drawString(390, y, f"{unit_price:,.2f}")
        p.drawString(480, y, f"{subtotal:,.2f}")
        y -= 20
    
    # Total Calculation
    p.line(50, y, 550, y)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y - 25, f"Total Due: PKR {total_bill:,.2f}")
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer.getvalue()

# --- USER INTERFACE ---
st.title("📦 WhatsApp Order-to-Invoice Automation Engine")
st.caption("Parses unstructured chats into structured order data and ready-to-print dispatch labels.")

# Sidebar for Setup
with st.sidebar:
    st.header("⚙️ Configuration")
    # Safely load from secrets if present, otherwise default to empty string
    default_key = ""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            default_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    # Sidebar input so anyone without secrets.toml can paste their key
    api_key = st.text_input(
        "Gemini API Key",
        value=default_key,
        type="password",
        help="Get a free key from https://aistudio.google.com"
    )
    st.markdown("Get your key at [Google AI Studio](https://aistudio.google.com/).")

    order_id_input = st.text_input("Order Reference #:", value="1001")

# Main Interface Split into Two Columns
col_input, col_output = st.columns([1, 1], gap="medium")

with col_input:
    st.subheader("1. Raw Chat Message")
        # Replaces default_text with a clean placeholder so the box starts empty
    raw_message = st.text_area(
        "Paste unstructured text / WhatsApp message:",
        placeholder="Paste your WhatsApp order message here...",
        height=180
    )
    process_btn = st.button("🚀 Process & Generate Invoice", type="primary")

with col_output:
    st.subheader("2. Structured Order & Receipt")
    
    # The API will ONLY run when you actually click the button:
    if process_btn:
           # The API will ONLY run when you actually click the button:
        if not api_key:
            st.error("⚠️ Please enter a Gemini API Key in the sidebar to proceed.")
        elif not raw_message.strip():
            st.warning("Please paste or type an order message first!")
        else:
            with st.spinner("Analyzing message with AI..."):
                import time
                target_model = "gemini-3.8-flash"
                max_retries = 2
                
                for attempt in range(max_retries):
                    try:
                        client = genai.Client(api_key=api_key)
                        response = client.models.generate_content(
                            model=target_model,
                            contents=f"Extract all order information from this customer message. Do NOT include any emojis or special characters in the output values:\n\n{raw_message}",
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=ExtractedOrder,
                                temperature=0.0
                            )
                        )
                        parsed_order = json.loads(response.text)
                        st.session_state["parsed_order"] = parsed_order
                        st.success("Order parsed successfully!")
                        break
                    except Exception as e:
                        err_msg = str(e)
                        if "503" in err_msg and attempt < max_retries - 1:
                            time.sleep(10)
                            continue
                        else:
                            st.error(f"Error processing order: {err_msg}")
                            break
    if "parsed_order" in st.session_state:
        order = st.session_state["parsed_order"]
        
        # Display extracted fields cleanly
        st.markdown(f"**Customer:** {order.get('customer_name')}")
        st.markdown(f"**Phone:** {order.get('phone_number')}")
        st.markdown(f"**Address:** {order.get('delivery_address')}")
        st.markdown(f"**Payment:** {order.get('payment_method')}")
        
        # Display items table
        st.table(order.get("items", []))
        
        # Generate and provide download button for PDF
        pdf_data = create_pdf_invoice(order, order_id=order_id_input)
        st.download_button(
            label="📄 Download Ready-to-Print Invoice (PDF)",
            data=pdf_data,
            file_name=f"Invoice_ORD_{order_id_input}.pdf",
            mime="application/pdf",
            use_container_width=True
        )