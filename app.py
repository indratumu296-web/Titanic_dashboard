import streamlit as st
from db import run_query

st.set_page_config(page_title="Titanic Explorer", layout="wide")
st.title("Titanic Dataset Explorer")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Data Explorer", "SQL Practice", "Test"],
)


if page == "Dashboard":
    st.header("Dashboard")

    totals = run_query("""
        SELECT COUNT(*) AS total,
               SUM(survived) AS survivors,
               ROUND(AVG(age)::numeric, 1) AS avg_age,
               ROUND(AVG(fare)::numeric, 2) AS avg_fare
        FROM passengers
    """).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Passengers", int(totals["total"]))
    c2.metric("Survivors", int(totals["survivors"]))
    c3.metric("Average age", float(totals["avg_age"]))
    c4.metric("Average fare", float(totals["avg_fare"]))

    left, right = st.columns(2)

    with left:
        st.subheader("Passengers by class")
        by_class = run_query("""
            SELECT pclass::text AS class, COUNT(*) AS passengers
            FROM passengers GROUP BY pclass ORDER BY pclass
        """)
        st.bar_chart(by_class.set_index("class"))

    with right:
        st.subheader("Survival rate by sex (%)")
        by_sex = run_query("""
            SELECT sex,
                   ROUND(100.0 * SUM(survived) / COUNT(*), 2)
                       AS survival_percentage
            FROM passengers GROUP BY sex ORDER BY sex
        """)
        st.bar_chart(by_sex.set_index("sex"))

    st.subheader("Missing values")
    missing = run_query("""
        SELECT COUNT(*) - COUNT(age) AS missing_age,
               COUNT(*) - COUNT(embarked) AS missing_embarked,
               COUNT(*) - COUNT(cabin) AS missing_cabin
        FROM passengers
    """)
    st.dataframe(missing, hide_index=True)


elif page == "Data Explorer":
    st.header("Data Explorer")

    col1, col2, col3 = st.columns(3)
    classes = col1.multiselect("Class", [1, 2, 3], default=[1, 2, 3])
    sexes = col2.multiselect(
        "Sex", ["male", "female"], default=["male", "female"]
    )
    outcome = col3.selectbox(
        "Outcome", ["All", "Survived", "Did not survive"]
    )

    if not classes or not sexes:
        st.warning("Select at least one class and one sex.")
    else:
        sql = """
            SELECT passengerid, name, sex, age, pclass,
                   fare, embarked, cabin, survived
            FROM passengers
            WHERE pclass = ANY(%s) AND sex = ANY(%s)
        """
        params = [classes, sexes]

        if outcome == "Survived":
            sql += " AND survived = 1"
        elif outcome == "Did not survive":
            sql += " AND survived = 0"

        sql += " ORDER BY passengerid"

        df = run_query(sql, params)
        st.write(f"{len(df)} passengers found.")
        st.dataframe(df, hide_index=True)
        st.download_button(
            "Download as CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name="titanic_filtered.csv",
            mime="text/csv",
        )


elif page == "SQL Practice":
    st.header("SQL Practice")
    st.caption(
        "Only read-only SELECT queries are allowed. "
        "Tables: passengers, titanic_staging."
    )

    default_sql = (
        "SELECT pclass, COUNT(*) AS passengers\n"
        "FROM passengers\n"
        "GROUP BY pclass\n"
        "ORDER BY pclass;"
    )

    user_sql = st.text_area("Your query", default_sql, height=180)

    if st.button("Run query"):
        cleaned = user_sql.strip().rstrip(";").strip()

        if not cleaned.lower().startswith(("select", "with")):
            st.error("Only SELECT queries are permitted.")
        elif ";" in cleaned:
            st.error("Run one statement at a time.")
        else:
            try:
                result = run_query(cleaned)
                st.success(f"{len(result)} rows returned.")
                st.dataframe(result, hide_index=True)
            except Exception as exc:
                st.error(f"Query failed: {exc}")


elif page == "Test":
    st.header("Knowledge Test")

    QUESTIONS = [
        {
            "q": "Which constraint uniquely identifies each row?",
            "options": ["CHECK", "PRIMARY KEY", "NOT NULL", "DEFAULT"],
            "answer": "PRIMARY KEY",
        },
        {
            "q": "Which psql command imports a CSV from the client?",
            "options": ["\\copy", "\\dt", "\\c", "\\l"],
            "answer": "\\copy",
        },
        {
            "q": "COUNT(age) counts...",
            "options": [
                "All rows",
                "Rows where age is NOT NULL",
                "Rows where age is NULL",
                "Distinct ages only",
            ],
            "answer": "Rows where age is NOT NULL",
        },
        {
            "q": "How do you test for a missing value in SQL?",
            "options": ["= NULL", "== NULL", "IS NULL", "EQUALS NULL"],
            "answer": "IS NULL",
        },
        {
            "q": "Which clause filters groups after aggregation?",
            "options": ["WHERE", "HAVING", "LIMIT", "ORDER BY"],
            "answer": "HAVING",
        },
    ]

    answers = {}

    for i, item in enumerate(QUESTIONS):
        answers[i] = st.radio(
            f"{i + 1}. {item['q']}",
            item["options"],
            index=None,
            key=f"question_{i}",
        )

    if st.button("Submit"):
        if any(a is None for a in answers.values()):
            st.warning("Please answer every question.")
        else:
            score = sum(
                answers[i] == item["answer"]
                for i, item in enumerate(QUESTIONS)
            )

            st.subheader(f"Score: {score} / {len(QUESTIONS)}")

            for i, item in enumerate(QUESTIONS):
                if answers[i] == item["answer"]:
                    st.success(f"Question {i + 1}: correct.")
                else:
                    st.error(
                        f"Question {i + 1}: incorrect. "
                        f"Correct answer: {item['answer']}"
                    )







st.sidebar.markdown("""
<style>
[data-testid="stSidebar"] {
    position: relative;
}

.sidebar-footer {
    position: fixed;
    bottom: 15px;
    left: 10px;
    width: 320px;
    padding: 15px;
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid #454650;
    border-radius: 10px;
    color: white;
    font-size: 16px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 12px;
    z-index: 999;
}

.sidebar-footer span {
    font-size: 23px;
}
</style>

<div class="sidebar-footer">
    <span>👤</span>
    Created by Indra Reddy
</div>
""", unsafe_allow_html=True)