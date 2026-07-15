🚦 Smart Green Corridor Simulation

📌 Overview

Smart Green Corridor is a simulation-based intelligent traffic management system that dynamically optimizes traffic signals and creates a green corridor for emergency vehicles (ambulances) using real-time traffic conditions.

This project leverages SUMO (Simulation of Urban Mobility) and Python-based algorithms to simulate and control traffic flow efficiently.


---

🏆 Achievement

🥈 1st Runner-Up at DIPEX 2026
Recognized for innovation in smart traffic systems and emergency response optimization.


---

🚀 Key Features

🚑 Ambulance Priority System

Automatically detects ambulance routes

Creates a green corridor by clearing traffic signals


🚦 Dynamic Traffic Control

Adjusts signal timing based on congestion


🧠 Simulation-Based Optimization

Uses SUMO for real-time traffic simulation


📡 Continuous Traffic Monitoring

Tracks vehicle density and flow


⚡ Automated Decision Making

Reduces human intervention




---

🏗️ Project Structure

SmartGreenCorridor/
│── api-test/tomtom-traffic/   # Traffic data API experiments
│── frontend/                  # UI (if applicable)
│── sumo_data/                 # SUMO simulation files
│── test/                      # Testing scripts
│
│── backend_ambulance_web.py
│── backend_ambulance_live_web.py
│── complete_phase0.py
│── phase0_network_setup.py
│── phase0_network_setup_v2.py
│── phase0_route_extractor.py
│── phase0_high_quality_network.py
│── phase1_backend.py
│── phase2_backend.py
│── phase2_traffic_generator.py
│── phase2_continuous_traffic.py
│── phase2_continuous_traffic_final.py
│── phase2_continuous_traffic_v2.py
│── phase2_ultra_light.py
│── phase3_ambulance_basic.py
│── phase3_traci_controller.py
│── test_ambulance_routing.py
│
│── routes.rou.xml             # Vehicle routes
│── requirements.txt           # Dependencies


---

⚙️ Working Principle

1. Traffic is simulated using SUMO


2. Vehicles and routes are generated dynamically


3. Ambulance route is identified


4. System:

Overrides traffic signals

Clears path ahead of ambulance



5. Traffic returns to normal after passage




---

🧠 Logic Flow

IF ambulance detected:
    Identify route
    Turn signals GREEN along path
    Stop cross traffic
ELSE:
    Adjust signals based on traffic density


---

🛠️ Tech Stack

Simulation: SUMO (Simulation of Urban Mobility)

Programming: Python

Libraries: TraCI (Traffic Control Interface)

Frontend: JavaScript (basic UI if used)



---

📊 Data Flow

SUMO Simulation → Python (TraCI नियंत्रण) → Signal Control Logic → Output Visualization


---

▶️ Setup & Installation

1️⃣ Clone Repository

git clone https://github.com/your-username/SmartGreenCorridor.git
cd SmartGreenCorridor

2️⃣ Install Dependencies

pip install -r requirements.txt

3️⃣ Install SUMO

Download from: https://www.eclipse.org/sumo/

Set environment variable:

export SUMO_HOME=/path/to/sumo

4️⃣ Run Simulation

python phase3_traci_controller.py


---

🧪 Use Cases

Smart city traffic systems 🚦

Emergency response optimization 🚑

Traffic research & simulations 📊

AI-based mobility solutions



---

🌟 Advantages

Saves critical emergency time

Reduces congestion

Scalable for real-world deployment

Data-driven decision making



---

🔮 Future Enhancements

🤖 AI-based traffic prediction

📍 Real-time GPS ambulance tracking

☁️ Cloud dashboard integration

📡 Live traffic API integration



---

👨‍💻 Authors

Gauravi Naik

Rahul Yadav

Krishna Bitthariya

Varun Mudaliyar
