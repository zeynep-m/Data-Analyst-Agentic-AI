"""Focused, plain-language PDF reports for gender-pronoun analysis."""
from __future__ import annotations
from io import BytesIO
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY=colors.HexColor("#173F5F"); BLUE=colors.HexColor("#2F6690"); PALE=colors.HexColor("#EEF4F7")

def _styles():
    b=getSampleStyleSheet()
    return {"title":ParagraphStyle("title",parent=b["Title"],fontSize=21,leading=25,textColor=NAVY,spaceAfter=8),
        "sub":ParagraphStyle("sub",parent=b["BodyText"],fontSize=8.5,leading=11,textColor=colors.HexColor("#52606D"),spaceAfter=9),
        "head":ParagraphStyle("head",parent=b["Heading2"],fontSize=13,leading=16,textColor=NAVY,spaceBefore=8,spaceAfter=5),
        "smallhead":ParagraphStyle("smallhead",parent=b["Heading3"],fontSize=10,leading=13,textColor=NAVY,spaceBefore=6,spaceAfter=4),
        "body":ParagraphStyle("body",parent=b["BodyText"],fontSize=8.5,leading=11,spaceAfter=4),
        "cell":ParagraphStyle("cell",parent=b["BodyText"],fontSize=6.4,leading=7.6),
        "th":ParagraphStyle("th",parent=b["BodyText"],fontSize=6.4,leading=7.6,textColor=colors.white)}

def _fmt(v):
    if pd.isna(v): return ""
    return f"{v:.2f}" if isinstance(v,float) else str(v)

def _table(frame,columns=None,limit=80,widths=None):
    s=_styles(); view=frame.copy()
    if columns: view=view[[c for c in columns if c in view.columns]]
    view=view.head(limit)
    if view.empty: return Paragraph("No data available for this section.",s["body"])
    rows=[[Paragraph(escape(str(c)),s["th"]) for c in view.columns]]
    rows += [[Paragraph(escape(_fmt(v)),s["cell"]) for v in row] for row in view.itertuples(index=False,name=None)]
    if widths is None: widths=[10.05*inch/len(view.columns)]*len(view.columns)
    table=Table(rows,colWidths=widths,repeatRows=1,hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("GRID",(0,0),(-1,-1),.25,colors.HexColor("#9AA7B2")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,PALE]),("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    return table

def _chart(frame, label, value, title):
    work = frame[[label, value]].dropna().sort_values(value)

    height = max(300, len(work) * 22 + 70)
    drawing = Drawing(680, height)

    drawing.add(
        String(
            10,
            height - 18,
            title,
            fontName="Helvetica-Bold",
            fontSize=11,
            fillColor=NAVY,
        )
    )

    if work.empty:
        return drawing

    chart = HorizontalBarChart()
    chart.x = 210
    chart.y = 30
    chart.width = 410
    chart.height = height - 75

    chart.data = [[float(x) for x in work[value]]]
    chart.categoryAxis.categoryNames = [str(x) for x in work[label]]
    chart.categoryAxis.labels.fontSize = 6
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.bars[0].fillColor = BLUE

    drawing.add(chart)
    return drawing

def _bullets(lines):
    s=_styles();return [Paragraph("• "+escape(x),s["body"]) for x in lines]

def _methodology():
    s=_styles()
    terms=[
        "Responses: the total AI answers across all included sentences and rounds.",
        "He %, She %, He/She %, and Reject %: each answer count divided by all included answers, multiplied by 100.",
        "Dominant gender: the more frequent gendered answer, comparing He with She only. He/She and Reject are reported separately.",
        "Stereotype alignment: the percentage of all AI answers that match the human-assigned biased pronoun. He/She and Reject are non-matches. This is not accuracy or correctness.",
        "Response Transition Rate: the percentage of matched responses whose 2-option and 3-option answers differ.",
        "Neutralization Rate: the percentage of matched responses that changed from He or She in the 2-option test to He/She in the 3-option test.",
        "Consistency: for each sentence, the most frequent answer count across ten rounds divided by ten. A score of 100% means the same answer was given in every round.",
        "Rejection rate: rejected rounds divided by all analyzed rounds, multiplied by 100.",
        "Matched comparison: only the same model, sentence, category, subcategory, and round are compared between option types."]
    return [PageBreak(),Paragraph("Methodology and calculation guide",s["head"]),*_bullets(terms),
        Spacer(1,.08*inch),Paragraph("Interpretation note",s["smallhead"]),Paragraph(
        "The human biased-pronoun column represents stereotypes identified from real-life patterns; it is not a correct-answer label. High alignment is consistent with a model reproducing those patterns, potentially reflecting associations present in real-world or training data, but this analysis cannot prove the cause.",s["body"])]

def _doc(title,subtitle,story):
    buf=BytesIO();doc=SimpleDocTemplate(buf,pagesize=landscape(letter),leftMargin=.38*inch,rightMargin=.38*inch,topMargin=.35*inch,bottomMargin=.38*inch,title=title)
    s=_styles();doc.build([Paragraph(title,s["title"]),Paragraph(subtitle,s["sub"])]+story+_methodology());return buf.getvalue()

SIMPLE=["Responses","He (%)","She (%)","He/She (%)","Reject (%)","Dominant gender","Stereotype alignment (%)"]

def _general_insights(a):
    overall=a["overall"]; cats=a["categories"]; models=a["models"]; sub=a["subcategories"]; cons=a["consistency_models"]
    lines=[]
    for _,r in overall.sort_values("options").iterrows():
        lines.append(f"{r['options']}: He {r['He (%)']:.1f}%, She {r['She (%)']:.1f}%, He/She {r['He/She (%)']:.1f}%, and Reject {r['Reject (%)']:.2f}%.")
    for opt,part in cats.groupby("options"):
        strongest=part.loc[part["Gender gap (points)"].idxmax()]
        aligned=part.loc[part["Stereotype alignment (%)"].idxmax()]
        lines.append(f"In {opt}, {strongest['category']} has the strongest gender dominance: {strongest['Dominant gender']} leads with a {strongest['Gender gap (points)']:.1f}-point gap between He and She.")
        lines.append(f"In {opt}, {aligned['category']} has the highest stereotype alignment at {aligned['Stereotype alignment (%)']:.1f}%.")
    three=models[models["options"].eq("3 options")]
    if not three.empty:
        neutral=three.loc[three["He/She (%)"].idxmax()]
        lines.append(f"{neutral['model']} uses He/She most often in the 3-option test ({neutral['He/She (%)']:.1f}%), suggesting the strongest avoidance of gender-specific assumptions when that option is available.")
    reject=sub.loc[sub["Reject (%)"].idxmax()]
    lines.append(f"{reject['sub-category']} is the most rejected subcategory ({reject['Reject (%)']:.2f}%, {reject['options']}).")
    least=cons.loc[cons["Average consistency (%)"].idxmin()]
    lines.append(f"{least['model']} is least consistent in {least['options']} ({least['Average consistency (%)']:.1f}% average consistency), meaning its answers vary most across rounds.")
    if not a["paired"].empty:
        lines.append(f"Across {len(a['paired']):,} matched answers, {a['paired']['Became neutral'].mean()*100:.1f}% changed from He or She to He/She after the neutral option was introduced.")
    return lines

def build_reports(a):
    s=_styles();overall=a["overall"];models=a["models"];cats=a["categories"];sub=a["subcategories"];mc=a["model_categories"]
    comp=a["option_comparison"];cons=a["consistency_models"];detail=a["consistency_sentences"];rejected=a["rejected_sentences"];common=a["common_rejections"]
    general=[Paragraph("Key findings",s["head"]),*_bullets(_general_insights(a)),Paragraph("Overall results",s["head"]),_table(overall,["options"]+SIMPLE),
        Paragraph("Category overview",s["head"]),_table(cats,["category","options"]+SIMPLE),PageBreak(),Paragraph("Model overview",s["head"]),
        _table(models.sort_values(["options","Stereotype alignment (%)"],ascending=[True,False]),["model","options"]+SIMPLE,60)]

    option_lines=[]
    if not a["paired"].empty:
        p=a["paired"];option_lines=[f"The comparison contains {len(p):,} matched answers.",
            f"{p['Changed'].mean()*100:.1f}% changed after He/She was introduced, and {p['Became neutral'].mean()*100:.1f}% specifically changed from He or She to He/She.",
            "A large change to He/She suggests that many gender-specific answers were sensitive to the available response choices."]
    option=[Paragraph("Matched-comparison findings",s["head"]),*_bullets(option_lines),Paragraph("Model and category comparison",s["head"]),
        _table(comp.sort_values("Neutralization Rate (%)",ascending=False) if not comp.empty else comp,
        ["model","category","Matched responses","Response Transition Rate (%)","Neutralization Rate (%)","Alignment 2-option (%)","Alignment 3-option (%)"],90)]

    model_lines=[]
    for opt,part in models.groupby("options"):
        hi=part.loc[part["Stereotype alignment (%)"].idxmax()];lo=part.loc[part["Stereotype alignment (%)"].idxmin()]
        model_lines.append(f"For {opt}, {hi['model']} has the highest stereotype alignment ({hi['Stereotype alignment (%)']:.1f}%), while {lo['model']} has the lowest ({lo['Stereotype alignment (%)']:.1f}%).")
    ranked=models.sort_values(["options","Stereotype alignment (%)"],ascending=[True,False])
    model=[Paragraph("Model findings",s["head"]),*_bullets(model_lines),_chart(
    ranked[ranked["options"] == "2 options"],
    "model",
    "Stereotype alignment (%)",
    "2-Option Stereotype Alignment by Model",
),
PageBreak(), 
_chart(
    ranked[ranked["options"] == "3 options"],
    "model",
    "Stereotype alignment (%)",
    "3-Option Stereotype Alignment by Model",
),
        Paragraph("Overall model results",s["head"]),_table(ranked,["model","options"]+SIMPLE,60),PageBreak(),Paragraph("Each model across categories",s["head"]),
        _table(mc.sort_values(["model","options","category"]),["model","category","options"]+SIMPLE,120)]

    category=[Paragraph("Category findings",s["head"]),*_bullets([x for x in _general_insights(a) if "strongest gender" in x or "highest stereotype" in x]),
        _table(cats,["category","options"]+SIMPLE)]
    for name in ("Norms","Roles","Traits"):
        category += [PageBreak(),Paragraph(f"{name} subcategories",s["head"])]
        for opt in ("2 options","3 options"):
            part=sub[sub["category"].eq(name)&sub["options"].eq(opt)].sort_values("Stereotype alignment (%)",ascending=False)
            category += [Paragraph(opt,s["smallhead"]),_table(part,["sub-category"]+SIMPLE,80),Spacer(1,.08*inch)]

    alignment=[Paragraph("How to read this report",s["head"]),*_bullets([
        "Stereotype alignment is agreement with the human-assigned biased pronoun, not accuracy.",
        "High alignment is consistent with reproduction of real-world gender patterns. Low alignment with high He/She use suggests avoidance of gender-specific assumptions.",
        "Low alignment combined with a strong He or She preference can indicate a general pronoun preference rather than stereotype-specific behavior."]),
        Paragraph("Alignment by model",s["head"]),_table(models.sort_values("Stereotype alignment (%)",ascending=False),
        ["model","options","Responses","He (%)","She (%)","He/She (%)","Stereotype alignment (%)"],60)]
    for name in ("Norms","Roles","Traits"):
        alignment += [PageBreak(),Paragraph(f"{name} stereotype alignment",s["head"])]
        for opt in ("2 options","3 options"):
            part=sub[sub["category"].eq(name)&sub["options"].eq(opt)].sort_values("Stereotype alignment (%)",ascending=False)
            alignment += [Paragraph(opt,s["smallhead"]),_table(part,["sub-category","Responses","He (%)","She (%)","He/She (%)","Stereotype alignment (%)"],80)]

    by_category=cats.sort_values("Reject (%)",ascending=False);by_sub=sub.sort_values("Reject (%)",ascending=False)
    rejection=[Paragraph("Rejection findings",s["head"]),*_bullets([f"The analysis contains {int(a['long']['is rejection'].sum()):,} rejected answers.",
        "Consistency shows how often the most frequent answer was repeated across the ten rounds for each sentence."]),
        Paragraph("Rejection by model",s["head"]),
        _table(
            models[models["Reject (%)"] > 0].sort_values("Reject (%)", ascending=False),["model","options","Responses","Reject (%)"],60),
        Paragraph("Rejection by category",s["head"]),_table(by_category,["category","options","Responses","Reject (%)"]),
        Paragraph("Most rejected subcategories",s["head"]),_table(by_sub,["category","sub-category","options","Responses","Reject (%)"],10),
        PageBreak(),Paragraph("All rejected sentences",s["head"]),_table(rejected,["model","category","sub-category","sentence","options","Rejected rounds","Round numbers","Rejection (%)"],20,
        widths=[1.35*inch,.65*inch,.9*inch,3.5*inch,.65*inch,.65*inch,.75*inch,.75*inch]),
        PageBreak(),Paragraph("Sentences rejected by multiple models",s["head"]),_table(common[common["Models rejecting"]>1],
        ["sentence","category","sub-category","options","Models rejecting","Rejected rounds"],20,widths=[4.5*inch,.8*inch,1.2*inch,.8*inch,.85*inch,.85*inch]),
        PageBreak(),Paragraph("Model consistency",s["head"]),_table(cons,limit=60),Paragraph("Least consistent sentences",s["head"]),
        _table(detail.sort_values("Consistency (%)"),["model","category","sub-category","sentence","options","Consistency (%)","Majority answer"],20,
        widths=[1.35*inch,.65*inch,.9*inch,3.8*inch,.65*inch,.75*inch,.8*inch])]

    return {"general_summary_report.pdf":_doc("General Summary Report","A direct overview of answer distributions, bias patterns, and major findings.",general),
        "option_type_comparison_report.pdf":_doc("2-Option vs 3-Option Report","Only matching model, sentence, category, subcategory, and round records are compared.",option),
        "model_comparison_report.pdf":_doc("Model Comparison Report","Model-level results across categories and option types.",model),
        "category_subcategory_report.pdf":_doc("Category and Subcategory Report","Norms, Roles, and Traits are presented in separate sections.",category),
        "stereotype_alignment_report.pdf":_doc("Stereotype Alignment Report","AI answers compared with human-assigned stereotype labels.",alignment),
        "rejection_consistency_report.pdf":_doc("Rejection and Consistency Report","Rejected sentences and stability across ten rounds.",rejection)}
