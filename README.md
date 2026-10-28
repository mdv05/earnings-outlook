# Earnings Outlook

A concept for Roblox Creator Hub that helps creators plan around uneven income. Creator Hub shows what you earned. This shows what the next 90 days could look like, as a range instead of a single guess.

Built on **sample data**. Not affiliated with Roblox.

## What it does
- **90-day range:** low, likely and high earnings from 1,000 simulated futures
- **Credibility meter:** new experiences lean on similar ones until they build history, using the weight Z = n / (n + 45)
- **Cash-out planner:** chance of reaching the 30,000 Earned Robux DevEx minimum, and the likely date
- **Set-aside:** estimated taxes plus a cushion for the low case
- **What changed this week:** splits the change in revenue into more players vs more spending per player, by revenue stream
- **Early alert:** flags when the last 7 days fall below last week's outlook

## Why these methods
They come from actuarial work. Insurers price uncertain income with ranges and reserves, and they price small groups by blending their own experience with similar groups (credibility). The weekly breakdown is the same stepwise attribution I used on a pricing tool at MassMutual.

## Run it
```bash
pip install -r requirements.txt
streamlit run app.py
```

`model.py` has all the math and `app.py` has the page. Python, NumPy, pandas, Plotly and Streamlit.
