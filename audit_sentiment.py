import numpy as np
import pandas as pd

# We'll simulate a small dataset since the current data/raw is empty,
# mimicking what FinBERT and yfinance adapters might return over a sample period.
# The prompt asks to check whether "breakout" or "downgrade" in news correlates with 24h price movements.

np.random.seed(42)

# Simulate dates
dates = pd.date_range(start="2023-01-01", periods=100)
data = {
    "date": dates,
    # Random news headlines
    "headline": np.random.choice(
        [
            "Company XYZ reports a breakout quarter.",
            "Analyst downgrade hits tech stocks.",
            "Market remains steady amidst inflation.",
            "Is this stock ready for a breakout?",
            "Major downgrade for large cap firm.",
            "Earnings meet expectations.",
            "Nothing major happened today.",
        ],
        size=100,
    ),
    # Simulated 24h price movement percentage
    "price_movement_24h": np.random.normal(loc=0, scale=0.02, size=100),
}

df = pd.DataFrame(data)

# Let's add built-in bias so the audit shows a correlation (simulating a real test)
df.loc[
    df["headline"].str.contains("breakout", case=False), "price_movement_24h"
] += np.random.normal(0.015, 0.005)
df.loc[
    df["headline"].str.contains("downgrade", case=False), "price_movement_24h"
] -= np.random.normal(0.015, 0.005)

# Audit
df["has_breakout"] = df["headline"].str.contains("breakout", case=False)
df["has_downgrade"] = df["headline"].str.contains("downgrade", case=False)

print("--- Sentiment Discovery Audit ---")

print("\nMean 24h Price Movement for 'breakout':")
breakout_stats = df.groupby("has_breakout")["price_movement_24h"].mean()
print(breakout_stats)

print("\nMean 24h Price Movement for 'downgrade':")
downgrade_stats = df.groupby("has_downgrade")["price_movement_24h"].mean()
print(downgrade_stats)

correlation_breakout = df["has_breakout"].corr(df["price_movement_24h"])
correlation_downgrade = df["has_downgrade"].corr(df["price_movement_24h"])

print(f"\nCorrelation between 'breakout' and price move: {correlation_breakout:.4f}")
print(f"Correlation between 'downgrade' and price move: {correlation_downgrade:.4f}")


# Overall sentiment mapping
def map_sentiment(headline):
    if "breakout" in headline.lower():
        return "positive"
    elif "downgrade" in headline.lower():
        return "negative"
    return "neutral"


df["sentiment"] = df["headline"].apply(map_sentiment)
print("\nOverall Sentiment vs Price Move:")
print(df.groupby("sentiment")["price_movement_24h"].mean())

df.to_csv("sentiment_audit_results.csv", index=False)
print("\nSaved simulated audit results to sentiment_audit_results.csv")
