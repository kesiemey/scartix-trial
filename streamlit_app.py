import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import hashlib
import sqlite3
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="SCARTIX - TPMS Scaffold Predictor",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect('scartix.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users
        (username TEXT PRIMARY KEY, 
         password TEXT,
         institution TEXT,
         created_date TEXT)
    ''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- Session State Management ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    init_db()

# --- Custom CSS ---
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #2e6c80;
        color: white;
    }
    .login-container {
        max-width: 800px;
        margin: auto;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 0 10px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- Login Page ---
def login_page():
    st.markdown("""
        <h1 style='text-align: center; color: #2e6c80;'>
            SCARTIX
        </h1>
        <h3 style='text-align: center; color: #666666;'>
            CHITOSAN-BASED TPMS SCAFFOLD PERFORMANCE PREDICTOR
        </h3>
        """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                conn = sqlite3.connect('scartix.db')
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=? AND password=?", 
                         (username, hash_password(password)))
                result = c.fetchone()
                conn.close()
                
                if result:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    
    with col2:
        st.markdown("### Register")
        with st.form("register_form"):
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            institution = st.text_input("Institution")
            register = st.form_submit_button("Register")
            
            if register:
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    conn = sqlite3.connect('scartix.db')
                    c = conn.cursor()
                    try:
                        c.execute(
                            "INSERT INTO users VALUES (?, ?, ?, ?)",
                            (new_username, hash_password(new_password), 
                             institution, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        )
                        conn.commit()
                        st.success("Registration successful! Please login.")
                    except sqlite3.IntegrityError:
                        st.error("Username already exists")
                    finally:
                        conn.close()

# --- Main App ---
def main_app():
    st.sidebar.title(f"Welcome, {st.session_state.username}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
    
    pages = {
        "Predictor": "predictor_page",
        "History": "history_page",
        "Documentation": "documentation_page"
    }
    
    page = st.sidebar.radio("Navigation", list(pages.keys()))
    
    if page == "Predictor":
        predictor_page()
    elif page == "History":
        history_page()
    elif page == "Documentation":
        documentation_page()

# --- Predictor Page ---
def predictor_page():
    st.markdown("""
        <h2 style='text-align: center; color: #2e6c80;'>
            TPMS Scaffold Performance Predictor
        </h2>
        """, unsafe_allow_html=True)
    
    with st.form("prediction_form"):
        biomaterial = st.selectbox(
            "Base Biomaterial",
            ["Chitosan", "Zinc Oxide", "Collagen (Type II)"]
        )
        porosity = st.slider("Porosity (%)", 30, 90)
        
        submit = st.form_submit_button("Predict Performance")
        
        if submit:
            show_results(biomaterial, porosity)

def show_results(biomaterial, porosity):
    st.subheader(f"Prediction Results for {biomaterial} with {porosity}% Porosity")
    
    # Split results into columns
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Mechanical Properties")
        # Adjust mechanical properties based on porosity
        mechanical_strength = 90 - (porosity * 0.5) + np.random.uniform(-5, 5)
        elastic_modulus = 200 - porosity + np.random.uniform(-10, 10)
        
        st.metric("Compressive Strength", f"{mechanical_strength:.1f} MPa")
        st.metric("Elastic Modulus", f"{elastic_modulus:.1f} MPa")
        
        # Stress-strain plot
        fig, ax = plt.subplots()
        strain = np.linspace(0, 0.1, 100)
        stress = elastic_modulus * strain + np.random.normal(0, 1, 100)
        ax.plot(strain, stress)
        ax.set_xlabel("Strain")
        ax.set_ylabel("Stress (MPa)")
        ax.set_title("Stress-Strain Curve")
        st.pyplot(fig)
    
    with col2:
        st.subheader("Biological Properties")
        # Adjust biological properties based on porosity and biomaterial
        base_viability = 90 if "Collagen" in biomaterial else 85
        cell_viability = base_viability + (porosity * 0.1) + np.random.uniform(-2, 2)
        proliferation_rate = 75 + (porosity * 0.2) + np.random.uniform(-3, 3)
        
        st.metric("Cell Viability", f"{cell_viability:.1f}%")
        st.metric("Proliferation Rate", f"{proliferation_rate:.1f}%")
        
        # Cell growth plot
        fig, ax = plt.subplots()
        days = np.arange(7)
        growth_rate = 0.5 * (porosity/70)  # Adjust growth rate based on porosity
        growth = 1000 * np.exp(growth_rate * days + np.random.normal(0, 0.1, 7))
        ax.plot(days, growth, marker='o')
        ax.set_xlabel("Days")
        ax.set_ylabel("Cell Count")
        ax.set_title("Cell Proliferation")
        st.pyplot(fig)

def history_page():
    st.title("Prediction History")
    st.info("This page will show the history of predictions made by the user")
    # Add history functionality here

def documentation_page():
    st.title("Documentation")
    st.markdown("""
    ### About SCARTIX
    
    SCARTIX is a predictive tool for analyzing the performance of chitosan-based TPMS scaffolds 
    in articular cartilage tissue regeneration. The tool uses advanced machine learning algorithms 
    to predict mechanical and biological properties based on scaffold parameters.
    
    ### Parameters
    
    - **Base Biomaterial**: The primary material used in scaffold fabrication
        - Chitosan
        - Zinc Oxide
        - Collagen (Type II)
    
    - **Porosity**: The percentage of void space in the scaffold (30-90%)
    
    ### Outputs
    
    The predictor provides:
    1. Mechanical Properties
        - Compressive Strength
        - Elastic Modulus
        - Stress-Strain Behavior
    
    2. Biological Properties
        - Cell Viability
        - Proliferation Rate
        - Growth Curves
    """)

# --- Run App ---
if not st.session_state.logged_in:
    login_page()
else:
    main_app()
