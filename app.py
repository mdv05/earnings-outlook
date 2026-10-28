import plotly.graph_objects as go
import streamlit as st

import model

st.set_page_config(page_title="Earnings Outlook", page_icon="📈", layout="wide")

st.title("Earnings Outlook")
st.caption("A concept for Roblox Creator Hub: plan around uneven income with ranges, not single guesses. "
           "Sample data only. Not affiliated with Roblox.")

with st.sidebar:
    name = st.selectbox("Sample experience", list(model.EXPERIENCES))
    detailed = st.toggle("Detailed view", value=False, help="Simple view for solo creators, detail for studios")
    tax_rate = st.slider("Tax set-aside", 0, 40, 25, step=5, format="%d%%",
                         help="A rough planning number, not tax advice") / 100
    show_usd = st.toggle("Show USD", value=True, help=f"DevEx rate: \\${model.DEVEX_RATE} per Earned Robux")


def money(robux):
    text = f"{robux:,.0f} Robux"
    # "\\$" because Streamlit reads a bare $ as the start of a math formula
    return text + f" (\\${robux * model.DEVEX_RATE:,.0f})" if show_usd else text


@st.cache_data
def run(name):
    history = model.sample_history(name)
    outlook = model.project(history)
    return history, outlook, model.early_alert(history), model.what_changed(history)


history, outlook, (status, actual, past), changes = run(name)
balance = model.EXPERIENCES[name]["balance"]
plan = model.payout_plan(outlook["revenue"], balance, outlook["bands"]["date"].dt.date.tolist())
reserve = model.set_aside(outlook, tax_rate)

# Early alert
if status == "red":
    st.error(f"Heads up: the last 7 days ({actual:,.0f} Robux) came in below the low end of last week's outlook. "
             "A good moment to ship an update.")
elif status == "amber":
    st.warning(f"The last 7 days ({actual:,.0f} Robux) are tracking between the low and likely case.")
else:
    st.success(f"The last 7 days ({actual:,.0f} Robux) are on track with last week's outlook.")

# The numbers a creator needs: simple view shows two, detailed adds the set-aside
cols = st.columns(3 if detailed else 2)
cols[0].metric("Likely earnings, next 90 days", money(outlook["likely"]))
cols[0].caption(f"Range: {outlook['low']:,.0f} to {outlook['high']:,.0f} Robux")
if plan["likely_date"]:
    cols[1].metric("Likely cash-out date", plan["likely_date"].strftime("%b %d"))
else:
    cols[1].metric("Likely cash-out date", "Beyond 90 days")
cols[1].caption(f"{plan['chance_90']:.0%} chance of reaching {model.DEVEX_MIN:,} Earned Robux within 90 days "
                f"(you have {balance:,})")
if detailed:
    cols[2].metric("Suggested set-aside", money(reserve["total"]))
    cols[2].caption(f"{money(reserve['taxes'])} for taxes + {money(reserve['cushion'])} cushion for a slow stretch")

# Credibility runs behind the scenes; creators just see how much to trust the numbers
z = outlook["cred"]["z"]
confidence = "Low" if z < 0.5 else "Medium" if z < 0.8 else "High"
st.info(f"**{confidence} confidence:** based on {len(history)} days of your data"
        + (", plus similar games." if z < 0.8 else "."))

# History plus the range going forward
st.subheader("Daily earnings: last 60 days and next 90")
bands = outlook["bands"]
recent = history.tail(60)
fig = go.Figure()
fig.add_trace(go.Scatter(x=bands["date"], y=bands["high"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
fig.add_trace(go.Scatter(x=bands["date"], y=bands["low"], fill="tonexty", line=dict(width=0),
                         fillcolor="rgba(0,162,255,0.18)", name="Low to high range"))
fig.add_trace(go.Scatter(x=bands["date"], y=bands["likely"], line=dict(color="#00a2ff", dash="dash"), name="Likely"))
fig.add_trace(go.Scatter(x=recent["date"], y=recent["revenue"], line=dict(color="#9aa0a6", width=2), name="Actual"))
fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Earned Robux per day",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
st.plotly_chart(fig, width="stretch")

if detailed:
    st.subheader("How much of this outlook is your own data?")
    st.progress(z, text=f"{z:.0%} your experience · {1 - z:.0%} similar experiences")
    st.caption(f"With {len(history)} days of history, your own trend gets {z:.0%} of the weight. "
               "New experiences lean on similar ones until they build a track record.")

    st.subheader("What changed this week")
    st.caption("Last 7 days vs the 7 before, split into more players vs more spending per player.")
    fig2 = go.Figure()
    fig2.add_bar(x=changes["stream"], y=changes["players effect"], name="Players effect", marker_color="#00a2ff")
    fig2.add_bar(x=changes["stream"], y=changes["spending effect"], name="Spending effect", marker_color="#ff9f1c")
    fig2.update_layout(barmode="relative", height=320, margin=dict(l=10, r=10, t=10, b=10),
                       yaxis_title="Change in Earned Robux", legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    st.plotly_chart(fig2, width="stretch")
    total = changes["total"].sum()
    st.caption(f"Total change: {total:+,.0f} Robux "
               f"({changes['players effect'].sum():+,.0f} from players, "
               f"{changes['spending effect'].sum():+,.0f} from spending).")

    with st.expander("How this works"):
        st.markdown(f"""
- **Range, not a guess.** 1,000 simulated futures for daily players, each turned into revenue at your
  recent revenue per player. The band is the 10th to 90th percentile.
- **Credibility weighting.** Your trend gets weight Z = n / (n + {model.K}), where n is days of history.
  The rest comes from similar experiences, the same way actuaries price a small group.
- **Cash-out planner.** The share of simulated futures where your balance reaches
  {model.DEVEX_MIN:,} Earned Robux, the DevEx minimum.
- **Set-aside.** Taxes on the likely case plus a cushion equal to the gap between the likely and low case.
- **What changed.** A stepwise split: first change the number of players, then change spending per player.
  The two effects add up to the total change.
- **Early alert.** Compares the last 7 days to the outlook this tool would have shown a week ago.
""")
