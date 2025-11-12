from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Survey Demographic Dashboard", layout="wide")

SURVEY_FILE = Path(__file__).parent / "Survey.xlsx"

RENAME_MAP: Dict[str, str] = {
    "Start time": "Start Time",
    "Completion time": "Completion Time",
    "Email Address": "Secondary Email",
    "What is your Educational Background\n": "Educational Background",
    "What is your current church affiliation\xa0": "Church Affiliation",
    "How frequently do you attend church?\n": "Attendance Frequency",
    "How do you attend church": "Attendance Mode",
    "How much time do you spend per day on media (Social Media, Streaming Platforms, etc)": "Daily Media Time",
    "Which platforms do you use?": "Media Platforms",
    "My engagement with media has made my faith:": "Media Impact on Faith",
    "How regular are you with personal devotion (Bible Reading/Prayer)": "Personal Devotion Regularity",
    "In what way do you contribute to your church (select all that apply)": "Church Contribution",
}

SENSITIVE_COLUMNS: Iterable[str] = (
    "Email",
    "Name",
    "First Name",
    "Last Name",
    "Secondary Email",
    "Phone Number",
)

FILTER_COLUMNS: Iterable[str] = (
    "Age Range",
    "Sex",
    "Ethnicity",
    "Educational Background",
    "Marital Status",
    "Church Affiliation",
)

MULTI_VALUE_FIELDS: Iterable[str] = (
    "Media Platforms",
    "Church Contribution",
)


def clean_string_series(series: pd.Series) -> pd.Series:
    """Normalize white space and remove empty responses."""
    if series.dtype != object:
        return series
    cleaned = (
        series.astype(str)
        .str.replace("\n", " ", regex=False)
        .str.replace("\xa0", " ", regex=False)
        .str.strip()
    )
    cleaned = cleaned.replace({"nan": pd.NA, "": pd.NA})
    return cleaned


@st.cache_data(show_spinner=False)
def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        st.error(f"Could not find the survey file at {path}")
        st.stop()

    df = pd.read_excel(path)
    df = df.rename(columns=RENAME_MAP)
    df.columns = [col.strip() for col in df.columns]

    for column in df.columns:
        df[column] = clean_string_series(df[column])

    drop_cols = [col for col in SENSITIVE_COLUMNS if col in df.columns]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    return df


def apply_filters(
    data: pd.DataFrame,
    selections: Dict[str, List[str]],
    options_map: Dict[str, List[str]],
) -> pd.DataFrame:
    filtered = data.copy()
    for column, selected in selections.items():
        if not selected:
            continue
        available = options_map.get(column, [])
        if set(selected) == set(available):
            continue
        filtered = filtered[filtered[column].isin(selected)]
    return filtered


def single_select_chart(data: pd.Series, title: str) -> None:
    counts = (
        data.dropna()
        .replace("", pd.NA)
        .dropna()
        .value_counts()
        .reset_index()
    )
    if counts.empty:
        st.info(f"No data available for {title.lower()}.")
        return

    counts.columns = ["Category", "Responses"]
    chart = (
        alt.Chart(counts)
        .mark_bar(radius=4)
        .encode(
            y=alt.Y("Category:N", sort="-x", title=""),
            x=alt.X("Responses:Q", title="Respondents"),
            tooltip=["Category", "Responses"],
        )
        .properties(title=title)
    )
    st.altair_chart(chart, use_container_width=True)


def single_select_pie_chart(data: pd.Series, title: str) -> None:
    counts = (
        data.dropna()
        .replace("", pd.NA)
        .dropna()
        .value_counts()
        .reset_index()
    )
    if counts.empty:
        st.info(f"No data available for {title.lower()}.")
        return

    counts.columns = ["Category", "Responses"]
    counts["Percent"] = counts["Responses"] / counts["Responses"].sum()

    chart = (
        alt.Chart(counts)
        .mark_arc(innerRadius=40)
        .encode(
            theta=alt.Theta("Responses:Q", stack=True),
            color=alt.Color("Category:N", legend=alt.Legend(title="")),
            tooltip=[
                alt.Tooltip("Category:N", title="Category"),
                alt.Tooltip("Responses:Q", title="Respondents"),
                alt.Tooltip("Percent:Q", title="Percent", format=".1%"),
            ],
        )
        .properties(title=title)
    )

    st.altair_chart(chart, use_container_width=True)


def multivalue_chart(data: pd.Series, title: str) -> None:
    exploded = (
        data.dropna()
        .str.split(";")
        .explode()
        .str.strip()
        .replace("", pd.NA)
        .dropna()
    )
    if exploded.empty:
        st.info(f"No multi-select responses available for {title.lower()}.")
        return

    counts = exploded.value_counts().reset_index()
    counts.columns = ["Category", "Responses"]
    chart = (
        alt.Chart(counts)
        .mark_bar(radius=4)
        .encode(
            y=alt.Y("Category:N", sort="-x", title=""),
            x=alt.X("Responses:Q", title="Respondents"),
            tooltip=["Category", "Responses"],
        )
        .properties(title=title)
    )
    st.altair_chart(chart, use_container_width=True)


def summarize_category(series: pd.Series) -> str:
    counts = (
        series.dropna()
        .replace("", pd.NA)
        .dropna()
        .value_counts()
    )
    if counts.empty:
        return "N/A"
    top_label = counts.index[0]
    top_count = counts.iloc[0]
    return f"{top_label} ({top_count})"


def summarize_multivalue(series: pd.Series) -> str:
    exploded = (
        series.dropna()
        .str.split(";")
        .explode()
        .str.strip()
        .replace("", pd.NA)
        .dropna()
    )
    if exploded.empty:
        return "N/A"
    counts = exploded.value_counts()
    top_label = counts.index[0]
    top_count = counts.iloc[0]
    return f"{top_label} ({top_count})"


def main() -> None:
    st.title("Survey Demographic Dashboard")
    st.caption("Interactive overview of respondent demographics and engagement patterns.")

    data = load_data(SURVEY_FILE)

    with st.sidebar:
        st.header("Filter Responses")
        selections: Dict[str, List[str]] = {}
        options_map: Dict[str, List[str]] = {}
        for column in FILTER_COLUMNS:
            if column not in data.columns:
                continue
            options = sorted(data[column].dropna().unique())
            options_map[column] = options
            selections[column] = st.multiselect(
                column,
                options=options,
                default=options,
            )

        st.markdown("---")
        st.write("Download filtered responses")
        filtered_snapshot = apply_filters(data, selections, options_map)
        st.download_button(
            "Download CSV",
            data=filtered_snapshot.to_csv(index=False).encode("utf-8"),
            file_name="filtered_survey_responses.csv",
            mime="text/csv",
            use_container_width=True,
        )

    filtered = apply_filters(data, selections, options_map)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Responses", f"{len(filtered):,}")
    col_b.metric("Top Age Range", summarize_category(filtered.get("Age Range", pd.Series(dtype=object))))
    col_c.metric(
        "Most Common Media Platform",
        summarize_multivalue(filtered.get("Media Platforms", pd.Series(dtype=object))),
    )

    col_d, col_e, col_f = st.columns(3)
    col_d.metric(
        "Attendance Frequency",
        summarize_category(filtered.get("Attendance Frequency", pd.Series(dtype=object))),
    )
    col_e.metric(
        "Attendance Mode",
        summarize_category(filtered.get("Attendance Mode", pd.Series(dtype=object))),
    )
    col_f.metric(
        "Personal Devotion",
        summarize_category(filtered.get("Personal Devotion Regularity", pd.Series(dtype=object))),
    )

    st.subheader("Demographic Overview")
    demo_cols = st.columns(3)
    if "Age Range" in filtered.columns:
        with demo_cols[0]:
            single_select_chart(filtered["Age Range"], "Respondents by Age Range")
    if "Sex" in filtered.columns:
        with demo_cols[1]:
            single_select_pie_chart(filtered["Sex"], "Respondents by Sex")
    if "Ethnicity" in filtered.columns:
        with demo_cols[2]:
            single_select_chart(filtered["Ethnicity"], "Respondents by Ethnicity")

    edu_cols = st.columns(2)
    if "Educational Background" in filtered.columns:
        with edu_cols[0]:
            single_select_chart(filtered["Educational Background"], "Educational Background")
    if "Career/Occupation/Industry" in filtered.columns:
        with edu_cols[1]:
            single_select_chart(filtered["Career/Occupation/Industry"], "Career / Industry")

    engage_cols = st.columns(2)
    if "Attendance Frequency" in filtered.columns:
        with engage_cols[0]:
            single_select_pie_chart(
                filtered["Attendance Frequency"],
                "Church Attendance Frequency",
            )
    if "Attendance Mode" in filtered.columns:
        with engage_cols[1]:
            single_select_pie_chart(filtered["Attendance Mode"], "Attendance Mode")

    media_cols = st.columns(2)
    if "Daily Media Time" in filtered.columns:
        with media_cols[0]:
            single_select_chart(filtered["Daily Media Time"], "Daily Media Consumption")
    if "Media Impact on Faith" in filtered.columns:
        with media_cols[1]:
            single_select_chart(filtered["Media Impact on Faith"], "Perceived Media Impact on Faith")

    st.subheader("Multi-Select Engagement Insights")
    multi_cols = st.columns(2)
    if "Media Platforms" in filtered.columns:
        with multi_cols[0]:
            multivalue_chart(filtered["Media Platforms"], "Media Platforms Used")
    if "Church Contribution" in filtered.columns:
        with multi_cols[1]:
            multivalue_chart(filtered["Church Contribution"], "Church Contribution Methods")

    with st.expander("View Filtered Responses"):
        st.dataframe(filtered, use_container_width=True)


if __name__ == "__main__":
    main()
