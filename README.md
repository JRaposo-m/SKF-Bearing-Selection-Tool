# SKF Bearing Selection Tool

Automated bearing selection and friction analysis tool based on SKF 
catalogue formulas, developed as part of a Mechanical Engineering 
project at FEUP.

## Overview

This tool replaces manual SKF catalogue analysis by implementing the 
SKF friction model formulas, allowing engineers to quickly evaluate 
and compare bearings based on their application requirements.

## Features

- SKF friction moment model (rolling, sliding and drag components)
- Parametric analysis (speed, load, viscosity)
- Stribeck curve generation
- Bearing selection based on load capacity and fatigue life (L10)
- Candidate bearing comparison and ranking

## Methods Implemented

- Rolling friction moment (M_rr)
- Sliding friction moment (M_sl)  
- Drag friction moment (M_drag)
- Dynamic load rating and L10 life (ISO 281)
- Stribeck parameter analysis

## Technologies
- Python
- NumPy
- Matplotlib


## References
- SKF General Catalogue
- ISO 281 — Rolling bearings — Dynamic load ratings and rating life
