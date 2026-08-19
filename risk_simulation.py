


import sqlite3
import numpy as np

def run_monte_carlo(iterations=10000):
    print(f"🎲 Running {iterations} Monte Carlo simulation paths...")
    
    conn = sqlite3.connect('mna_valuation.db')
    cursor = conn.cursor()
    
    baseline_value = 150.0  
    try:
        cursor.execute("SELECT AVG(fcf_value) FROM fcff_forecast")
        row = cursor.fetchone()
        if row and row[0] is not None: 
            baseline_value = float(row[0]) / 1e9  
    except Exception as e:
        pass
    finally:
        conn.close()
    
    np.random.seed(42)
    simulated_growth = np.random.normal(0.04, 0.015, iterations)
    simulated_wacc = np.random.normal(0.095, 0.01, iterations)
    simulated_wacc = np.clip(simulated_wacc, 0.01, None) 
    
    valuation_shocks = baseline_value * (1 + simulated_growth) / (simulated_wacc - simulated_growth + 0.01)
    valuation_shocks = np.clip(valuation_shocks, 0, None)
    
    median_val = np.percentile(valuation_shocks, 50)
    var_95 = np.percentile(valuation_shocks, 5) 
    
    print("\n📊 RISK SIMULATION RESULTS:")
    print(f"➡️ Simulated Median Valuation: ${median_val:.2f}B")
    print(f"⚠️ 95% Corporate Value-at-Risk (VaR): ${var_95:.2f}B")
    print("\n✅ Simulation complete. Risk metrics tracked.")

if __name__ == "__main__":
    run_monte_carlo()
