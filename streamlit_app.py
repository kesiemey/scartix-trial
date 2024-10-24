import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import hashlib
import sqlite3
import os
import plotly.graph_objects as go
import smtplib
from email.mime.text import MIMEText
from scipy.stats import norm
import re
from email.message import EmailMessage


# --- Page Configuration ---
st.set_page_config(
   page_title="SCARTIX - Scaffold Performance Predictor",
   page_icon="🧬",
   layout="wide",
   initial_sidebar_state="expanded"
)

# For a gradient background:
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(to right, #E8F0FE, #D4E4FA);
    }
</style>
""", unsafe_allow_html=True)

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
  


def login_page():
   import streamlit.components.v1 as components
  
   # Custom CSS for the page
   st.markdown("""
       <style>
       /* Main container styling */
       .main {
           background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
           padding: 2rem;
       }
      
       /* Custom title styling */
       .title-container {
           text-align: center;
           margin-bottom: 2rem;
           background: linear-gradient(135deg, #6b46c1 0%, #4299e1 100%);
           padding: 2rem;
           border-radius: 1rem;
           box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
       }
      
       .main-title {
           color: white;
           font-size: 3rem;
           font-weight: 700;
           margin-bottom: 0.5rem;
           text-transform: uppercase;
           letter-spacing: 0.1em;
       }
      
       .subtitle {
           color: rgba(255, 255, 255, 0.9);
           font-size: 1.2rem;
           font-weight: 500;
           
       /* Input field styling */
       .stTextInput input {
           border: 2px solid #e2e8f0;
           border-radius: 0.5rem;
           padding: 0.75rem;
           font-size: 1rem;
           transition: all 0.3s;
       }
      
       .stTextInput input:focus {
           border-color: #6b46c1;
           box-shadow: 0 0 0 3px rgba(107, 70, 193, 0.2);
       }
      
       /* Button styling */
       .stButton button {
           background: linear-gradient(135deg, #6b46c1 0%, #4299e1 100%);
           color: white;
           border: none;
           padding: 0.75rem 2rem;
           border-radius: 0.5rem;
           font-weight: 600;
           transition: all 0.3s;
           width: 100%;
       }
      
       .stButton button:hover {
           transform: translateY(-2px);
           box-shadow: 0 4px 6px rgba(107, 70, 193, 0.2);
       }
      
       /* Error message styling */
       .stAlert {
           border-radius: 0.5rem;
           margin-top: 1rem;
       }
       </style>
   """, unsafe_allow_html=True)


   # Updated gyroid visualization with new colors
   gyroid_html = """
   <div id="gyroidContainer" style="width: 100%; height: 250px; margin: 2rem auto;">
       <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.158.0/three.min.js"></script>
       <script>
           const scene = new THREE.Scene();
           const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
           const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
           const container = document.getElementById('gyroidContainer');
           renderer.setSize(container.clientWidth, container.clientHeight);
           renderer.setClearColor(0x000000, 0);
           container.appendChild(renderer.domElement);


           const resolution = 50;
           const size = 2.8;
           const geometry = new THREE.BoxGeometry(size, size, size, resolution, resolution, resolution);
          
           const material = new THREE.ShaderMaterial({
               uniforms: {
                   time: { value: 0 }
               },
               vertexShader: `
                   varying vec3 vPosition;
                   void main() {
                       vPosition = position;
                       gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                   }
               `,
               fragmentShader: `
                   varying vec3 vPosition;
                   uniform float time;
                  
                   float gyroid(vec3 p, float scale) {
                       p *= scale;
                       return dot(sin(p), cos(vec3(p.y, p.z, p.x)));
                   }
                  
                   void main() {
                       float scale = 6.0;
                       vec3 p = vPosition;
                       float d = gyroid(p, scale);
                      
                       if (abs(d) > 0.1) discard;
                      
                       vec3 color = vec3(0.42, 0.28, 0.75); // Updated to purple theme
                       gl_FragColor = vec4(color, 0.9);
                   }
               `,
               side: THREE.DoubleSide,
               transparent: true
           });


           const mesh = new THREE.Mesh(geometry, material);
           scene.add(mesh);
           camera.position.z = 4;


           let isHovered = false;
           container.addEventListener('mouseenter', () => isHovered = true);
           container.addEventListener('mouseleave', () => isHovered = false);


           function animate() {
               requestAnimationFrame(animate);
               if (isHovered) {
                   mesh.rotation.x += 0.01;
                   mesh.rotation.y += 0.01;
               } else {
                   mesh.rotation.y += 0.003;
               }
               material.uniforms.time.value += 0.01;
               renderer.render(scene, camera);
           }
           animate();


           window.addEventListener('resize', () => {
               const width = container.clientWidth;
               const height = container.clientHeight;
               renderer.setSize(width, height);
               camera.aspect = width / height;
               camera.updateProjectionMatrix();
           });
       </script>
   </div>
   """


   # Title and Logo Section with updated styling
   st.markdown("""
       <div class="title-container">
           <h1 class="main-title">SCARTIX</h1>
           <p class="subtitle">CHITOSAN-BASED TPMS SCAFFOLD PERFORMANCE PREDICTOR</p>
       </div>
   """, unsafe_allow_html=True)
  
   # Insert the gyroid visualization
   components.html(gyroid_html, height=300)
  
   # Create three columns for better spacing
   col1, col2, col3 = st.columns([1, 2, 1])
  
   with col2:
       tab1, tab2 = st.tabs(["Login", "Register"])
      
       with tab1:
           st.markdown('<div class="form-container">', unsafe_allow_html=True)
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
           st.markdown('</div>', unsafe_allow_html=True)
      
       with tab2:
           st.markdown('<div class="form-container">', unsafe_allow_html=True)
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
           st.markdown('</div>', unsafe_allow_html=True)

# --- Main App ---
def main_app():
   st.markdown("""
    <style>
    /* Sidebar title styling (Welcome message) */
    .css-10trblm {
        color: #2C3E50;
        font-size: 1.1rem;
        margin-bottom: 1rem;
        text-transform: none;  /* Ensures welcome message isn't all caps */
    }
    
    /* Sidebar container */
    .css-1d391kg {
        background-color: #F8F9FA;
    }
    
    /* Sidebar links/navigation */
    .css-1oe5cao {
        text-transform: none;  /* Ensures nav items aren't all caps by default */
    }
    
    /* Logout button styling */
    .stButton button {
        background: linear-gradient(135deg, #2C3E50, #9B59B6);
        color: white;
        width: 100%;
        padding: 0.75rem;
        border: none;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.95rem;
        text-transform: uppercase;  /* Makes logout button text uppercase */
        letter-spacing: 0.05em;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        background: linear-gradient(135deg, #2C3E50, #9B59B6);
        border: none;
        color: white;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
    }
    
    .stButton button:active {
        transform: translateY(0);
        border: none;
    }
    </style>
""", unsafe_allow_html=True)
   
   st.sidebar.title(f"Welcome, {st.session_state.username}")
   if st.sidebar.button("Logout"):
       st.session_state.logged_in = False
       st.rerun()
  
   pages = {
       "Home": "home_page",
       "Predictor": "predictor_page",
       "Technical Support": "technicalsupport_page"
   }
  
   page = st.sidebar.radio("Navigation", list(pages.keys()))
  
   if page == "Home":
       home_page()
   elif page == "Technical Support":
       technicalsupport_page()
   elif page == "Predictor":
       predictor_page()

# Define tissue/organ mechanical properties requirements
TISSUE_PROPERTIES = {
    'articular_cartilage': {
        'stress': {'min': 5.0, 'optimal': 7.0},  # MPa
        'strain': {'min': 7000, 'optimal': 8500},  # microstrain
        'flow_rate': {'min': 0.2, 'optimal': 0.25},  # mL/min
        'shear_stress': {'min': 280, 'optimal': 320},  # Pa
        'description': 'Load-bearing cartilage in joints',
        'critical_factors': ['stress', 'shear_stress']
    },
    'meniscus': {
        'stress': {'min': 4.0, 'optimal': 6.0},
        'strain': {'min': 6500, 'optimal': 8000},
        'flow_rate': {'min': 0.15, 'optimal': 0.2},
        'shear_stress': {'min': 250, 'optimal': 300},
        'description': 'Knee meniscus tissue',
        'critical_factors': ['stress', 'strain']
    },
    'bone_tissue': {
        'stress': {'min': 15.0, 'optimal': 20.0},
        'strain': {'min': 2000, 'optimal': 3000},
        'flow_rate': {'min': 0.1, 'optimal': 0.15},
        'shear_stress': {'min': 400, 'optimal': 500},
        'description': 'Bone tissue with high mechanical demands',
        'critical_factors': ['stress', 'strain']
    },
    'skin': {
        'stress': {'min': 1.0, 'optimal': 2.0},
        'strain': {'min': 10000, 'optimal': 12000},
        'flow_rate': {'min': 0.3, 'optimal': 0.4},
        'shear_stress': {'min': 100, 'optimal': 150},
        'description': 'Dermal tissue with high elasticity requirements',
        'critical_factors': ['strain', 'flow_rate']
    },
    'blood_vessel': {
        'stress': {'min': 2.0, 'optimal': 3.0},
        'strain': {'min': 9000, 'optimal': 11000},
        'flow_rate': {'min': 0.4, 'optimal': 0.5},
        'shear_stress': {'min': 200, 'optimal': 250},
        'description': 'Vascular tissue with specific flow requirements',
        'critical_factors': ['flow_rate', 'shear_stress']
    }
}

def evaluate_tissue_compatibility(scaffold_props, tissue_reqs):
    """
    Evaluate scaffold compatibility with tissue requirements, incorporating
    mechanical strength and cell migration metrics
    
    Args:
        scaffold_props (dict): Properties of the scaffold including mechanical strength and cell migration
        tissue_reqs (dict): Tissue requirements for various properties
    
    Returns:
        tuple: (final_score, detailed_scores)
    """
    scores = {}
    
    # Evaluate traditional properties
    for property_name in ['stress', 'strain', 'flow_rate', 'shear_stress']:
        if property_name in scaffold_props and property_name in tissue_reqs:
            actual_value = scaffold_props[property_name]
            min_req = tissue_reqs[property_name]['min']
            optimal_req = tissue_reqs[property_name]['optimal']
            
            if actual_value >= optimal_req:
                scores[property_name] = 1.0
            elif actual_value >= min_req:
                scores[property_name] = (actual_value - min_req) / (optimal_req - min_req) * 0.5 + 0.5
            else:
                scores[property_name] = max(0, actual_value / min_req * 0.5)
    
    # Evaluate mechanical strength (percentage based)
    if 'mechanical_strength' in scaffold_props:
        mech_strength = scaffold_props['mechanical_strength']
        if mech_strength >= 80:  # Excellent
            scores['mechanical_strength'] = 1.0
        elif mech_strength >= 60:  # Good
            scores['mechanical_strength'] = 0.75
        elif mech_strength >= 40:  # Fair
            scores['mechanical_strength'] = 0.5
        else:  # Poor
            scores['mechanical_strength'] = 0.25
    
    # Evaluate cell migration (percentage based)
    if 'cell_migration' in scaffold_props:
        cell_migr = scaffold_props['cell_migration']
        if cell_migr >= 75:  # Excellent
            scores['cell_migration'] = 1.0
        elif cell_migr >= 60:  # Good
            scores['cell_migration'] = 0.75
        elif cell_migr >= 45:  # Fair
            scores['cell_migration'] = 0.5
        else:  # Poor
            scores['cell_migration'] = 0.25
    
    # Calculate weighted final score
    critical_factors = tissue_reqs.get('critical_factors', [])
    
    # Add mechanical strength and cell migration as critical factors if they meet certain thresholds
    if scaffold_props.get('mechanical_strength', 0) >= 70:
        critical_factors.append('mechanical_strength')
    if scaffold_props.get('cell_migration', 0) >= 65:
        critical_factors.append('cell_migration')
    
    if critical_factors:
        weighted_score = sum(scores[factor] * 2 for factor in critical_factors if factor in scores)
        weighted_score += sum(scores[prop] for prop in scores if prop not in critical_factors)
        total_weight = len([f for f in critical_factors if f in scores]) * 2 + (len(scores) - len([f for f in critical_factors if f in scores]))
        final_score = weighted_score / total_weight
    else:
        final_score = sum(scores.values()) / len(scores)
    
    # Adjust final score based on mechanical strength and cell migration thresholds
    if scaffold_props.get('mechanical_strength', 0) < 40 or scaffold_props.get('cell_migration', 0) < 45:
        final_score *= 0.5  # Significant penalty for poor mechanical strength or cell migration
    
    return final_score, scores

# Updated tissue properties dictionary to include mechanical strength and cell migration requirements
TISSUE_PROPERTIES = {
    'articular_cartilage': {
        'stress': {'min': 5.0, 'optimal': 7.0},  # MPa
        'strain': {'min': 7000, 'optimal': 8500},  # microstrain
        'flow_rate': {'min': 0.2, 'optimal': 0.25},  # mL/min
        'shear_stress': {'min': 280, 'optimal': 320},  # Pa
        'mechanical_strength_threshold': 70,  # Minimum percentage required
        'cell_migration_threshold': 65,  # Minimum percentage required
        'description': 'Load-bearing cartilage in joints',
        'critical_factors': ['stress', 'shear_stress', 'mechanical_strength']
    },
    'meniscus': {
        'stress': {'min': 4.0, 'optimal': 6.0},
        'strain': {'min': 6500, 'optimal': 8000},
        'flow_rate': {'min': 0.15, 'optimal': 0.2},
        'shear_stress': {'min': 250, 'optimal': 300},
        'mechanical_strength_threshold': 65,
        'cell_migration_threshold': 60,
        'description': 'Knee meniscus tissue',
        'critical_factors': ['stress', 'strain', 'mechanical_strength']
    },
    'bone_tissue': {
        'stress': {'min': 15.0, 'optimal': 20.0},
        'strain': {'min': 2000, 'optimal': 3000},
        'flow_rate': {'min': 0.1, 'optimal': 0.15},
        'shear_stress': {'min': 400, 'optimal': 500},
        'mechanical_strength_threshold': 80,
        'cell_migration_threshold': 55,
        'description': 'Bone tissue with high mechanical demands',
        'critical_factors': ['stress', 'strain', 'mechanical_strength']
    },
    'skin': {
        'stress': {'min': 1.0, 'optimal': 2.0},
        'strain': {'min': 10000, 'optimal': 12000},
        'flow_rate': {'min': 0.3, 'optimal': 0.4},
        'shear_stress': {'min': 100, 'optimal': 150},
        'mechanical_strength_threshold': 50,
        'cell_migration_threshold': 75,
        'description': 'Dermal tissue with high elasticity requirements',
        'critical_factors': ['strain', 'flow_rate', 'cell_migration']
    },
    'blood_vessel': {
        'stress': {'min': 2.0, 'optimal': 3.0},
        'strain': {'min': 9000, 'optimal': 11000},
        'flow_rate': {'min': 0.4, 'optimal': 0.5},
        'shear_stress': {'min': 200, 'optimal': 250},
        'mechanical_strength_threshold': 60,
        'cell_migration_threshold': 70,
        'description': 'Vascular tissue with specific flow requirements',
        'critical_factors': ['flow_rate', 'shear_stress', 'cell_migration']
    }
}

def get_recommendation_class(score):
    """
    Determine the CSS class for recommendation based on score
    
    Args:
        score (float): Compatibility score between 0 and 1
        
    Returns:
        str: CSS class name for styling
    """
    if score >= 0.8:
        return "assessment-optimal"
    return "assessment-suboptimal"

# --- Predictor Page ---
def predictor_page():
    st.markdown("""
        <style>
        /* Modern Color Palette */
        :root {
            --primary-purple: #6B46C1;
            --accent-green: #38A169;
            --accent-blue: #3182CE;
            --light-gray: #F7FAFC;
            --medium-gray: #A0AEC0;
            --text-dark: #2D3748;
            --white: #FFFFFF;
        }
        
        /* Card Styling */
        .metric-card {
            background: var(--white);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 1rem;
            border-left: 4px solid var(--primary-purple);
            transition: transform 0.2s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-2px);
        }
        
        .metric-title {
            color: var(--text-dark);
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        
        .metric-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary-purple);
            margin-bottom: 0.5rem;
        }
        
        .metric-assessment {
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 500;
        }
        
        .assessment-optimal {
            background-color: #C6F6D5;
            color: #22543D;
        }
        
        .assessment-suboptimal {
            background-color: #FED7D7;
            color: #822727;
        }
        
        /* Graph Section Styling */
        .graph-section {
            background: var(--white);
            border-radius: 12px;
            padding: 1.5rem;
            margin-top: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .graph-title {
            color: var(--text-dark);
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--light-gray);
        }
        
        /* Header Styling */
        .page-header {
            text-align: center;
            padding: 2rem 0;
            margin-bottom: 2rem;
            background: linear-gradient(135deg, var(--primary-purple), var(--accent-blue));
            color: var(--white);
            border-radius: 12px;
        }
        
        .header-title {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        
        .header-subtitle {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .section-title {
            color: var(--text-dark);
            font-size: 1.5rem;
            font-weight: 600;
            margin: 2rem 0 1rem 0;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--light-gray);
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Page Header
    st.markdown("""
        <div class="page-header">
            <div class="header-title">TPMS Scaffold Performance Predictor</div>
            <div class="header-subtitle">Advanced Analysis and Visualization Tool</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Input for porosity with styled slider
    porosity = st.slider("Select Porosity (%)", min_value=30, max_value=90, value=60, step=1)
    
    # Submit button with custom styling
    st.markdown("""
        <style>
        .stButton > button {
            background: linear-gradient(135deg, var(--primary-purple), var(--accent-blue));
            color: white;
            border: none;
            padding: 0.75rem 2rem;
            font-weight: 600;
            width: 100%;
            transition: all 0.3s ease;
        }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(107, 70, 193, 0.2);
        }
        </style>
    """, unsafe_allow_html=True)
    
    if st.button("Simulate"):
        simulator = TPMSScaffoldSimulator()
        results = simulator.get_values(porosity)
        interpretations = simulator.interpret_results(results)
        
        # Results Section
        st.markdown(f"<h2 style='color: var(--text-dark); margin-top: 2rem;'>Scaffold Properties Analysis for {porosity}% Porosity</h2>", unsafe_allow_html=True)
        
        # Create three columns for metrics
        col1, col2, col3 = st.columns(3)
        
        # Column 1 Metrics
        with col1:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Stress</div>
                    <div class="metric-value">{results['stress']:.4f} MPa</div>
                    <div class="metric-assessment {'assessment-optimal' if 'Optimal' in interpretations['stress'] else 'assessment-suboptimal'}">
                        {interpretations['stress']}
                    </div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-title">Flow Rate</div>
                    <div class="metric-value">{results['flow_rate']:.3f} mL/min</div>
                    <div class="metric-assessment {'assessment-optimal' if 'Optimal' in interpretations['flow_rate'] else 'assessment-suboptimal'}">
                        {interpretations['flow_rate']}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        # Column 2 Metrics
        with col2:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Strain</div>
                    <div class="metric-value">{results['strain']:.4f}</div>
                    <div class="metric-assessment {'assessment-optimal' if 'Optimal' in interpretations['strain'] else 'assessment-suboptimal'}">
                        {interpretations['strain']}
                    </div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-title">Shear Stress</div>
                    <div class="metric-value">{results['shear_stress']:.2f} Pa</div>
                    <div class="metric-assessment {'assessment-optimal' if 'Optimal' in interpretations['shear_stress'] else 'assessment-suboptimal'}">
                        {interpretations['shear_stress']}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        # Column 3 Metrics
        with col3:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Mechanical Strength</div>
                    <div class="metric-value">{results['mechanical_strength']:.2f}%</div>
                    <div class="metric-assessment {'assessment-optimal' if 'Excellent' in interpretations['mechanical_strength'] else 'assessment-suboptimal'}">
                        {interpretations['mechanical_strength']}
                    </div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-title">Cell Migration</div>
                    <div class="metric-value">{results['cell_migration']:.2f}%</div>
                    <div class="metric-assessment {'assessment-optimal' if 'Excellent' in interpretations['cell_migration'] else 'assessment-suboptimal'}">
                        {interpretations['cell_migration']}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        # Articular Cartilage Compatibility Section
        st.markdown("""
            <div class="section-title">Articular Cartilage Compatibility Analysis</div>
        """, unsafe_allow_html=True)
        
        tissue = 'articular_cartilage'
        requirements = TISSUE_PROPERTIES[tissue]
        compatibility_score, property_scores = evaluate_tissue_compatibility(results, requirements)
        
        # Determine recommendation status
        if compatibility_score >= 0.8:
            status = "Highly Suitable"
            assessment_class = "assessment-optimal"
        elif compatibility_score >= 0.50:
            status = "Suitable"
            assessment_class = "assessment-optimal"
        else:
            status = "Not Recommended"
            assessment_class = "assessment-suboptimal"
        
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Overall Compatibility Score</div>
                <div class="metric-value">{compatibility_score:.2f}</div>
                <div class="metric-assessment {assessment_class}">
                    {status}
                </div>
            </div>
            
            <p><strong>Description:</strong> {requirements['description']}</p>
        """, unsafe_allow_html=True)
        
        # Display property scores for articular cartilage
        cols = st.columns(2)
        for idx, (prop, score) in enumerate(property_scores.items()):
            is_critical = prop in requirements['critical_factors']
            with cols[idx % 2]:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-title">{prop.replace('_', ' ').title()} {' (Critical)' if is_critical else ''}</div>
                        <div class="metric-value">{score:.2f}</div>
                        <div class="metric-assessment {get_recommendation_class(score)}">
                            {'Optimal' if score >= 0.8 else 'Needs Improvement'}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        
        # Graphs Section
        st.markdown("""
            <div class="graph-section">
                <div class="graph-title">Stress-Strain Relationship</div>
            </div>
        """, unsafe_allow_html=True)
        st.pyplot(simulator.plot_stress_strain(porosity))
        
        st.markdown("""
            <div class="graph-section">
                <div class="graph-title">Flow Rate Analysis</div>
            </div>
        """, unsafe_allow_html=True)
        st.pyplot(simulator.plot_flow_rate(porosity))
        
        # Other Tissues Section
        st.markdown("""
            <div class="section-title">Potential for Other Tissue Applications</div>
        """, unsafe_allow_html=True)
        
        # Analyze compatibility for other tissue types
        for tissue, requirements in {k: v for k, v in TISSUE_PROPERTIES.items() if k != 'articular_cartilage'}.items():
            compatibility_score, property_scores = evaluate_tissue_compatibility(results, requirements)
            
            # Format tissue name
            tissue_name = tissue.replace('_', ' ').title()
            
            # Determine recommendation status
            if compatibility_score >= 0.8:
                status = "Highly Suitable"
                assessment_class = "assessment-optimal"
            elif compatibility_score >= 0.6:
                status = "Suitable"
                assessment_class = "assessment-optimal"
            else:
                status = "Not Recommended"
                assessment_class = "assessment-suboptimal"
            
            # Create expandable section
            with st.expander(f"{tissue_name} - {status}"):
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-title">Compatibility Score</div>
                        <div class="metric-value">{compatibility_score:.2f}</div>
                        <div class="metric-assessment {assessment_class}">
                            {status}
                        </div>
                    </div>
                    
                    <p><strong>Description:</strong> {requirements['description']}</p>
                    <p><strong>Critical Properties:</strong></p>
                """, unsafe_allow_html=True)
                
                # Display property scores
                cols = st.columns(2)
                for idx, (prop, score) in enumerate(property_scores.items()):
                    is_critical = prop in requirements['critical_factors']
                    with cols[idx % 2]:
                        st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-title">{prop.replace('_', ' ').title()} {' (Critical)' if is_critical else ''}</div>
                                <div class="metric-value">{score:.2f}</div>
                                <div class="metric-assessment {get_recommendation_class(score)}">
                                    {'Optimal' if score >= 0.8 else 'Needs Improvement'}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)


def is_valid_email(email):
    """Check if email is valid"""
    pattern = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
    return re.match(pattern, email) is not None

def is_valid_name(name):
    """Check if name contains at least first and last name"""
    return len(name.strip().split()) >= 2

def technicalsupport_page():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Color Variables - Matching home page */
:root {
    --primary-blue: #2C3E50;
    --secondary-blue: #3498DB;
    --accent-purple: #9B59B6;
    --accent-green: #27AE60;
    --light-gray: #F8F9FA;
    --medium-gray: #95A5A6;
    --dark-gray: #2C3E50;
    --white: #FFFFFF;
    --error-red: #E53E3E;
}

/* Global Styles */
.stApp {
    font-family: 'Inter', sans-serif;
    background-color: var(--light-gray);
}

/* Header Styling - Matching hero section from home page */
.support-header {
    text-align: center;
    margin-bottom: 3rem;
    background: linear-gradient(135deg, var(--primary-blue), var(--accent-purple));
    padding: 3rem 1rem;
    border-radius: 12px;
    color: var(--white);
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.header-title {
    font-size: 2.5rem;
    font-weight: 700;
    color: var(--white);
    margin-bottom: 1rem;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
}

.header-subtitle {
    font-size: 1.25rem;
    color: var(--light-gray);
    max-width: 600px;
    margin: 0 auto;
}

/* Input Fields */
.stTextInput > div > div {
    background: var(--light-gray);
    border: 1px solid var(--medium-gray);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    transition: all 0.3s ease;
}

.stTextInput > div > div:focus-within {
    border-color: var(--secondary-blue);
    box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
}

.stTextArea > div > div {
    background: var(--light-gray);
    border: 1px solid var(--medium-gray);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    min-height: 150px;
    transition: all 0.3s ease;
}

.stTextArea > div > div:focus-within {
    border-color: var(--secondary-blue);
    box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
}

/* Submit Button */
.stButton > button {
    background: linear-gradient(135deg, var(--primary-blue), var(--accent-purple));
    color: var(--white);
    border: none;
    padding: 1rem 2rem;
    font-weight: 600;
    width: 100%;
    border-radius: 8px;
    font-size: 1.125rem;
    transition: all 0.3s ease;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 1rem;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(44, 62, 80, 0.2);
}

/* Success Message */
.success-message {
    background-color: rgba(39, 174, 96, 0.1);
    color: var(--accent-green);
    padding: 1rem;
    border-radius: 8px;
    text-align: center;
    font-weight: 500;
    margin-top: 1rem;
}

/* Required Field Label */
.required-field {
    color: var(--error-red);
    font-weight: bold;
}

/* Helper Text */
.helper-text {
    font-size: 0.875rem;
    color: var(--dark-gray);
    margin-top: 0.25rem;
}

/* Error Message */
.error-message {
    color: var(--error-red);
    font-size: 0.875rem;
    margin-top: 0.25rem;
}
        </style>
    """, unsafe_allow_html=True)
    
    # Header Section
    st.markdown("""
        <div class="support-header">
            <div class="header-title">Technical Support</div>
            <div class="header-subtitle">
                We're here to help! Please fill out the form below with your concerns or recommendations, 
                and our support team will get back to you as soon as possible.
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Email Configuration
    email_config = {
        "sender_email": "mabborangmykha@gmail.com",  # Your actual Gmail address
        "sender_password": "wmck uwcm mxat yldi",  # Your 16-character app password
        "receiver_email": "aggabaokc@gmail.com",
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587
    }
    
    # Send Email Function
    def send_email(name, email, concern):
        msg = EmailMessage()
        msg.set_content(f"""
            Name: {name}
            Email: {email}
            
            Concern/Recommendation:
            {concern}
        """)
        msg["Subject"] = f"Technical Support Request from {name}"
        msg["From"] = email_config["sender_email"]
        msg["To"] = email_config["receiver_email"]
        
        try:
            with smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"]) as smtp:
                smtp.starttls()
                smtp.login(email_config["sender_email"], email_config["sender_password"])
                smtp.send_message(msg)
            return True
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            return False
    
    # Support Form
    st.markdown('<div class="support-form">', unsafe_allow_html=True)
    
    with st.form("support_form"):
        st.markdown('<p class="helper-text">Fields marked with <span class="required-field">*</span> are required</p>', 
                   unsafe_allow_html=True)
        
        name = st.text_input("Full Name :red[*]", 
                            placeholder="Enter your full name (First and Last name)",
                            help="Please enter your complete name (First and Last name)")
        
        email = st.text_input("Gmail Address :red[*]", 
                             placeholder="Enter your Gmail address",
                             help="Please enter a valid Gmail address")
        
        concern = st.text_area("Concern or Recommendation :red[*]", 
                             placeholder="Please describe your concern or recommendation in detail...")
        
        submit_button = st.form_submit_button("Submit Request")
        
        if submit_button:
            # Validate all fields are filled
            if not all([name, email, concern]):
                st.error("Please fill in all required fields.")
                return
            
            # Validate name format
            if not is_valid_name(name):
                st.error("Please enter your complete name (First and Last name).")
                return
            
            # Validate email format
            if not is_valid_email(email):
                st.error("Please enter a valid Gmail address (example@gmail.com).")
                return
            
            # If all validations pass, send email
            if send_email(name, email, concern):
                st.markdown("""
                    <div class="success-message">
                        Thank you for your submission! Our support team will contact you shortly.
                    </div>
                """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def home_page():
   # Custom CSS with updated color palette
   st.markdown("""
       <style>
       /* Color Variables */
       :root {
           --primary-blue: #2C3E50;
           --secondary-blue: #3498DB;
           --accent-purple: #9B59B6;
           --accent-green: #27AE60;
           --light-gray: #F8F9FA;
           --medium-gray: #95A5A6;
           --dark-gray: #2C3E50;
           --white: #FFFFFF;
       }
      
       /* Main container styling */
       .main-container {
           max-width: 1200px;
           margin: auto;
           padding: 2rem;
           background-color: var(--light-gray);
       }
      
       /* Hero section styling */
       .hero-section {
           text-align: center;
           margin-bottom: 3rem;
           background: linear-gradient(135deg, var(--primary-blue), var(--accent-purple));
           padding: 3rem 1rem;
           border-radius: 12px;
           color: var(--white);
       }
      
       .hero-title {
           font-size: 2.5rem;
           color: var(--white);
           margin-bottom: 1rem;
           text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
       }
      
       .hero-subtitle {
           font-size: 1.25rem;
           color: var(--light-gray);
           max-width: 600px;
           margin: 0 auto;
       }
      
       /* Card styling */
       .stcard {
           background-color: var(--white);
           border-radius: 12px;
           padding: 1.5rem;
           margin-bottom: 1.5rem;
           box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
           border-top: 4px solid var(--secondary-blue);
           transition: transform 0.2s ease-in-out;
       }
      
       .stcard:hover {
           transform: translateY(-2px);
       }
      
       .parameters-card {
           border-top-color: var(--accent-purple);
       }
      
       .outputs-card {
           border-top-color: var(--accent-green);
       }
      
       .card-title {
           font-size: 1.25rem;
           color: var(--primary-blue);
           margin-bottom: 1rem;
           font-weight: 600;
           display: flex;
           align-items: center;
           gap: 0.5rem;
       }
      
       .card-title:before {
           content: "•";
           color: var(--secondary-blue);
           font-size: 1.5rem;
       }
      
       .card-content {
           color: var(--dark-gray);
           line-height: 1.6;
       }
      
       /* List styling */
       .custom-list {
           list-style-type: none;
           padding-left: 0;
       }
      
       .custom-list li {
           display: flex;
           align-items: center;
           margin-bottom: 0.75rem;
           color: var(--dark-gray);
           padding: 0.5rem;
           border-radius: 6px;
           transition: background-color 0.2s ease;
       }
      
       .custom-list li:hover {
           background-color: var(--light-gray);
       }
      
       .custom-list li:before {
           content: "→";
           color: var(--secondary-blue);
           margin-right: 0.75rem;
           font-weight: bold;
       }
      
       /* Property box styling */
       .property-box {
           background-color: var(--light-gray);
           padding: 1rem;
           border-radius: 8px;
           margin-bottom: 0.75rem;
           border-left: 4px solid var(--accent-purple);
           transition: transform 0.2s ease;
       }
      
       .property-box:hover {
           transform: translateX(4px);
       }
      
       /* Tab styling */
       .stTabs [data-baseweb="tab-list"] {
           gap: 1rem;
           background-color: var(--white);
           padding: 1rem;
           border-radius: 12px;
           box-shadow: 0 2px 4px rgba(0,0,0,0.1);
       }
      
       .stTabs [data-baseweb="tab"] {
           padding: 1rem 2rem;
           color: var(--dark-gray);
           border-radius: 8px;
       }
      
       .stTabs [data-baseweb="tab-highlight"] {
           background-color: var(--secondary-blue);
       }
      
       /* Steps styling */
       .steps-list {
           counter-reset: steps;
           list-style-type: none;
           padding-left: 0;
       }
      
       .steps-list li {
           position: relative;
           padding-left: 3rem;
           margin-bottom: 1rem;
           counter-increment: steps;
       }
      
       .steps-list li:before {
           content: counter(steps);
           position: absolute;
           left: 0;
           width: 2rem;
           height: 2rem;
           background-color: var(--accent-green);
           color: var(--white);
           border-radius: 50%;
           display: flex;
           align-items: center;
           justify-content: center;
           font-weight: bold;
       }
      
       /* Additional styling for specific sections */
       .section-overview {
           border-left: 4px solid var(--secondary-blue);
           padding-left: 1rem;
       }
      
       .section-parameters {
           border-left: 4px solid var(--accent-purple);
           padding-left: 1rem;
       }
      
       .section-outputs {
           border-left: 4px solid var(--accent-green);
           padding-left: 1rem;
       }
       </style>
   """, unsafe_allow_html=True)


   # Hero Section with gradient background
   st.markdown("""
       <div class="hero-section">
           <h1 class="hero-title">WELCOME TO SCARTIX</h1>
           <p class="hero-subtitle">
               Advanced Predictive Tool for Chitosan-based TPMS Scaffolds for Articular Cartilage Tissue Regeneration
           </p>
       </div>
   """, unsafe_allow_html=True)


   # Tab Navigation
   tab1, tab2, tab3, tab4 = st.tabs([
       "Overview",
       "Parameters",
       "Outputs",
       "Usage Guide"
   ])


   # Overview Tab
   with tab1:
       st.markdown("""
           <div class="stcard section-overview">
               <h2 class="card-title">About SCARTIX</h2>
               <div class="card-content">
                   <p>
                       SCARTIX is a pioneering program designed to predict the performance
                       of chitosan-based TPMS scaffolds in articular cartilage tissue regeneration.
                       It provides advanced predictive tools to support researchers and professionals
                       in optimizing scaffold designs, facilitating innovative solutions in the
                       field of regenerative medicine.
                   </p>
               </div>
           </div>
                   <div class="stcard section-overview">
               <h2 class="card-title">About CHITOSAN</h2>
               <div class="card-content">
                   <p>
                       Chitosan, a natural polysaccharide derived from chitin, is valued in tissue engineering for its biocompatibility, biodegradability, and minimal foreign-body response. These properties make it a suitable material for scaffold development in tissue regeneration (Wang et al., 2023).
                   </p>
               </div>
           </div>
                   <div class="stcard section-overview">
               <h2 class="card-title">Why CHITOSAN?</h2>
               <div class="card-content">
                   <p>
                       Ressler (2022) states that chitosan's structure enables chemical and mechanical alterations to produce unique properties, functions, and applications. Chitosan and its polymer-based composites are frequently used in material development due to the polysaccharide structure's similarity to cartilage glycosaminoglycans and the ability to guide mesenchymal stem cells (MSC) differentiation towards chondrocyte cell type (chondrogenesis). To simulate natural bone tissue and induce development into osteoblast cell types (osteogenesis), chitosan-based scaffolds are frequently mixed with inorganic phases.
                   </p>
               </div>
           </div>
       """, unsafe_allow_html=True)


   # Parameters Tab
   with tab2:
       col1, col2 = st.columns(2)
      
       with col1:
           st.markdown("""
               <div class="stcard parameters-card">
                   <h2 class="card-title">Base Biomaterial</h2>
                   <ul class="custom-list">
                       <li>Chitosan</li>
                   </ul>
               </div>
                       <div class="stcard parameters-card">
                   <h2 class="card-title">Coming Soon</h2>
                   <ul class="custom-list">
                       <li>Titanium</li>
                       <li>Collagen (Type II)</li>
                   </ul>
               </div>
           """, unsafe_allow_html=True)
          
       with col2:
           st.markdown("""
               <div class="stcard parameters-card">
                   <h2 class="card-title">Porosity Range</h2>
                   <p class="card-content">Percentage of void space in the scaffold</p>
                   <div class="property-box">
                       <strong>Minimum:</strong> 30%
                   </div>
                   <div class="property-box">
                       <strong>Maximum:</strong> 90%
                   </div>
               </div>
           """, unsafe_allow_html=True)


   # Outputs Tab
   with tab3:
       col1, col2 = st.columns(2)
      
       with col1:
           st.markdown("""
               <div class="stcard outputs-card">
                   <h2 class="card-title">Mechanical Properties</h2>
                   <ul class="custom-list">
                       <li>Compressive Strength</li>
                       <li>Elastic Modulus</li>
                       <li>Stress-Strain Behavior</li>
                   </ul>
               </div>
           """, unsafe_allow_html=True)
          
       with col2:
           st.markdown("""
               <div class="stcard outputs-card">
                   <h2 class="card-title">Biological Properties</h2>
                   <ul class="custom-list">
                       <li>Cell Viability</li>
                       <li>Proliferation Rate</li>
                       <li>Growth Curves</li>
                   </ul>
               </div>
           """, unsafe_allow_html=True)


   # Usage Guide Tab
   with tab4:
       st.markdown("""
           <div class="stcard">
               <h2 class="card-title">Getting Started</h2>
               <p class="card-content">Follow these steps to begin using SCARTIX for your research:</p>
               <ol class="steps-list">
                   <li>Create an account with your institutional email</li>
                   <li>Navigate to the Predictor page from the main dashboard</li>
                   <li>Input your desired porosity percentage using the slider</li>
                   <li>Click "Simulate" to generate predictions and visualizations</li>
                   <li>Review the comprehensive results and save them for future reference</li>
               </ol>
           </div>
       """, unsafe_allow_html=True)


# --- Run App ---
if not st.session_state.logged_in:
   login_page()
else:
   main_app()
