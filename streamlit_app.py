import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import hashlib
import sqlite3
import os
from scipy.stats import norm

# --- Page Configuration ---
st.set_page_config(
    page_title="SCARTIX - TPMS Scaffold Predictor",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Constants and Parameters ---
NATIVE_CARTILAGE = {
    'stress_range': (1.5, 3.0),  # MPa
    'strain_range': (7500, 8500),
    'flow_rate_range': (0.4, 0.6),  # mL/min
    'shear_stress_range': (150, 250)  # Pa
}

def generate_complete_params():
    params = {}
    porosities = list(range(30, 91))
    
    key_points = {
        30: {
            'stress': {'mean': 5.8913, 'std': 1.1549},
            'strain': {'mean': 8058.8783, 'std': 1648.1018},
            'flow_rate': {'mean': 0.3, 'std': 0.08},
            'shear_stress': {'mean': 300, 'std': 20},
            'mechanical_strength': {'mean': 100.0, 'std': 5.2},
            'cell_migration': {'mean': 65.0, 'std': 8.1},
        },
        60: {
            'stress': {'mean': 1.9460, 'std': 0.3939},
            'strain': {'mean': 8049.9094, 'std': 1628.8954},
            'flow_rate': {'mean': 0.5, 'std': 0.1},
            'shear_stress': {'mean': 200, 'std': 15},
            'mechanical_strength': {'mean': 70.0, 'std': 4.8},
            'cell_migration': {'mean': 85.0, 'std': 7.4},
        },
        90: {
            'stress': {'mean': 0.1197, 'std': 0.0242},
            'strain': {'mean': 8041.5586, 'std': 1646.9436},
            'flow_rate': {'mean': 0.7, 'std': 0.12},
            'shear_stress': {'mean': 150, 'std': 10},
            'mechanical_strength': {'mean': 40.0, 'std': 3.9},
            'cell_migration': {'mean': 95.0, 'std': 8.8},
        }
    }
    
    for porosity in porosities:
        params[porosity] = {}
        if porosity <= 60:
            p1, p2 = 30, 60
        else:
            p1, p2 = 60, 90
            
        factor = (porosity - p1) / (p2 - p1)
        
        for prop in ['stress', 'strain', 'flow_rate', 'shear_stress', 'mechanical_strength', 'cell_migration']:
            params[porosity][prop] = {
                'mean': key_points[p1][prop]['mean'] + factor * (key_points[p2][prop]['mean'] - key_points[p1][prop]['mean']),
                'std': key_points[p1][prop]['std'] + factor * (key_points[p2][prop]['std'] - key_points[p1][prop]['std'])
            }
    
    return params

STATISTICAL_PARAMS = generate_complete_params()

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

# --- TPMS Scaffold Simulator Class ---
class TPMSScaffoldSimulator:
    def __init__(self):
        self.statistical_params = STATISTICAL_PARAMS
        self.n_points = 100
        
    def calculate_cell_migration(self, porosity, flow_rate, shear_stress):
        norm_porosity = (porosity - 30) / 60
        norm_flow = (flow_rate - 0.3) / 0.4
        norm_shear = 1 - ((shear_stress - 150) / 150)
        
        porosity_weight = 0.4
        flow_weight = 0.35
        shear_weight = 0.25
        
        migration_score = (norm_porosity * porosity_weight + 
                         norm_flow * flow_weight + 
                         norm_shear * shear_weight) * 100
        
        return max(min(migration_score, 100), 0)
        
    def generate_stress_strain_values(self, porosity_params):
        strain_range = 3 * porosity_params['strain']['std']
        strain_values = np.linspace(
            porosity_params['strain']['mean'] - strain_range,
            porosity_params['strain']['mean'] + strain_range,
            self.n_points
        )
        stress_values = np.full_like(strain_values, porosity_params['stress']['mean'])
        return stress_values.tolist(), strain_values.tolist()
        
    def generate_flow_rate_values(self, params):
        flow_rate = np.full(self.n_points, params['flow_rate']['mean'])
        return flow_rate.tolist()
    
    def get_bio_properties(self, porosity, params):
        mechanical_strength = params['mechanical_strength']['mean']
        cell_migration = self.calculate_cell_migration(
            porosity,
            params['flow_rate']['mean'],
            params['shear_stress']['mean']
        )
        return mechanical_strength, cell_migration
    
    def interpret_results(self, values):
        interpretations = {}
        
        if NATIVE_CARTILAGE['stress_range'][0] <= values['stress'] <= NATIVE_CARTILAGE['stress_range'][1]:
            interpretations['stress'] = "Optimal - Within native cartilage range"
        elif values['stress'] < NATIVE_CARTILAGE['stress_range'][0]:
            interpretations['stress'] = "Suboptimal - Lower than native cartilage"
        else:
            interpretations['stress'] = "Suboptimal - Higher than native cartilage"
            
        if NATIVE_CARTILAGE['strain_range'][0] <= values['strain'] <= NATIVE_CARTILAGE['strain_range'][1]:
            interpretations['strain'] = "Optimal - Within native cartilage range"
        elif values['strain'] < NATIVE_CARTILAGE['strain_range'][0]:
            interpretations['strain'] = "Suboptimal - Lower than native cartilage"
        else:
            interpretations['strain'] = "Suboptimal - Higher than native cartilage"
            
        if NATIVE_CARTILAGE['flow_rate_range'][0] <= values['flow_rate'] <= NATIVE_CARTILAGE['flow_rate_range'][1]:
            interpretations['flow_rate'] = "Optimal - Promotes nutrient transport"
        elif values['flow_rate'] < NATIVE_CARTILAGE['flow_rate_range'][0]:
            interpretations['flow_rate'] = "Suboptimal - May limit nutrient transport"
        else:
            interpretations['flow_rate'] = "Suboptimal - May cause excessive shear stress"
            
        if NATIVE_CARTILAGE['shear_stress_range'][0] <= values['shear_stress'] <= NATIVE_CARTILAGE['shear_stress_range'][1]:
            interpretations['shear_stress'] = "Optimal - Suitable for cell viability"
        elif values['shear_stress'] < NATIVE_CARTILAGE['shear_stress_range'][0]:
            interpretations['shear_stress'] = "Suboptimal - May not stimulate cells sufficiently"
        else:
            interpretations['shear_stress'] = "Suboptimal - May cause cell damage"
            
        if values['mechanical_strength'] >= 80:
            interpretations['mechanical_strength'] = "Excellent - Close to native cartilage"
        elif 60 <= values['mechanical_strength'] < 80:
            interpretations['mechanical_strength'] = "Good - Suitable for load-bearing"
        else:
            interpretations['mechanical_strength'] = "Fair - May need reinforcement"
            
        if values['cell_migration'] >= 85:
            interpretations['cell_migration'] = "Excellent - Optimal for cell infiltration"
        elif 70 <= values['cell_migration'] < 85:
            interpretations['cell_migration'] = "Good - Supports cell movement"
        elif 50 <= values['cell_migration'] < 70:
            interpretations['cell_migration'] = "Fair - Limited cell distribution"
        else:
            interpretations['cell_migration'] = "Poor - Significant barriers to cell movement"
            
        return interpretations
    
    def plot_stress_strain(self, porosity):
        params = self.statistical_params[porosity]
        stress, strain = self.generate_stress_strain_values(params)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(strain, stress, '-', label=f'{porosity}% Porosity')
        
        ax.set_xlabel('Strain')
        ax.set_ylabel('Stress (MPa)')
        ax.set_title(f'Stress-Strain Relationship for {porosity}% Porosity')
        ax.grid(True)
        ax.legend()
        
        return fig
    
    def plot_flow_rate(self, porosity):
        params = self.statistical_params[porosity]
        flow_rate = params['flow_rate']['mean']
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axvline(x=flow_rate, color='b', linestyle='-', label=f'Flow Rate: {flow_rate:.3f} mL/min')
        
        ax.set_xlabel('Flow Rate (mL/min)')
        ax.set_ylabel('Value')
        ax.set_title(f'Flow Rate for {porosity}% Porosity')
        ax.set_xlim(0, 1.0)
        ax.grid(True)
        ax.legend()
        
        return fig
        
    def get_values(self, porosity):
        params = self.statistical_params[porosity]
        
        stress, strain = self.generate_stress_strain_values(params)
        flow_rate = params['flow_rate']['mean']
        mechanical_strength, cell_migration = self.get_bio_properties(porosity, params)
        
        return {
            'stress': params['stress']['mean'],
            'strain': params['strain']['mean'],
            'flow_rate': flow_rate,
            'mechanical_strength': mechanical_strength,
            'cell_migration': cell_migration,
            'shear_stress': params['shear_stress']['mean']
        }

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
    
    # Input for porosity
    porosity = st.slider("Select Porosity (%)", min_value=30, max_value=90, value=60, step=1)

    # Submit
    if st.button("Simulate"):
        simulator = TPMSScaffoldSimulator()
        results = simulator.get_values(porosity)
        interpretations = simulator.interpret_results(results)
        
        # Display results with interpretations
        st.subheader(f"Results for {porosity}% Porosity")
        
        st.write("Stress:")
        st.write(f"Value: {results['stress']:.4f} MPa")
        st.write(f"Assessment: {interpretations['stress']}")
        
        st.write("\nStrain:")
        st.write(f"Value: {results['strain']:.4f}")
        st.write(f"Assessment: {interpretations['strain']}")
        
        st.write("\nFlow Rate:")
        st.write(f"Value: {results['flow_rate']:.3f} mL/min")
        st.write(f"Assessment: {interpretations['flow_rate']}")
        
        st.write("\nShear Stress:")
        st.write(f"Value: {results['shear_stress']:.2f} Pa")
        st.write(f"Assessment: {interpretations['shear_stress']}")
        
        st.write("\nMechanical Strength:")
        st.write(f"Value: {results['mechanical_strength']:.2f}% of native cartilage")
        st.write(f"Assessment: {interpretations['mechanical_strength']}")
        
        st.write("\nCell Migration:")
        st.write(f"Value: {results['cell_migration']:.2f}% of optimal")
        st.write(f"Assessment: {interpretations['cell_migration']}")
        
        # Plot stress-strain relationship
        st.subheader("Stress-Strain Relationship")
        st.pyplot(simulator.plot_stress_strain(porosity))
        
        # Plot flow rate
        st.subheader("Flow Rate")
        st.pyplot(simulator.plot_flow_rate(porosity))
        

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
