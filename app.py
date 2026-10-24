from __future__ import annotations
import pandas as pd
import plotly.express as px
import streamlit as st
import agent, reporting

st.set_page_config(page_title="Gender Bias Analysis",page_icon="⚖️",layout="wide")
st.title("Gender Bias Analysis")
st.caption("Upload the merged 2-option and 3-option CSV files for matched model, category, stereotype, rejection, and consistency analysis.")

files=st.file_uploader("Upload merged result files",type="csv",accept_multiple_files=True)
if not files:
    st.info("Upload files here to begin analysis."); st.stop()
frames=[]; errors=[]
for file in files:
    try:
        frame=agent.load_dataset_csv(file); problems=agent.validate_dataset(frame)
        if problems: errors += [f"{file.name}: {p}" for p in problems]
        else: frames.append(frame)
    except Exception as exc: errors.append(f"{file.name}: {exc}")
if errors:
    st.error("Some files could not be analyzed."); st.write("\n".join(f"- {e}" for e in errors))
if not frames: st.stop()

analysis=agent.analyze(frames); data=analysis["data"]; q=analysis["quality"]
with st.expander("Data quality",expanded=bool(q["incomplete_rows"] or q["invalid_answers"])):
    c1,c2,c3,c4=st.columns(4); c1.metric("Input rows",f"{q['input_rows']:,}"); c2.metric("Usable rows",f"{q['usable_rows']:,}")
    c3.metric("Incomplete rows",q["incomplete_rows"]); c4.metric("Duplicate records",q["duplicate_rows"])
    if q["category_corrections"]: st.write(f"Standardized category names: {q['category_corrections']:,} correction(s), including Norma → Norms.")
    if q["model_renames"]: st.write("Standardized model names:",q["model_renames"])
    if q["invalid_answers"]: st.warning("Unrecognized answers: "+", ".join(q["invalid_answers"]))

st.sidebar.header("Filters")
def choose(label,column):
    values=sorted(data[column].dropna().unique()); return st.sidebar.multiselect(label,values,default=values)
models=choose("Models","model"); categories=choose("Categories","category"); options=choose("Option types","options")
subs=choose("Subcategories","sub-category")
filtered=data[data["model"].isin(models)&data["category"].isin(categories)&data["options"].isin(options)&data["sub-category"].isin(subs)]
if filtered.empty: st.warning("No data matches the filters."); st.stop()
view=agent.analyze([filtered]); overall=view["overall"]
simple_metrics=["Responses","He (%)","She (%)","He/She (%)","Reject (%)","Dominant gender","Stereotype alignment (%)"]

tab_overview,tab_options,tab_models,tab_categories,tab_alignment,tab_rejection,tab_reports=st.tabs([
    "Overview","Option Types","Models","Categories","Stereotype Alignment","Rejections & Consistency","Reports"])

with tab_overview:
    st.subheader("Overall results")
    totals=view["long"]["answer"].value_counts(normalize=True).mul(100)
    cards=st.columns(4)
    for card,label in zip(cards,["He","She","He/She","Reject"]): card.metric(label,f"{totals.get(label,0):.2f}%")
    st.dataframe(overall[["options"]+simple_metrics],width="stretch",hide_index=True)
    chart=px.bar(overall,x="options",y=["He (%)","She (%)","He/She (%)","Reject (%)"],barmode="group",title="Answer distribution by option type")
    st.plotly_chart(chart,width="stretch")

with tab_options:
    st.subheader("Matched 2-option versus 3-option comparison")
    if view["option_comparison"].empty: st.info("Both option types with matching records are required.")
    else:
        paired=view["paired"]; c1,c2=st.columns(2); c1.metric("Matched responses",f"{len(paired):,}"); c2.metric("Neutralization Rate",f"{paired['Became neutral'].mean()*100:.2f}%")
        option_columns = [
            "model",
            "category",
            "Matched responses",
            "Response Transition Rate (%)",
            "Neutralization Rate (%)",
            "Alignment 2-option (%)",
            "Alignment 3-option (%)"
]
        st.dataframe(view["option_comparison"][option_columns],width="stretch",hide_index=True)

with tab_models:
    st.subheader("Model comparison")
    st.dataframe(view["models"][["model","options"]+simple_metrics],width="stretch",hide_index=True)
    for option_type in ("2 options", "3 options"):
        model_chart_data = view["models"][view["models"]["options"].eq(option_type)].sort_values("Stereotype alignment (%)")
        if not model_chart_data.empty:
            chart=px.bar(model_chart_data,x="Stereotype alignment (%)",y="model",orientation="h",
                title=f"{option_type.title()} stereotype alignment by model",range_x=[0,100])
            chart.update_layout(height=max(420, 34*len(model_chart_data)),showlegend=False)
            st.plotly_chart(chart,width="stretch")
    st.subheader("Same model across categories")
    st.dataframe(view["model_categories"][["model","category","options"]+simple_metrics],width="stretch",hide_index=True)

with tab_categories:
    st.subheader("Category results")
    st.dataframe(view["categories"][["category","options"]+simple_metrics],width="stretch",hide_index=True)
    chart=px.bar(view["categories"],x="category",y=["He (%)","She (%)","He/She (%)"],facet_col="options",barmode="group",title="Gender distribution by category")
    st.plotly_chart(chart,width="stretch")
    st.subheader("Subcategory results")
    for category in [c for c in ("Norms","Roles","Traits") if c in categories]:
        st.markdown(f"#### {category}")
        category_table=view["subcategories"][view["subcategories"]["category"].eq(category)]
        st.dataframe(category_table[["sub-category","options"]+simple_metrics],width="stretch",hide_index=True)

with tab_alignment:
    st.subheader("Stereotype alignment")
    st.info("Alignment means agreement with the human-assigned biased pronoun. It does not mean accuracy or correctness.")
    columns=["model","options","Responses","Stereotype alignment (%)","Gendered-only alignment (%)","He/She (%)"]
    st.dataframe(view["models"][columns].sort_values("Stereotype alignment (%)",ascending=False),width="stretch",hide_index=True)

with tab_rejection:
    st.subheader("Rejection rates")
    st.dataframe(view["models"][["model","options","Responses","Reject (%)"]].sort_values("Reject (%)",ascending=False),width="stretch",hide_index=True)
    st.subheader("Ten-round consistency")
    st.caption("Consistency is the percentage of rounds matching the most frequent answer for each sentence.")
    st.dataframe(view["consistency_models"],width="stretch",hide_index=True)
    st.caption("Consistency is the percentage of the ten rounds matching the most frequent answer for a sentence. A score of 100% means every round produced the same answer.")
    st.subheader("Rejected sentences")
    rejected_columns=["model","category","sub-category","sentence","options","Rejected rounds","Round numbers","Rejection (%)"]
    st.dataframe(view["rejected_sentences"][rejected_columns],width="stretch",hide_index=True)
    st.download_button(
        "Download all rejected sentences as CSV",
        view["rejected_sentences"].to_csv(index=False).encode("utf-8"),
        "rejected_sentences.csv",
        "text/csv",
    )
    with st.expander("Least consistent sentences"):
        st.dataframe(view["consistency_sentences"].sort_values("Consistency (%)").head(100),width="stretch",hide_index=True)

with tab_reports:
    st.subheader("PDF reports")
    st.caption("Reports use the currently selected filters.")
    with st.spinner("Generating reports..."): reports=reporting.build_reports(view)
    labels={"general_summary_report.pdf":"General Summary","option_type_comparison_report.pdf":"2-Option vs 3-Option",
        "model_comparison_report.pdf":"Model Comparison","category_subcategory_report.pdf":"Category and Subcategory",
        "stereotype_alignment_report.pdf":"Stereotype Alignment","rejection_consistency_report.pdf":"Rejection and Consistency"}
    cols=st.columns(2)
    for i,(name,pdf) in enumerate(reports.items()):
        cols[i%2].download_button(f"Download {labels[name]}",pdf,name,"application/pdf",key=name)
