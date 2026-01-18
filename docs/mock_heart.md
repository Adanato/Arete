---
arete: true
deck: Medicine::Anatomy::Heart
tags:
  - anatomy
  - cardiology
  - arete/retention/high
cards:
  # --- 1. Basic Structure (The Foundation) ---
  - id: arete_heart_struct_01
    model: Basic
    Front: "What are the four chambers of the heart?"
    Back: "Right Atrium, Right Ventricle, Left Atrium, Left Ventricle"
    deps:
      requires: []
      related: [arete_heart_struct_02, arete_heart_struct_03, arete_heart_flow_01, arete_heart_elec_01]

  - id: arete_heart_struct_02
    model: Basic
    Front: "Which septum separates the atria?"
    Back: "Interatrial Septum"
    deps:
      requires: [arete_heart_struct_01]
      related: [arete_heart_elec_02, arete_heart_embryo_01]

  - id: arete_heart_struct_03
    model: Basic
    Front: "Which septum separates the ventricles?"
    Back: "Interventricular Septum"
    deps:
      requires: [arete_heart_struct_01]
      related: [arete_heart_elec_04, arete_heart_supply_02]

  # --- 2. Blood Flow (The Process) ---
  - id: arete_heart_flow_01
    model: Basic
    Front: "Blood enters the Right Atrium via which vessels?"
    Back: "Superior and Inferior Vena Cava"
    deps:
      requires: [arete_heart_struct_01]
      related: [arete_heart_path_03, arete_heart_flow_05]

  - id: arete_heart_flow_02
    model: Basic
    Front: "Blood flows from Right Atrium to Right Ventricle through which valve?"
    Back: "Tricuspid Valve"
    deps:
      requires: [arete_heart_flow_01]
      related: [arete_heart_flow_06, arete_heart_elec_03]

  - id: arete_heart_flow_03
    model: Basic
    Front: "Blood leaves the Right Ventricle through which valve?"
    Back: "Pulmonary Valve"
    deps:
      requires: [arete_heart_flow_02]
      related: [arete_heart_flow_07, arete_heart_path_03]

  - id: arete_heart_flow_04
    model: Basic
    Front: "Where does blood go after passing the Pulmonary Valve?"
    Back: "Pulmonary Arteries (to lungs)"
    deps:
      requires: [arete_heart_flow_03]
      related: [arete_heart_embryo_02, arete_heart_flow_05]

  - id: arete_heart_flow_05
    model: Basic
    Front: "Oxygenated blood returns to the Left Atrium via?"
    Back: "Pulmonary Veins"
    deps:
      requires: [arete_heart_flow_04]
      related: [arete_heart_flow_01, arete_heart_path_04]

  - id: arete_heart_flow_06
    model: Basic
    Front: "Blood flows from Left Atrium to Left Ventricle through which valve?"
    Back: "Mitral (Bicuspid) Valve"
    deps:
      requires: [arete_heart_flow_05]
      related: [arete_heart_flow_02, arete_heart_path_02]

  - id: arete_heart_flow_07
    model: Basic
    Front: "Blood leaves the Left Ventricle through which valve?"
    Back: "Aortic Valve"
    deps:
      requires: [arete_heart_flow_06]
      related: [arete_heart_flow_03, arete_heart_phys_05]

  # --- 3. Electrical System (The Driver) ---
  - id: arete_heart_elec_01
    model: Basic
    Front: "What is the primary pacemaker of the heart?"
    Back: "Sinoatrial (SA) Node"
    deps:
      requires: [arete_heart_struct_01]
      related: [arete_heart_supply_01, arete_heart_path_01, arete_heart_phys_02]

  - id: arete_heart_elec_02
    model: Basic
    Front: "Where does the electrical signal go after the SA Node?"
    Back: "Atrioventricular (AV) Node"
    deps:
      requires: [arete_heart_elec_01]
      related: [arete_heart_struct_02, arete_heart_elec_03]

  - id: arete_heart_elec_03
    model: Basic
    Front: "What delays the signal at the AV node?"
    Back: "To allow atria to contract fully before ventricles"
    deps:
      requires: [arete_heart_elec_02]
      related: [arete_heart_flow_02, arete_heart_flow_06]

  - id: arete_heart_elec_04
    model: Basic
    Front: "What carries the signal down the septum?"
    Back: "Bundle of His"
    deps:
      requires: [arete_heart_elec_02]
      related: [arete_heart_struct_03, arete_heart_supply_02]

  - id: arete_heart_elec_05
    model: Basic
    Front: "What fibers distribute the signal to ventricular muscle?"
    Back: "Purkinje Fibers"
    deps:
      requires: [arete_heart_elec_04]
      related: [arete_heart_struct_01]

  # --- 4. Clinical Correlates (Application) ---
  - id: arete_heart_path_01
    model: Basic
    Front: "What is Atrial Fibrillation?"
    Back: "Disorganized electrical activity in atria"
    deps:
      requires: [arete_heart_elec_01]
      related: [arete_heart_flow_02, arete_heart_phys_02]

  - id: arete_heart_path_02
    model: Basic
    Front: "What valve is most commonly affected by Rheumatic Fever?"
    Back: "Mitral Valve"
    deps:
      requires: [arete_heart_flow_06]
      related: [arete_heart_flow_02]

  - id: arete_heart_path_03
    model: Basic
    Front: "Right-sided heart failure causes edema where?"
    Back: "Peripheral (legs, liver)"
    deps:
      requires: [arete_heart_flow_02, arete_heart_flow_03]
      related: [arete_heart_flow_01, arete_heart_path_04]

  - id: arete_heart_path_04
    model: Basic
    Front: "Left-sided heart failure causes edema where?"
    Back: "Pulmonary (lungs)"
    deps:
      requires: [arete_heart_flow_06, arete_heart_flow_07]
      related: [arete_heart_flow_05, arete_heart_path_03, arete_heart_phys_03]

  # --- 5. Coronary Circulation (Supply) ---
  - id: arete_heart_supply_01
    model: Basic
    Front: "Which artery supplies the SA Node?"
    Back: "RCA (Right Coronary Artery) in 60% of people"
    deps:
      requires: [arete_heart_elec_01]
      related: [arete_heart_struct_01]

  - id: arete_heart_supply_02
    model: Basic
    Front: "Which artery supplies the anterior septum?"
    Back: "LAD (Left Anterior Descending)"
    deps:
      requires: [arete_heart_struct_03]
      related: [arete_heart_elec_04, arete_heart_supply_03]

  - id: arete_heart_supply_03
    model: Basic
    Front: "Infarction of the LAD implies damage to which wall?"
    Back: "Anterior Wall of Left Ventricle"
    deps:
      requires: [arete_heart_struct_01, arete_heart_supply_02]
      related: [arete_heart_flow_07]

  # --- 6. Embryology (Origins) ---
  - id: arete_heart_embryo_01
    model: Basic
    Front: "What structure forms the Atrial Septum?"
    Back: "Septum Primum and Septum Secundum"
    deps:
      requires: [arete_heart_struct_02]
      related: [arete_heart_embryo_02]

  - id: arete_heart_embryo_02
    model: Basic
    Front: "What is the Foramen Ovale?"
    Back: "Opening between atria in fetus"
    deps:
      requires: [arete_heart_embryo_01]
      related: [arete_heart_flow_04, arete_heart_embryo_03]

  - id: arete_heart_embryo_03
    model: Basic
    Front: "Why does the Foramen Ovale close?"
    Back: "Pressure in LA becomes > RA after birth"
    deps:
      requires: [arete_heart_embryo_02]
      related: [arete_heart_flow_05]

  # --- 7. Physiology (Numbers) ---
  - id: arete_heart_phys_01
    model: Basic
    Front: "What is Stroke Volume?"
    Back: "EDV - ESV"
    deps:
      requires: [arete_heart_struct_01]
      related: [arete_heart_phys_02, arete_heart_phys_03]

  - id: arete_heart_phys_02
    model: Basic
    Front: "What is Cardiac Output?"
    Back: "HR x SV"
    deps:
      requires: [arete_heart_phys_01, arete_heart_elec_01]
      related: [arete_heart_flow_07]

  - id: arete_heart_phys_03
    model: Basic
    Front: "What is Ejection Fraction?"
    Back: "SV / EDV (Normal > 55%)"
    deps:
      requires: [arete_heart_phys_01]
      related: [arete_heart_path_04]

  - id: arete_heart_phys_04
    model: Basic
    Front: "Preload is approximated by?"
    Back: "EDV (End Diastolic Volume)"
    deps:
      requires: [arete_heart_phys_01]
      related: [arete_heart_flow_05]

  - id: arete_heart_phys_05
    model: Basic
    Front: "Afterload is approximated by?"
    Back: "MAP (Mean Arterial Pressure)"
    deps:
      requires: [arete_heart_flow_07]
      related: [arete_heart_path_04]---
# Heart Anatomy & Physiology

This file contains 30 cards interlinked to demonstrate complex dependency graph visualization.

## Structure
- **Struct**: Basic chambers and walls.
- **Flow**: Path of blood.
- **Elec**: Conduction system.
- **Path**: Diseases (depend on structure/flow).
- **Supply**: Coronary arteries (depend on structure).
- **Embryo**: Formation (depends on structure).
- **Phys**: Formulas (depend on concepts).
