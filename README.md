
## IhingaAI | Agricultural Decision-Support System

**NISR Hackathon 2026 | Agricultural Productivity Track**

**Team Pioneers**
- Aime Gentil IZERIMANA
- Dative Akimana

## About IhingaAI

IhingaAI is a data-driven agricultural decision-support application designed to help Rwandan farmers improve farm management and make informed agricultural decisions.

The application combines machine-learning-based crop-production estimation, farm management, weather information, financial tracking, and AI-assisted agricultural guidance.

It provides dedicated dashboards for **Farmers, Agronomists, and Agricultural Planners**.

## Project Links

- **Live Application:** [Launch IhingaAI](https://ihingaai-pioneers.streamlit.app/)
- **Demonstration Video:** [Watch Demo](https://drive.google.com/file/d/1HkZN2P3bqKjj7SrVQSrFSIY3NqpEZ64u/view?usp=sharing)
- **Data Sources:** [View Sources](DATA_SOURCES.md)

## Key Features

- **Crop Production Prediction:** Machine-learning models estimate crop production using historical agricultural survey data.
- **Farm Management:** Register fields, manage farm details, and track activities.
- **Financial Tracking:** Record farm expenses, income, and financial summaries.
- **Weather and Market Information:** Access district-level weather forecasts and available market prices.
- **AI Agricultural Assistant:** Receive optional AI-powered explanations and farming guidance.
- **Agronomist Dashboard:** Support assigned farmers and provide agricultural advice.
- **Planner Dashboard:** Explore district analytics and agricultural planning information.

## Machine Learning and Datasets

IhingaAI uses supervised machine-learning models developed from prepared data derived from the **NISR 2025 Seasonal Agricultural Survey (SAS)**.

The project includes two trained model artifacts and their prepared modeling datasets.

| File | Purpose |
|---|---|
| [Baseline Dataset](data/IhingaAI_Baseline_Model_Data.pkl) | Prepared baseline modeling data |
| [Extension Dataset](data/IhingaAI_Extension_Model_Data.pkl) | Prepared extension modeling data |
| [Baseline Model](data/IhingaAI_Frozen_Model_v1.pkl) | Trained prediction model |
| [Extension Model](data/IhingaAI_Frozen_Extension_v1.pkl) | Trained extension model |

The models support historical-data-based production estimates, not guaranteed harvest outcomes.

## Technologies

Python, Streamlit, Scikit-learn, Pandas, NumPy, SQLite, Plotly, Open-Meteo, and optional Google Gemini integration.

## Installation and Usage

**1. Clone the repository**

```bash
git lfs install
git clone https://github.com/Aime-Gentil/IhingaAI.git
cd IhingaAI
git lfs pull
```

**2. Install dependencies**

```bash
python -m pip install -r requirements.txt
```

**3. Run the application**

```bash
python -m streamlit run app.py
```

Open the local URL displayed by Streamlit, usually `http://localhost:8501`.

Optional integrations may require private API configuration.

## Demonstration Accounts

The following accounts are provided for testing with the corresponding demonstration database.

| Role | Phone Number | Password |
|---|---|---|
| Farmer | `0798935073` | `Aims@2005` |
| Agronomist | `0798935083` | `Aims@2005` |
| Planner | `0798935063` | `Aims@2005` |

**Note:** The live deployment and locally downloaded project may use different database records. Demo accounts must exist in the database used by the running application.

## Important Notes

- IhingaAI is a hackathon prototype.
- Predictions are based on historical data and require further field validation.
- Weather, market, and AI services depend on external service availability.
- Local SQLite database changes may not persist after Streamlit Cloud restarts.
- The project documentation provides additional information about methodology, system design, evaluation, limitations, and future improvements.

## Team Pioneers

**Aime Gentil IZERIMANA and Dative Akimana**

Developed for the **NISR Hackathon Competition 2026**, Agricultural Productivity Track.
