import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io
import warnings
warnings.filterwarnings('ignore')

# Configure the page
st.set_page_config(
    page_title="FIFO Work Order Processor",
    page_icon="🏭",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        color: #2e86ab;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 15px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 15px;
        margin: 10px 0;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 5px;
        padding: 15px;
        margin: 10px 0;
    }
    .dataframe {
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

def parse_excel_file(uploaded_file):
    """Parse the uploaded Excel file and extract work order data"""
    try:
        # Read the Excel file
        df = pd.read_excel(uploaded_file, sheet_name='Feuil1', header=3)
        
        # Clean column names
        df.columns = [str(col).strip().replace('\n', ' ') for col in df.columns]
        
        # Remove empty rows
        df = df.dropna(how='all')
        
        return df
    except Exception as e:
        st.error(f"Error parsing Excel file: {str(e)}")
        return None

def apply_fifo_logic(df):
    """Apply FIFO logic to the work order data"""
    try:
        # Convert DLUO to datetime for proper sorting
        df['DLUO'] = pd.to_datetime(df['DLUO'], errors='coerce', format='%d%m%Y')
        
        # Sort by Component and DLUO (FIFO - oldest first)
        df_sorted = df.sort_values(['Component', 'DLUO'], ascending=[True, True])
        
        return df_sorted
    except Exception as e:
        st.error(f"Error applying FIFO logic: {str(e)}")
        return df

def generate_work_order_summary(df):
    """Generate a summary of the work order"""
    if df.empty:
        return None
    
    summary = {
        'Production_Ticket_Nr': df['Production Ticket Nr'].iloc[0],
        'Wording': df['Wording'].iloc[0],
        'Product_Code': df['Product Code'].iloc[0],
        'Batch_Nr': df['Batch Nr'].iloc[0],
        'Manager': df['Manager'].iloc[0],
        'Quantity_Launched': df['Quantity launched Theoretical'].iloc[0],
        'Start_Date': df['Current date marked the beginning'].iloc[0],
        'Total_Components': df['Component'].nunique(),
        'Total_Rows': len(df)
    }
    
    return summary

def calculate_component_requirements(df):
    """Calculate component requirements and availability"""
    component_summary = df.groupby(['Component', 'Description']).agg({
        'Quantity required': 'first',
        'Available Quantity': 'sum',
        'Batch Nr': 'count',
        'DLUO': 'min'
    }).reset_index()
    
    component_summary['Sufficient_Stock'] = component_summary['Available Quantity'] >= component_summary['Quantity required']
    component_summary['Shortage'] = component_summary['Quantity required'] - component_summary['Available Quantity']
    component_summary['Shortage'] = component_summary['Shortage'].apply(lambda x: max(0, x))
    
    return component_summary

def generate_picking_list(df):
    """Generate FIFO-based picking list"""
    picking_list = df[[
        'Component', 'Description', 'Batch Nr', 'DLUO', 
        'Available Quantity', 'Quantity required', 'Warehouse Stock',
        'depot location', 'Build', 'Zone', 'Location Description'
    ]].copy()
    
    # Mark priority items (oldest DLUO first)
    picking_list['DLUO_Rank'] = picking_list.groupby('Component')['DLUO'].rank(method='first')
    picking_list['Priority'] = picking_list['DLUO_Rank'] == 1
    
    return picking_list

def main():
    st.markdown('<div class="main-header">🏭 FIFO Work Order Processor</div>', unsafe_allow_html=True)
    
    # Sidebar for file upload and settings
    with st.sidebar:
        st.header("📁 File Upload")
        uploaded_file = st.file_uploader("Upload Excel Work Order", type=['xlsx', 'xls'])
        
        st.header("⚙️ Settings")
        show_raw_data = st.checkbox("Show Raw Data", value=False)
        show_picking_list = st.checkbox("Show Picking List", value=True)
        show_shortages = st.checkbox("Show Stock Shortages", value=True)
        
        st.header("ℹ️ About")
        st.info("""
        This app processes work orders using FIFO (First-In-First-Out) logic:
        - Sorts components by expiration date (DLUO)
        - Generates optimized picking lists
        - Identifies stock shortages
        - Provides production insights
        """)
    
    # Main content area
    if uploaded_file is not None:
        # Parse the uploaded file
        df = parse_excel_file(uploaded_file)
        
        if df is not None and not df.empty:
            # Display basic file info
            st.markdown('<div class="section-header">📊 Work Order Overview</div>', unsafe_allow_html=True)
            
            # Generate and display summary
            summary = generate_work_order_summary(df)
            if summary:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Production Ticket", summary['Production_Ticket_Nr'])
                    st.metric("Product Code", summary['Product_Code'])
                with col2:
                    st.metric("Wording", summary['Wording'])
                    st.metric("Batch Number", summary['Batch_Nr'])
                with col3:
                    st.metric("Manager", summary['Manager'])
                    st.metric("Quantity", f"{summary['Quantity_Launched']:,}")
                with col4:
                    st.metric("Components", summary['Total_Components'])
                    st.metric("Start Date", summary['Start_Date'])
            
            # Apply FIFO logic
            st.markdown('<div class="section-header">🔄 Applying FIFO Logic</div>', unsafe_allow_html=True)
            df_fifo = apply_fifo_logic(df)
            
            if not df_fifo.empty:
                st.success("✅ FIFO logic applied successfully! Components sorted by expiration date (DLUO).")
                
                # Display component requirements
                st.markdown('<div class="section-header">📦 Component Requirements</div>', unsafe_allow_html=True)
                component_summary = calculate_component_requirements(df_fifo)
                
                # Display stock status
                total_components = len(component_summary)
                sufficient_stock = component_summary['Sufficient_Stock'].sum()
                shortages = total_components - sufficient_stock
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Components", total_components)
                with col2:
                    st.metric("Sufficient Stock", sufficient_stock)
                with col3:
                    st.metric("Shortages", shortages, delta=f"-{shortages}")
                
                # Show shortages if any
                if show_shortages and shortages > 0:
                    shortage_df = component_summary[component_summary['Sufficient_Stock'] == False]
                    if not shortage_df.empty:
                        st.markdown('<div class="warning-box">⚠️ Stock Shortages Detected</div>', unsafe_allow_html=True)
                        st.dataframe(shortage_df[['Component', 'Description', 'Quantity required', 'Available Quantity', 'Shortage']])
                
                # Generate and display picking list
                if show_picking_list:
                    st.markdown('<div class="section-header">📋 FIFO Picking List</div>', unsafe_allow_html=True)
                    picking_list = generate_picking_list(df_fifo)
                    
                    # Add color coding for priority items
                    def highlight_priority(row):
                        if row['Priority']:
                            return ['background-color: #fff3cd'] * len(row)
                        return [''] * len(row)
                    
                    styled_picking_list = picking_list.style.apply(highlight_priority, axis=1)
                    st.dataframe(styled_picking_list, use_container_width=True)
                    
                    # Download button for picking list
                    csv = picking_list.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Picking List (CSV)",
                        data=csv,
                        file_name=f"picking_list_{summary['Production_Ticket_Nr']}.csv",
                        mime="text/csv"
                    )
                
                # Show raw data if requested
                if show_raw_data:
                    st.markdown('<div class="section-header">📄 Raw Data</div>', unsafe_allow_html=True)
                    st.dataframe(df_fifo, use_container_width=True)
            
            else:
                st.error("No data available after applying FIFO logic.")
        
        else:
            st.error("Could not parse the Excel file or file is empty.")
    
    else:
        # Demo mode with sample data structure
        st.markdown('<div class="section-header">📋 Expected Excel File Format</div>', unsafe_allow_html=True)
        
        # Display expected columns based on the provided file
        expected_columns = [
            "Production Ticket Nr", "Wording", "Product Code", "Batch Nr", "Manager",
            "Quantity launched Theoretical", "Current date marked the beginning", "Component",
            "Description", "Batch Nr", "DLUO", "Quantity required", "Available Quantity",
            "Quantity in stock", "In waiting Quantity", "Rejected Quantity", "Reserved Quantity",
            "Warehouse Stock", "depot location", "Build", "Zone", "Location Description"
        ]
        
        st.info("""
        **Expected Excel Format:**
        - File should have the same structure as your provided WO 00000086.xlsx
        - Data should start from row 4 (after headers)
        - Required columns include production details, components, quantities, and location information
        """)
        
        # Create sample data for demonstration
        st.markdown('<div class="section-header">🎯 How It Works</div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("1. Upload")
            st.write("Upload your Excel work order file with component data")
        
        with col2:
            st.subheader("2. FIFO Processing")
            st.write("System automatically sorts components by expiration date (DLUO)")
        
        with col3:
            st.subheader("3. Generate Lists")
            st.write("Get optimized picking lists and stock analysis")

if __name__ == "__main__":
    main()
