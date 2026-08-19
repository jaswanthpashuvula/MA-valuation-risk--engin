# 📊 M&A Quantitative Risk & Valuation Pipeline

An automated quantitative finance engine built to streamline target asset valuation and market risk stress-testing for M&A desks.

## 🛠️ Tech Stack & Architecture
•⁠  ⁠*Language:* Python 3 (Pandas, NumPy, yfinance)
•⁠  ⁠*Database:* SQLite3 (Relational structure tracking 2,600+ entries)
•⁠  ⁠*Risk Engine:* 10,000-path stochastic Monte Carlo simulation

## 📈 System Execution Output
When executed locally, the end-to-end extraction pipeline populates the relational database, and the stochastic model outputs the following baseline risk thresholds:

⁠ text
🎲 Running 10,000 Monte Carlo simulation paths...

📊 RISK SIMULATION RESULTS:
➡️ Simulated Median Valuation: \$2384.07B
⚠️ 95% Corporate Value-at-Risk (VaR): \$1608.75B

✅ Simulation complete. Risk metrics tracked.
 ⁠

## 📁 Project System Architecture Documentation

### ⚙️ 1. Automated ETL Financial Ingestion Layer (⁠ extraction.py ⁠, ⁠ config.py ⁠)
•⁠  ⁠*Objective:* Mitigate core operational risks and data latency inherent in manual investment analyst financial statement inputs.
•⁠  ⁠*Mechanism:* Architected an asynchronous data extraction module utilizing the ⁠ yfinance ⁠ API framework to programmatically pull multi-ticker GAAP/IFRS balance sheets, income statements, and cash flow historical documentation. 

### 📊 2. Relational Analytics & Database Pipeline (⁠ metrics.py ⁠, ⁠ pipeline.py ⁠)
•⁠  ⁠*Objective:* Implement a high-integrity repository framework to clean and normalize raw structural accounting schedules into queryable data fields.
•⁠  ⁠*Mechanism:* Engineered a normalized, transactional SQLite data layout tracking nested historical profiles across revenue metrics and dynamic EBITDA margins.

### 📈 3. Predictive Valuation & DCF Engine (⁠ fcff.py ⁠)
•⁠  ⁠*Objective:* Construct a multi-variable algorithmic valuation matrix to automate structural forward-looking financial forecasting.
•⁠  ⁠*Mechanism:* Synthesizes historical peer parameters to auto-generate a 5-year discrete projection period for Free Cash Flows to Firm (FCFF). Computes WACC via CAPM to derive intrinsic per-share targets.

### 🎲 4. Stochastic Risk Simulation & Downside Stress-Testing (⁠ risk_simulation.py ⁠)
•⁠  ⁠*Objective:* Provide a sophisticated alternative to single-scenario analysis by quantifying corporate asset valuations across thousands of volatile macro environments.
•⁠  ⁠*Mechanism:* Deployed a high-density, 10,000-iteration Monte Carlo simulation engine utilizing ⁠ NumPy ⁠ vectorized execution logic. Applies continuous statistical distributions to systematically shock underlying parameters, implementing a strict ⁠ 95% Confidence Value-at-Risk (VaR) ⁠ optimization floor calculation.
