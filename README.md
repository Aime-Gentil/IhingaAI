# IhingaAI — Smarter Farming Together

**An AI-Assisted Agricultural Decision-Support Platform for Rwanda**

**Team:** Pioneers  
**Competition:** NISR Hackathon 2026  
**Track:** Agricultural Productivity

**[Live Application](https://ihingaai-pioneers.streamlit.app)** | **[GitHub Repository](https://github.com/Aime-Gentil/IhingaAI)**

## 1. Project Overview

IhingaAI is an agricultural decision-support platform that helps Rwandan farmers, agronomists, and agricultural planners make informed decisions using data, machine learning, and artificial intelligence.

The platform integrates harvest estimation, crop monitoring, weather information, market prices, farm financial management, and agricultural guidance into one accessible application.

Its goal is to transform agricultural data into practical insights that support better farming decisions and improved productivity.

## 2. Problem Statement

Many farmers have limited access to timely and relevant agricultural information, making it difficult to predict harvest outcomes, identify risks, manage production costs, and plan farming activities effectively.

Agronomists and agricultural planners also need better access to organized field information to support farmers and understand agricultural patterns.

IhingaAI addresses these challenges by connecting agricultural data with practical decision-support tools.

## 3. Key Features

| Feature | Description |
|---|---|
| Harvest Estimation | Estimates production for 14 supported crops using trained machine-learning models. |
| Field Management | Registers fields and maintains farm records and estimation history. |
| AI Assistant | Provides personalized agricultural guidance using Google Gemini. |
| Crop Monitoring | Tracks crop stages, field observations, and photographs. |
| Weather Forecasts | Provides district-level forecasts to support farm planning. |
| Risk Assessment | Identifies potential farming risks using available information. |
| Market Information | Displays available agricultural market-price information. |
| Farm Finances | Tracks recorded expenses, sales, and cash-flow trends. |
| Farm Activities | Organizes activities, calendars, and reminders. |
| Agronomist Support | Enables consultations and permission-based information sharing. |
| Planning Analytics | Provides agricultural summaries and analytical insights. |

## 4. User Roles

**Farmers:** Register fields, estimate harvests, monitor crops, evaluate risks, track finances, and access agricultural guidance.

**Agronomists:** Review authorized farmer information, respond to consultations, and provide professional support.

**Planners:** Access agricultural analytics and planning information. Account creation requires administrator authorization.

## 5. Data and Methodology

IhingaAI uses historical agricultural observations associated with Rwanda's **2025 Seasonal Agricultural Survey (SAS)** from the National Institute of Statistics of Rwanda (NISR).

Two frozen machine-learning models support harvest estimation across 14 crops and their supported agricultural seasons.

Predictions use inputs such as crop type, season, district, farmer type, and cultivated area. Results include estimated production, an uncertainty range, and supporting information.

Google Gemini provides optional AI-generated recommendations, while Open-Meteo supplies weather forecasts.

**Note:** Model estimates are based on historical evidence and should not be interpreted as guaranteed harvest outcomes. AI guidance does not replace qualified agricultural expertise.

Further details are available in `DATA_SOURCES.md`.

## 6. Technology Stack

| Component | Technology |
|---|---|
| Language | Python |
| Application | Streamlit |
| Data Processing | Pandas, NumPy |
| Machine Learning | Scikit-learn |
| Generative AI | Google Gemini |
| Visualization | Plotly |
| Database | SQLite |
| Weather API | Open-Meteo |
| Version Control | Git, GitHub |
| Deployment | Streamlit Community Cloud |

## 7. Installation

**Requirements:** Python 3.11 and the dependencies specified in `requirements.txt`.

Clone the repository:

```bash
git clone https://github.com/Aime-Gentil/IhingaAI.git
cd IhingaAI
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the application:

```bash
python -m streamlit run app.py
```

AI functionality requires a Gemini API key configured through Streamlit Secrets. API keys and private user information must never be committed to GitHub.

## 8. Limitations and Future Improvements

IhingaAI is currently a hackathon prototype intended for demonstration and further evaluation.

Current limitations include:

- Local SQLite data may be lost after cloud restarts or redeployments.
- Harvest predictions depend on historical data quality and model coverage.
- Weather forecasts are district-level rather than field-specific.
- Market prices may not represent current transactions.
- AI-generated recommendations require human judgment and verification.

Future development will prioritize persistent cloud storage, expanded model validation, stronger data protection, and improved agricultural recommendations.

## 9. Team and Acknowledgements

**Developed by Team Pioneers** for the NISR Hackathon 2026, Agricultural Productivity Track.

We acknowledge the National Institute of Statistics of Rwanda (NISR), Open-Meteo, and other information and technology providers supporting the project.

IhingaAI is an independent hackathon project.

**[Explore IhingaAI](https://ihingaai-pioneers.streamlit.app)**
