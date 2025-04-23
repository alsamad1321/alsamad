import streamlit as st
import qrcode
from PIL import Image, ImageDraw
import io
import base64
import os
import tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from datetime import datetime
import pandas as pd
import uuid
from pathlib import Path
import time
import ast

# Create necessary directories if they don't exist
TEMP_DIR = Path(tempfile.gettempdir()) / "hall_ticket_system"
TEMP_DIR.mkdir(exist_ok=True)
ASSETS_DIR = Path("assets")
ASSETS_DIR.mkdir(exist_ok=True)

# Load or create a database for student records
def load_database():
    try:
        db_path = ASSETS_DIR / "student_database.csv"
        if db_path.exists():
            return pd.read_csv(db_path)
        else:
            # Create an empty dataframe with the required columns
            df = pd.DataFrame(columns=[
                'id', 'name', 'roll_number', 'program', 'semester', 
                'exam_date', 'seat_number', 'hall_ticket_id', 'subjects'
            ])
            df.to_csv(db_path, index=False)
            return df
    except Exception as e:
        st.error(f"Error loading database: {str(e)}")
        # Return empty DataFrame as fallback
        return pd.DataFrame(columns=[
            'id', 'name', 'roll_number', 'program', 'semester', 
            'exam_date', 'seat_number', 'hall_ticket_id', 'subjects'
        ])

# Save student record to database
def save_to_database(student_data):
    try:
        db_path = ASSETS_DIR / "student_database.csv"
        df = load_database()
        
        # Check if the student already exists
        if not df[df['roll_number'] == student_data['roll_number']].empty:
            df = df[df['roll_number'] != student_data['roll_number']]
        
        # Add the new record
        df = pd.concat([df, pd.DataFrame([student_data])], ignore_index=True)
        df.to_csv(db_path, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving to database: {str(e)}")
        return False

# New function to delete a student record from database
def delete_from_database(roll_number, hall_ticket_id):
    try:
        db_path = ASSETS_DIR / "student_database.csv"
        df = load_database()
        
        # Filter out the student with the matching roll number and hall ticket ID
        df = df[(df['roll_number'] != roll_number) | (df['hall_ticket_id'] != hall_ticket_id)]
        
        # Save the updated dataframe
        df.to_csv(db_path, index=False)
        
        # Delete the PDF file if it exists
        pdf_path = TEMP_DIR / f"hall_ticket_{roll_number}_{hall_ticket_id}.pdf"
        if pdf_path.exists():
            os.remove(pdf_path)
            
        return True
    except Exception as e:
        st.error(f"Error deleting record: {str(e)}")
        return False

# Function to generate a short URL (UUID) and map it to a hall ticket
def generate_hall_ticket_url(hall_ticket_id):
    # Instead of generating a URL that redirects to a website,
    # we'll create a direct download link that works when scanned
    
    # Generate a unique identifier for this hall ticket
    unique_id = str(uuid.uuid4())[:8].upper()
    
    # When the QR code is scanned, we'll use this format:
    return f"HALL_TICKET_ID:{hall_ticket_id}:{unique_id}"

# Fixed function to handle QR code scanning
def create_scannable_qr_data(hall_ticket_id, student_roll_number):
    """
    Creates QR code data that directly downloads the hall ticket PDF when scanned.
    """
    # Create a simple format that includes both required pieces of information
    # This will be used by the download page to look up the hall ticket
    return f"{hall_ticket_id}:{student_roll_number}"

# Function to generate QR code
def generate_qr_code(data, size=200):
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # Higher error correction
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Resize the QR code
        img = img.resize((size, size))
        
        return img
    except Exception as e:
        st.error(f"Error generating QR code: {str(e)}")
        # Create a blank image as a fallback
        return Image.new('RGB', (size, size), color='white')

# Function to get binary PDF data for download
def get_binary_file_downloader_html(bin_file, file_label='File'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(bin_file)}" class="download-button">{file_label}</a>'
    return href

# Function to create download link
def get_download_link(file_path, link_text="Download File"):
    try:
        return get_binary_file_downloader_html(file_path, link_text)
    except Exception as e:
        st.error(f"Error creating download link: {str(e)}")
        return "Download link could not be created."

# Function to generate hall ticket PDF
def generate_hall_ticket_pdf(student_data):
    try:
        # Create a unique filename for the PDF
        filename = f"hall_ticket_{student_data['roll_number']}_{student_data['hall_ticket_id']}.pdf"
        file_path = TEMP_DIR / filename
        
        # Create the PDF
        c = canvas.Canvas(str(file_path), pagesize=A4)
        width, height = A4
        
        # Add a border to the page
        c.setStrokeColor(colors.black)
        c.setLineWidth(2)
        c.rect(1*cm, 1*cm, width-2*cm, height-2*cm, stroke=1, fill=0)
        
        # Add header
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height-2*cm, "GODAVARI INSTITUTE OF MANAGEMENT AND RESEARCH")
        
        # Add subtitle
        c.setFont("Helvetica", 14)
        c.drawCentredString(width/2, height-2.7*cm, "EXAMINATION HALL TICKET")
        
        # Add academic session
        current_year = datetime.now().year
        academic_session = f"Academic Session: {current_year}-{current_year+1}"
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, height-3.3*cm, academic_session)
        
        # Generate QR code with direct download data - FIXED FORMAT
        # Simply include both hall ticket ID and roll number separated by a colon
        qr_data = create_scannable_qr_data(student_data['hall_ticket_id'], student_data['roll_number'])
        qr_img = generate_qr_code(qr_data)
        
        # Save QR code to a temporary file
        qr_path = TEMP_DIR / f"qr_{student_data['roll_number']}.png"
        qr_img.save(qr_path)
        
        # Place QR code on the PDF - Moved to right side
        try:
            c.drawImage(str(qr_path), width-4.5*cm, height-8*cm, width=3*cm, height=3*cm)
            
            # Add text under QR code explaining what it is
            c.setFont("Helvetica", 8)
            c.drawCentredString(width-3*cm, height-8.5*cm, "Scan to download")
            c.drawCentredString(width-3*cm, height-8.8*cm, "hall ticket")
        except Exception as e:
            st.warning(f"Could not add QR code to PDF: {str(e)}")
        
        # Add student information
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2*cm, height-5*cm, "STUDENT INFORMATION")
        
        c.setFont("Helvetica", 10)
        y_position = height-5.5*cm
        
        # Student details in two columns
        details = [
            ("Name:", student_data['name']),
            ("Roll Number:", student_data['roll_number']),
            ("Program:", student_data['program']),
            ("Semester:", student_data['semester']),
            ("Exam Date:", student_data['exam_date']),
            ("Seat Number:", student_data['seat_number']),
            ("Hall Ticket ID:", student_data['hall_ticket_id'])
        ]
        
        for label, value in details:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(2*cm, y_position, label)
            c.setFont("Helvetica", 10)
            c.drawString(5*cm, y_position, str(value))
            y_position -= 0.7*cm
        
        # Add exam details section
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2*cm, y_position-0.5*cm, "EXAMINATION DETAILS")
        
        y_position -= 1.2*cm
        
        # Check if subjects exist in the data
        subjects = student_data.get('subjects', [])
        if isinstance(subjects, str):
            # If subjects is a string (saved from database), convert it to list
            try:
                subjects = ast.literal_eval(subjects)
            except:
                # If conversion fails, treat it as a comma-separated string
                subjects = [s.strip() for s in subjects.split(',') if s.strip()]
        
        if not subjects:
            c.setFont("Helvetica", 10)
            c.drawString(2*cm, y_position, "No examination subjects specified.")
            y_position -= 0.7*cm
        else:
            # Table headers
            c.setFont("Helvetica-Bold", 10)
            c.drawString(2*cm, y_position, "Subject Code")
            c.drawString(6*cm, y_position, "Subject Name")
            c.drawString(13*cm, y_position, "Date")
            y_position -= 0.5*cm
            
            # Draw a line under headers
            c.line(2*cm, y_position-0.1*cm, width-2*cm, y_position-0.1*cm)
            y_position -= 0.4*cm
            
            # List all subjects with improved formatting
            c.setFont("Helvetica", 10)
            for subject in subjects:
                if isinstance(subject, dict):
                    # If subject is a dictionary with code, name, date
                    # Draw a rectangle for each row to improve readability
                    c.setFillColor(colors.lightgrey)
                    c.rect(2*cm, y_position-0.3*cm, width-4*cm, 0.6*cm, fill=1, stroke=0)
                    c.setFillColor(colors.black)
                    
                    # Write subject details
                    c.drawString(2*cm, y_position, subject.get('code', ''))
                    
                    # Limit subject name length to fit in allocated space
                    subject_name = subject.get('name', '')
                    if len(subject_name) > 40:
                        subject_name = subject_name[:37] + "..."
                    c.drawString(6*cm, y_position, subject_name)
                    
                    c.drawString(13*cm, y_position, subject.get('date', ''))
                else:
                    # If subject is just a string, put it in the name column
                    c.drawString(6*cm, y_position, str(subject))
                
                y_position -= 0.7*cm
                
                # Check if we need to start a new page for more subjects
                if y_position < 6*cm:
                    break
        
        # Add examination instructions
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2*cm, y_position-0.5*cm, "IMPORTANT INSTRUCTIONS")
        
        instructions = [
            "1. This hall ticket must be presented at the examination center.",
            "2. Candidates should be seated in the examination hall 15 minutes before the start of the examination.",
            "3. Mobile phones and electronic devices are strictly prohibited in the examination hall.",
            "4. Candidates are not allowed to leave the examination hall before the end of the examination.",
            "5. Unfair means during the examination will lead to disqualification."
        ]
        
        y_position -= 1.5*cm
        for instruction in instructions:
            c.setFont("Helvetica", 9)
            c.drawString(2*cm, y_position, instruction)
            y_position -= 0.5*cm
        
        # Add signature fields
        c.setFont("Helvetica", 10)
        c.drawString(2*cm, 4*cm, "Student's Signature")
        c.drawString(width-6*cm, 4*cm, "Examiner's Signature")
        
        # Add signature lines
        c.line(2*cm, 3.5*cm, 6*cm, 3.5*cm)
        c.line(width-6*cm, 3.5*cm, width-2*cm, 3.5*cm)
        
        # Add footer
        c.setFont("Helvetica", 8)
        c.drawCentredString(width/2, 2*cm, "This hall ticket is electronically generated and does not require a stamp.")
        c.drawCentredString(width/2, 1.7*cm, "Scan QR code to download this hall ticket directly")
        
        # Save the PDF
        c.save()
        
        # Clean up the temporary QR code file
        try:
            os.remove(qr_path)
        except:
            pass  # Ignore errors during cleanup
        
        return file_path
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        return None

def create_qr_download_endpoint():
    st.markdown("""
    <div class="section-container">
        <h2>Hall Ticket Download</h2>
        <p>Please enter your Hall Ticket ID and Roll Number to download your hall ticket.</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("download_form"):
        hall_ticket_id = st.text_input("Hall Ticket ID", placeholder="Enter your Hall Ticket ID")
        roll_number = st.text_input("Roll Number", placeholder="Enter your Roll Number")
        
        # Add a field for QR code data to handle direct scans
        qr_data = st.text_input("QR Code Data", placeholder="Leave blank if not scanning QR code", help="This field is automatically filled when scanning the QR code", key="qr_data")
        
        submit_button = st.form_submit_button("Download Hall Ticket")
    
    if submit_button:
        # Check if QR data is provided (from QR code scan)
        if qr_data:
            try:
                # Parse QR data (expected format: "hall_ticket_id:roll_number")
                hall_ticket_id, roll_number = qr_data.split(":")
                st.success(f"QR code data processed successfully. Hall Ticket ID: {hall_ticket_id}, Roll Number: {roll_number}")
            except:
                st.error("Invalid QR code data. Please enter your Hall Ticket ID and Roll Number manually.")
        
        if not hall_ticket_id or not roll_number:
            st.error("Please enter both Hall Ticket ID and Roll Number.")
            return
        
        try:
            # Find the student record
            df = load_database()
            student = df[(df['hall_ticket_id'] == hall_ticket_id) & (df['roll_number'] == roll_number)]
            
            if student.empty:
                st.error("No hall ticket found with the provided details.")
                return
            
            # Generate the hall ticket
            student_data = student.iloc[0].to_dict()
            pdf_path = generate_hall_ticket_pdf(student_data)
            
            if pdf_path:
                st.success("Hall Ticket found!")
                st.markdown(get_download_link(pdf_path, "Download Hall Ticket"), unsafe_allow_html=True)
            else:
                st.error("Could not generate the hall ticket. Please try again.")
        except Exception as e:
            st.error(f"Error: {str(e)}")

# Update the main function to include the new QR download endpoint
def main():
    try:
        # Set page config
        st.set_page_config(
            page_title="Hall Ticket Generation System",
            page_icon="🎓",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Custom CSS to improve UI
        st.markdown("""
        <style>
        .main {
            background-color: #f8f9fa;
        }
        .stApp {
            max-width: 1200px;
            margin: 0 auto;
        }
        .css-1d391kg {
            padding: 1rem 1rem 1rem;
        }
        .stTextInput > div > div > input, .stSelectbox > div > div > input {
            background-color: white;
        }
        h1, h2, h3 {
            color: #1e3a8a;
        }
        .header-container {
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #1e3a8a;
            color: white;
            padding: 1rem;
            border-radius: 5px;
            margin-bottom: 2rem;
        }
        .subheader {
            text-align: center;
            color: #4a5568;
            margin-bottom: 2rem;
        }
        .stButton>button {
            background-color: #1e3a8a;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            font-size: 1rem;
            border-radius: 5px;
            cursor: pointer;
            width: 100%;
        }
        .stButton>button:hover {
            background-color: #2d4eaa;
        }
        .download-link {
            text-align: center;
            margin-top: 1rem;
        }
        .download-button {
            display: inline-block;
            background-color: #1e3a8a;
            color: white;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            margin-top: 1rem;
            text-align: center;
            font-weight: bold;
        }
        .download-button:hover {
            background-color: #2d4eaa;
        }
        .delete-button {
            display: inline-block;
            background-color: #e53e3e;
            color: white;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            margin-top: 1rem;
            text-align: center;
            font-weight: bold;
        }
        .delete-button:hover {
            background-color: #c53030;
        }
        .success-message {
            background-color: #d1fae5;
            color: #065f46;
            padding: 1rem;
            border-radius: 5px;
            margin-top: 1rem;
        }
        .section-container {
            background-color: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 2rem;
        }
        .qr-info {
            background-color: #e6f7ff;
            padding: 1rem;
            border-radius: 5px;
            margin-top: 1rem;
            border-left: 4px solid #1890ff;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Header
        st.markdown('<div class="header-container"><h1>Hall Ticket Generation System</h1></div>', unsafe_allow_html=True)
        st.markdown('<p class="subheader">Godavari Institute of Management and Research</p>', unsafe_allow_html=True)
        
        # Sidebar for navigation
        with st.sidebar:
            st.markdown("### Navigation")
            page = st.radio("Select a page:", ["Generate Hall Ticket", "View Existing Hall Tickets", "Download Hall Ticket"])
        
        if page == "Generate Hall Ticket":
            st.markdown('<div class="section-container">', unsafe_allow_html=True)
            st.markdown("## Student Information")
            st.markdown("Please fill in the following details to generate a hall ticket.")
            
            # Create a form for student details
            with st.form("student_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    name = st.text_input("Full Name", placeholder="Enter student's full name")
                    roll_number = st.text_input("Roll Number", placeholder="Enter roll number")
                    program = st.selectbox("Program", [
                        "Bachelor of Business Administration (BBA)",
                        "Master of Business Administration (MBA)",
                        "Bachelor of Commerce (B.Com)",
                        "Master of Commerce (M.Com)",
                        "Bachelor of Computer Applications (BCA)",
                        "Master of Computer Applications (MCA)"
                    ])
                
                with col2:
                    semester = st.selectbox("Semester", ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"])
                    exam_date = st.date_input("Examination Date")
                    seat_number = st.text_input("Seat Number", placeholder="Enter seat number")
                
                # New section for subjects
                st.markdown("## Examination Subjects")
                
                # Dynamic subject input
                subjects = []
                num_subjects = st.number_input("Number of Subjects", min_value=1, max_value=10, value=3)
                
                for i in range(int(num_subjects)):
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        subject_code = st.text_input(f"Subject {i+1} Code", key=f"code_{i}", placeholder="e.g. CS101")
                    with col2:
                        subject_name = st.text_input(f"Subject {i+1} Name", key=f"name_{i}", placeholder="e.g. Introduction to Programming")
                    with col3:
                        subject_date = st.date_input(f"Subject {i+1} Exam Date", key=f"date_{i}")
                    
                    subjects.append({
                        'code': subject_code,
                        'name': subject_name,
                        'date': subject_date.strftime('%d-%m-%Y') if subject_date else ''
                    })
                
                # Generate button
                submit_button = st.form_submit_button("Generate Hall Ticket")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Process form submission
            if submit_button:
                if not (name and roll_number and program and semester and exam_date and seat_number):
                    st.error("Please fill in all the required fields.")
                else:
                    # Show loading spinner
                    with st.spinner("Generating Hall Ticket..."):
                        try:
                            # Generate a unique ID for the hall ticket
                            hall_ticket_id = str(uuid.uuid4())[:8].upper()
                            
                            # Prepare student data
                            student_data = {
                                'id': str(uuid.uuid4()),
                                'name': name,
                                'roll_number': roll_number,
                                'program': program,
                                'semester': semester,
                                'exam_date': exam_date.strftime('%d-%m-%Y'),
                                'seat_number': seat_number,
                                'hall_ticket_id': hall_ticket_id,
                                'subjects': subjects
                            }
                            
                            # Save to database
                            db_save_success = save_to_database(student_data)
                            
                            if not db_save_success:
                                st.warning("Could not save to database, but will still generate the hall ticket.")
                            
                            # Generate the PDF
                            pdf_path = generate_hall_ticket_pdf(student_data)
                            
                            if pdf_path:
                                # Success message
                                st.markdown('<div class="success-message">', unsafe_allow_html=True)
                                st.success("Hall Ticket generated successfully!")
                                st.markdown(f"**Hall Ticket ID:** {hall_ticket_id}")
                                st.markdown('</div>', unsafe_allow_html=True)
                                
                                # Create download button with improved styling
                                st.markdown('<div class="download-link">', unsafe_allow_html=True)
                                download_link = get_download_link(pdf_path, "📄 Download Hall Ticket")
                                st.markdown(download_link, unsafe_allow_html=True)
                                
                                # Add delete button
                                if st.button("🗑️ Delete This Hall Ticket", key="delete_generated"):
                                    if delete_from_database(roll_number, hall_ticket_id):
                                        st.success("Hall ticket deleted successfully!")
                                        # Use st.rerun() instead of st.experimental_rerun()
                                        st.rerun()
                                    else:
                                        st.error("Failed to delete hall ticket.")
                                
                                st.markdown('</div>', unsafe_allow_html=True)
                                
                                # QR Code information
                                st.markdown('<div class="qr-info">', unsafe_allow_html=True)
                                st.markdown("#### About the QR Code")
                                st.markdown("The hall ticket contains a QR code that when scanned will allow direct download of the hall ticket. To download, the student will need to enter their Hall Ticket ID and Roll Number when prompted.")
                                st.markdown('</div>', unsafe_allow_html=True)
                                
                                # Preview
                                st.markdown("### Preview")
                                st.info("PDF preview is available after download. Please download the hall ticket to view it.")
                            else:
                                st.error("Failed to generate the hall ticket. Please try again.")
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")
        
        elif page == "View Existing Hall Tickets":
            st.markdown('<div class="section-container">', unsafe_allow_html=True)
            st.markdown("## View Existing Hall Tickets")
            
            try:
                # Load database
                df = load_database()
                
                if df.empty:
                    st.info("No hall tickets have been generated yet.")
                else:
                    # Search functionality - Fixed
                    search_term = st.text_input("Search by Name or Roll Number")
                    
                    if search_term:
                        # Improved search capability - make everything lowercase and use string contains
                        # Convert all columns to string type before searching to avoid type errors
                        name_filter = df['name'].astype(str).str.lower().str.contains(search_term.lower(), na=False)
                        roll_filter = df['roll_number'].astype(str).str.lower().str.contains(search_term.lower(), na=False)
                        hall_ticket_filter = df['hall_ticket_id'].astype(str).str.lower().str.contains(search_term.lower(), na=False)
                        
                        # Combine filters
                        filtered_df = df[name_filter | roll_filter | hall_ticket_filter]
                    else:
                        filtered_df = df
                    
                    if filtered_df.empty:
                        st.info("No matching records found.")
                    else:
                        # Display the records
                        st.markdown(f"**Found {len(filtered_df)} records**")
                        
                        for _, row in filtered_df.iterrows():
                            try:
                                with st.expander(f"{row['name']} - {row['roll_number']}"):
                                    col1, col2 = st.columns(2)
                                    
                                    with col1:
                                        st.markdown(f"**Name:** {row['name']}")
                                        st.markdown(f"**Roll Number:** {row['roll_number']}")
                                        st.markdown(f"**Program:** {row['program']}")
                                        st.markdown(f"**Semester:** {row['semester']}")
                                    
                                    with col2:
                                        st.markdown(f"**Exam Date:** {row['exam_date']}")
                                        st.markdown(f"**Seat Number:** {row['seat_number']}")
                                        st.markdown(f"**Hall Ticket ID:** {row['hall_ticket_id']}")
                                    
                                    # Show subjects if available
                                    if 'subjects' in row and row['subjects']:
                                        st.markdown("**Examination Subjects:**")
                                        try:
                                            # Try to parse the subjects if stored as string
                                            if isinstance(row['subjects'], str):
                                                subjects = ast.literal_eval(row['subjects'])
                                            else:
                                                subjects = row['subjects']
                                                
                                            # Create a table to display subjects
                                            if subjects and isinstance(subjects, list):
                                                # Display as a proper table
                                                subjects_data = []
                                                for subject in subjects:
                                                    if isinstance(subject, dict):
                                                        subjects_data.append([
                                                            subject.get('code', ''),
                                                            subject.get('name', ''),
                                                            subject.get('date', '')
                                                        ])
                                                    else:
                                                        subjects_data.append(['', str(subject), ''])
                                                
                                                # Create a DataFrame for better display
                                                subjects_df = pd.DataFrame(
                                                    subjects_data, 
                                                    columns=['Subject Code', 'Subject Name', 'Exam Date']
                                                )
                                                st.dataframe(subjects_df, use_container_width=True)
                                        except Exception as e:
                                            st.warning(f"Could not parse subjects: {str(e)}")
                                            st.write(row['subjects'])
                                    
                                    # Download/Delete options
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        try:
                                            # Generate hall ticket for downloading
                                            pdf_path = generate_hall_ticket_pdf(row.to_dict())
                                            if pdf_path:
                                                st.markdown(get_download_link(pdf_path, "📄 Download Hall Ticket"), unsafe_allow_html=True)
                                        except Exception as e:
                                            st.error(f"Error generating hall ticket: {str(e)}")
                                    
                                    with col2:
                                        # Delete button
                                        if st.button("🗑️ Delete Hall Ticket", key=f"delete_{row['id']}"):
                                            if delete_from_database(row['roll_number'], row['hall_ticket_id']):
                                                st.success("Hall ticket deleted successfully!")
                                                # Use st.rerun() instead of st.experimental_rerun()
                                                st.rerun()
                                            else:
                                                st.error("Failed to delete hall ticket.")
                            except Exception as e:
                                st.error(f"Error displaying student record: {str(e)}")
            except Exception as e:
                st.error(f"Error loading database: {str(e)}")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        elif page == "Download Hall Ticket":
            create_qr_download_endpoint()
    
    except Exception as e:
        st.error(f"An error occurred in the application: {str(e)}")

if __name__ == "__main__":
    main()