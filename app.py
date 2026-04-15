import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Splitwise Dashboard", layout="wide")

st.title("💰 Splitwise Dashboard")

# 🔑 Credentials

CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = "https://splitwise-dashboard-9yvtvmc5gfynj927jr4adt.streamlit.app"

# 🔗 Auth
auth_url = f"https://secure.splitwise.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
st.link_button("🔗 Connect Splitwise", auth_url)

params = st.query_params

if "token" not in st.session_state:
    st.session_state["token"] = None

# 🔐 Get Token
if "code" in params and st.session_state["token"] is None:
    code = params["code"]

    token_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }

    res = requests.post("https://secure.splitwise.com/oauth/token", data=token_data)
    token = res.json().get("access_token")

    if token:
        st.session_state["token"] = token
        st.success("Connected!")

token = st.session_state["token"]

# ==============================
# 🚀 MAIN APP
# ==============================

if token:

    with st.form("form"):
        GROUP_ID = st.text_input("Enter Group ID")
        submit = st.form_submit_button("Fetch Data")

    if submit:

        headers = {"Authorization": f"Bearer {token}"}

        # ==============================
        # 📊 FETCH EXPENSES
        # ==============================

        all_expenses = []
        offset = 0
        limit = 100

        while True:
            url = f"https://secure.splitwise.com/api/v3.0/get_expenses?group_id={GROUP_ID}&limit={limit}&offset={offset}"
            r = requests.get(url, headers=headers)
            data = r.json()

            expenses = data.get("expenses", [])
            if not expenses:
                break

            all_expenses.extend(expenses)
            offset += limit

        # ==============================
        # 📊 CHARTS
        # ==============================

        user_summary = {}

        for exp in all_expenses:
            if exp.get("deleted_at") is not None:
                continue
            if exp.get("payment"):
                continue

            for u in exp["users"]:
                name = f"{u['user']['first_name']} {u['user'].get('last_name') or ''}".strip()

                paid = float(u.get("paid_share", 0))
                used = float(u.get("owed_share", 0))

                if name not in user_summary:
                    user_summary[name] = {"Paid": 0, "Used": 0}

                user_summary[name]["Paid"] += paid
                user_summary[name]["Used"] += used

        summary_df = pd.DataFrame([
            {"User": k, "Paid": round(v["Paid"], 2), "Used": round(v["Used"], 2)}
            for k, v in user_summary.items()
        ])

        st.metric("💰 Total Group Spend", round(summary_df["Paid"].sum(), 2))

        col1, col2 = st.columns(2)

        with col1:
            fig1 = px.bar(summary_df, x="User", y="Paid", text="Paid", title="Total Paid")
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            fig2 = px.bar(summary_df, x="User", y="Used", text="Used", title="Total Used")
            st.plotly_chart(fig2, use_container_width=True)

        # ==============================
        # 📋 CURRENT MONTH SPLIT TABLE
        # ==============================

        current_month = datetime.now().month
        current_year = datetime.now().year

        rows = []
        total_positive = 0
        total_negative = 0

        for exp in all_expenses:

            if exp.get("deleted_at") is not None:
                continue

            if exp.get("payment", False):
                continue

            if float(exp.get("cost", 0)) <= 0:
                continue

            exp_date = datetime.strptime(exp.get("date")[:10], "%Y-%m-%d")

            if exp_date.month != current_month or exp_date.year != current_year:
                continue

            paid_by = ""
            owes_list = []
            payer_net = 0

            for user in exp["users"]:
                name = f"{user['user']['first_name']} {user['user'].get('last_name') or ''}".strip()

                paid = float(user.get("paid_share", 0))
                owed = float(user.get("owed_share", 0))
                net = round(paid - owed, 2)

                if paid > 0:
                    paid_by = name
                    payer_net = net
                    total_positive += net

                if net < 0:
                    owes_list.append(f"{name} ({net})")
                    total_negative += net

            rows.append({
                "Description": exp.get("description"),
                "Paid By": paid_by,
                "Owes (-)": ", ".join(owes_list),
                "Paid (+)": f"{paid_by} (+{payer_net})",
                "Total Amount": round(float(exp.get("cost", 0)), 2),
                "Date": exp.get("date", "")[:10]
            })

        df = pd.DataFrame(rows)

        st.subheader("💸 Current Month Expense Split")
        st.dataframe(df, use_container_width=True)

      

        # ==============================
        # 💸 CURRENT BALANCES
        # ==============================

        url = f"https://secure.splitwise.com/api/v3.0/get_group/{GROUP_ID}"
        r = requests.get(url, headers=headers)
        group_data = r.json()

        members = group_data["group"]["members"]

        balance_rows = []

        for m in members:
            name = f"{m['first_name']} {m.get('last_name') or ''}".strip()

            for bal in m["balance"]:
                amount = round(float(bal["amount"]), 2)

                if abs(amount) > 0.01:
                    balance_rows.append({
                        "User": name,
                        "Balance": amount
                    })

        balance_df = pd.DataFrame(balance_rows)

        st.subheader("💸 Current Unsettled")
        st.dataframe(balance_df, use_container_width=True)

else:
    st.info("Connect Splitwise first")
