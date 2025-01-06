# SendSage - Climbing Analytics Platform

📊 **Transform your climbing data into actionable insights**

## Introduction

SendSage is your personal climbing analytics dashboard, designed to help athletes easily convert their Mountain Project Ticklist data into meaningful insights. The platform analyzes key performance metrics and provides comprehensive information such as total vertical distance climbed and location-based visualizations. Through engaging and interactive visualizations, SendSage helps athletes better understand their climbing performance and track their progression.

## Features

### Dashboard Overview

- **Quick Stats:** Total pitches, unique locations, favorite areas, and days outside
- **Experience Base Analytics:**
  - Base Volume: Climbing milestones, seasonal patterns, and work capacity analysis
  - Progression: Route length and difficulty tier development tracking
  - When & Where: Seasonal heatmaps, location hierarchies, and animated crag history

### Performance Analytics

- **Grade Tracking:** Highest clean sends across Sport, Trad, and Boulder
- **Recent Achievements:** Latest hard sends with attempt counts and locations
- **Advanced Analysis:**
  - Performance Pyramid: Interactive grade pyramids with send rates and project history
  - Performance Characteristics: Style analysis through energy systems, route length, and angle preferences

### Data Management

- **Easy Data Input:** Mountain Project Profile URL integration
- **Data Refresh:** On-demand data updates
- **Performance Data Verification:** Manual verification system for accurate analysis

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

[Click here to access SendSage](https://prototype-climbing-analytics-app.onrender.com/)
