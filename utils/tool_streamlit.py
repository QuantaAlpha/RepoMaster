import os
import uuid
import pandas as pd
import plotly.express as px

import io
import fitz  # PyMuPDF for PDF handling
import base64

from PIL import Image

import streamlit as st
import string
import random

def random_string(length=12):
    letters = string.ascii_lowercase + string.digits
    return "".join(random.choice(letters) for i in range(length))

class AppContext:
    _instance = None

    def __init__(self):
        self.st = None
        self.work_dir = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_work_dir(cls, work_dir):
        cls.get_instance().work_dir = work_dir

    @classmethod
    def set_streamlit(cls, st):
        cls.get_instance().st = st


def get_file_type(file_name):
    _, extension = os.path.splitext(file_name)
    extension = extension.lower()
    if extension in ['.csv', '.xlsx', '.xls']:
        return 'data'
    elif extension in ['.txt', '.md', '.py', '.js', '.html', '.css']:
        return 'text'
    elif extension == '.pdf':
        return 'pdf'
    elif extension in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']:
        return 'image'
    elif extension in ['.mp3', '.wav', '.ogg']:
        return 'audio'
    elif extension in ['.mp4', '.avi', '.mov']:
        return 'video'
    else:
        return 'other'

# Enhanced file handling functions
def get_files_from_dir(directory):
    files = []
    if os.path.exists(directory):
        for file in os.listdir(directory):
            file_path = os.path.join(directory, file)
            file_info = {
                'name': file,
                'path': file_path,
                'type': get_file_type(file),
                'thumbnail': generate_thumbnail(file_path)
            }
            files.append(file_info)
    files = [file_info for file_info in files if file_info['type'] in ['pdf','image', 'data']] + [
        file_info for file_info in files if file_info['type'] not in ['pdf','image', 'data']]
    return files

def generate_thumbnail(file_path):
    file_type = get_file_type(file_path)
    if file_type == 'image':
        with Image.open(file_path) as img:
            img.thumbnail((100, 100))
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
    elif file_type == 'pdf':
        try:
            doc = fitz.open(file_path)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(100/72, 100/72))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
        except Exception:
            return generate_default_thumbnail()
    else:
        return generate_default_thumbnail()

def generate_default_thumbnail():
    img = Image.new('RGB', (100, 10), color=(200, 200, 200))
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def display_file_content(file_path):
    file_type = get_file_type(file_path)
    
    idx = str(uuid.uuid4())
    
    if file_type == 'data':
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:  # Excel files
            df = pd.read_excel(file_path)
        st.dataframe(df)
        
        if len(df.columns) >= 2 and 0:
            x_col = st.selectbox("Select X-axis", df.columns, key=f"x_axis_{idx}")
            y_col = st.selectbox("Select Y-axis", df.columns, key=f"y_axis_{idx}")
            chart_type = st.selectbox("Select chart type", ["Line", "Bar", "Scatter"], key=f"chart_{idx}")
            
            if chart_type == "Line":
                fig = px.line(df, x=x_col, y=y_col)
            elif chart_type == "Bar":
                fig = px.bar(df, x=x_col, y=y_col)
            else:
                fig = px.scatter(df, x=x_col, y=y_col)
            
            st.plotly_chart(fig)
    elif file_type == 'text':
        with open(file_path, 'r') as file:
            content = file.read()
            st.text_area("File Content", content, height=300)
    elif file_type == 'pdf':
        with fitz.open(file_path) as doc:
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                st.image(img, caption=f"Page {page.number + 1}")
    elif file_type == 'image':
        st.image(file_path)
    elif file_type in ['audio', 'video']:
        st.warning(f"{file_type.capitalize()} preview is not available. Please download the file to view its content.")
    else:
        st.error("Unsupported file type")

def handle_file_upload(work_dir):
    # st.markdown('<h3 class="section-header">File Upload</h3>', unsafe_allow_html=True)
    st.markdown('<div class="file-uploader">', unsafe_allow_html=True)
    file = st.sidebar.file_uploader("Upload your file", type=['csv', 'xlsx', 'xls', 'pdf', 'txt', 'md', 'py', 'js', 'html', 'css', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'mp3', 'wav', 'ogg', 'mp4', 'avi', 'mov'])
    # st.markdown('</div>', unsafe_allow_html=True)
    # st.sidebar.success(f"File {file.name} uploaded successfully!")
    
    if file is not None:
        file_extension = os.path.splitext(file.name)[1]
        
        # Save the uploaded file
        os.makedirs(work_dir, exist_ok=True)
        save_path = os.path.join(work_dir, file.name)
        with open(save_path, "wb") as f:
            f.write(file.getbuffer())
        st.sidebar.success(f"File {file.name} saved successfully!")
    
    return file

def download_file_lists(work_dir):
    st.markdown("### Download Files you need...")
    image_files = get_files_from_dir(work_dir, ['.png', '.jpg', '.jpeg', '.gif'])
    table_files = get_files_from_dir(work_dir, ['.csv', '.xlsx'])
    pdf_txt_files = get_files_from_dir(work_dir, ['.pdf', '.md', '.pdf'])

    # Use st.selectbox to update dropdown box in real-time
    selected_image = st.selectbox("Select an image to download", image_files, key=f"imag_select_{random_string(8)}")
    if selected_image:
        file_path = os.path.join(work_dir, selected_image)
        with open(file_path, "rb") as file:
            btn = st.download_button(
                label="Download Image",
                data=file,
                file_name=selected_image
            )

    selected_table = st.selectbox("Select a table to download", table_files, key=f"table_select_{random_string(8)}")
    if selected_table:
        file_path = os.path.join(work_dir, selected_table)
        with open(file_path, "rb") as file:
            btn = st.download_button(
                label="Download Table",
                data=file,
                file_name=selected_table
            )

    selected_pdf = st.selectbox("Select a pdf/markdown/txt to download", pdf_txt_files, key=f"pdf_select_{random_string(8)}")
    if selected_pdf:
        file_path = os.path.join(work_dir, selected_pdf)
        with open(file_path, "rb") as file:
            btn = st.download_button(
                label="Download Table",
                data=file,
                file_name=selected_pdf
            )

def Upload_files(work_dir):
    st.markdown("## File Upload")
    file = st.file_uploader("Upload your financial data", type=['csv', 'xlsx', 'pdf', 'txt', 'md'])
    if file is not None:
        if file.type == "application/pdf":
            # Here you can add logic to read PDF content
            pass
        elif file.type == "text/csv":
            df = pd.read_csv(file)
            st.dataframe(df.head())
        elif file.type == "application/vnd.ms-excel" or file.type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            df = pd.read_excel(file)
            st.dataframe(df.head())
        elif file.type == "text/plain":
            content = file.read().decode("utf-8")
            st.text(content)
        elif file.type == "text/markdown":
            content = file.read().decode("utf-8")
            st.markdown(content)
        elif file.type == "text/html":
            content = file.read().decode("utf-8")
            st.markdown(content, unsafe_allow_html=True)
        else:
            st.error("Unsupported file type")
        
        # Save the uploaded file
        os.makedirs(work_dir)
        save_path = os.path.join(work_dir, file.name)
        with open(save_path, "wb") as f:
            f.write(file.getbuffer())
        st.success(f"File {file.name} saved to: {save_path}")     
        
        
def create_preview_tab(file_path):
    new_tab_id = f"preview_{len(st.session_state.tabs)}"
    st.session_state.tabs.append(new_tab_id)
    st.session_state.active_tab = new_tab_id
    st.session_state[f"preview_file_{new_tab_id}"] = file_path
    return new_tab_id

def get_file_preview_content(file_path):
    file_type = get_file_type(file_path)
    content = None
    
    if file_type == 'data':
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:  # Excel files
            df = pd.read_excel(file_path)
        content = {
            'type': 'data',
            'dataframe': df,
            'columns': df.columns.tolist()
        }
    elif file_type == 'text':
        with open(file_path, 'r') as file:
            content = {
                'type': 'text',
                'text': file.read()
            }
    elif file_type == 'pdf':
        content = {
            'type': 'pdf',
            'pages': []
        }
        with fitz.open(file_path) as doc:
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                content['pages'].append(img_str)
    elif file_type == 'image':
        with open(file_path, "rb") as image_file:
            content = {
                'type': 'image',
                'image': base64.b64encode(image_file.read()).decode()
            }
    elif file_type in ['audio', 'video']:
        content = {
            'type': file_type,
            'message': f"{file_type.capitalize()} preview is not available. Please download the file to view its content."
        }
    else:
        content = {
            'type': 'error',
            'message': "Unsupported file type"
        }
    
    return content

def display_file_preview(content):
    if content['type'] == 'data':
        st.dataframe(content['dataframe'])
        
        if len(content['columns']) >= 2:
            x_col = st.selectbox("Select X-axis", content['columns'])
            y_col = st.selectbox("Select Y-axis", content['columns'])
            chart_type = st.selectbox("Select chart type", ["Line", "Bar", "Scatter"])
            
            if chart_type == "Line":
                fig = px.line(content['dataframe'], x=x_col, y=y_col)
            elif chart_type == "Bar":
                fig = px.bar(content['dataframe'], x=x_col, y=y_col)
            else:
                fig = px.scatter(content['dataframe'], x=x_col, y=y_col)
            
            st.plotly_chart(fig)
    elif content['type'] == 'text':
        st.text_area("File Content", content['text'], height=300)
    elif content['type'] == 'pdf':
        for i, page_img in enumerate(content['pages']):
            st.image(page_img, caption=f"Page {i + 1}")
    elif content['type'] == 'image':
        st.image(content['image'])
    elif content['type'] in ['audio', 'video']:
        st.warning(content['message'])
    else:
        st.error(content['message'])
        
def st_print_history_message(st, history_message):
    for message in history_message:
        role = message.get("role")
        content = message.get("content")
        
        # Check if there's any non-empty content to display
        has_content = content and content.strip()
        has_function_call = "function_call" in message and message["function_call"]
        has_tool_calls = "tool_calls" in message and message["tool_calls"]
        has_tool_responses = "tool_responses" in message and message["tool_responses"]
        
        if has_content or has_function_call or has_tool_calls or has_tool_responses:
            with st.chat_message(role):
                if has_content:
                    st.markdown(content)
                
                if has_tool_calls:
                    for tool_call in message["tool_calls"]:
                        function = tool_call.get("function", {})
                        name = function.get("name")
                        arguments = function.get("arguments")
                        if name and arguments:
                            st.markdown(f"**Tool Call:** {name}")
                            st.code(arguments)
                            
                if has_function_call:
                    function_call = message["function_call"]
                    name = function_call.get("name")
                    arguments = function_call.get("arguments")
                    if name and arguments:
                        st.markdown(f"**Function Call:** {name}")
                        st.code(arguments)                            
                
                if has_tool_responses:
                    for tool_response in message["tool_responses"]:
                        response_content = tool_response.get("content")
                        if response_content and response_content.strip():
                            st.markdown(f"**Tool Response:**")
                            st.markdown(response_content)
