# Climbing Analytics Web Application

📊 **Gain actionable insights based on Athlete training and performance history**

## Introduction

This is a tool designed to help athletes easily convert their Mountain Project Ticklist data into actionable insights. The app analyzes pertinent performance metrics and provides fun information such as total vertical distance climbed and location-based bar chart races. The results are displayed as engaging visualizations to help athletes better understand their climbing performance and progress.

## Features

- **Seamless User Input:** Easy data input through Mountain Project Profile URL
- **Interactive Visualizations:** D3.js-powered custom displays of data trends.
- **Engaging Visuals:** Fun visualizations such as bar chart races showing climbing locations and their changes over time.
- **Progression Tracking:** Visualizations that illustrate how climbing performance has evolved over time.
- **Performance Insights:** A dedicated section for in-depth analysis of top-end performances.

## Technologies Used

### Backend

- **Python Flask:** Core web framework
- **SQLAlchemy:** Database ORM and management
- **PostgreSQL:** Relational database
- **Custom Services:** Modular architecture with specialized services for analytics, data processing, and climb classification

### Frontend

- **JavaScript/D3.js:** Interactive data visualizations and charts
- **HTML/CSS:** Modern, responsive design with modular CSS architecture
- **Custom Components:** Specialized visualization modules for different climbing metrics

### Deployment & Infrastructure

- **Heroku:** Cloud platform hosting
- **Git:** Version control
- **Database Migrations:** SQL-based schema management

## Step By Step- easy as 1,2,3

### Step 1: User inputs Mountain Project Profile URL

- App sends request to Mountain Project API.

### Step 2: Calculations are Performed

- Athlete data is cleaned and transformed into an appropriate analytical structure.
- Performance metrics and aggregate data are pre-calculated server-side.
- Data is stored in a relational database for efficient querying.

### Step 3: User can explore visualizations

- The database is queried to generate interactive visualizations of relevant data trends.
- Users can explore various aspects of their climbing performance through engaging and informative charts.

## Try it out!

[Click here to access the Climbing Analytics Web Application](https://climbing-analytics-app-test-d2e4a88e081a.herokuapp.com/)
