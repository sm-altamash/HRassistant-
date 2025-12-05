import pymupdf
import streamlit as st
from scripts.AI_Utilities import AI_Utilities


# === HARD-CODED GEMINI API KEY (replace with your actual key) ===
GEMINI_API_KEY = "fydfga2647264574ysdtfadftadafdtyafdyd"  # <-- replace this string with your Gemini API key

# Initialize session state
if "cv_content" not in st.session_state:
    st.session_state["cv_content"] = ""
if "evaluation" not in st.session_state:
    st.session_state["evaluation"] = None
if "evaluation_report" not in st.session_state:
    st.session_state["evaluation_report"] = None
if "suggestions" not in st.session_state:
    st.session_state["suggestions"] = None
if "generate_clicked" not in st.session_state:
    st.session_state["generate_clicked"] = False
if "ai_utilities" not in st.session_state:
    st.session_state["ai_utilities"] = AI_Utilities()  # Store AI Utilities instance

SUCCESS_SCORE = 85
FAILURE_SCORE = 45

st.set_page_config(
    page_title="AI Resume & JD Analyzer",
    page_icon="👩🏻‍💻",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Report a bug": "https://github.com/vivekpathania/ai-experiments/issues"
    },
)

st.title("AI Resume & JD Analyzer")
st.caption("Optimize your hiring process or enhance your CV with AI.")

container = st.container(border=False)

with st.sidebar:
    mode = st.radio("Select Mode", ["Hiring", "Candidate"])
    # removed Groq API key input (we're using a hard-coded Gemini key)
    st.info("Using hard-coded Gemini API key for LLM access.")

    uploaded_jd_file = st.file_uploader("Upload Job Description (PDF)", key="jd")
    uploaded_cv_file = st.file_uploader("Upload Candidate CV (PDF)", key="cv")
    submitted = st.button("Evaluate Fit" if mode == "Hiring" else "Analyze CV")

# Main App Logic
if submitted:
    # We no longer require a Groq API key from the user since GEMINI_API_KEY is hard-coded
    if not uploaded_jd_file or not uploaded_cv_file:
        st.error("Both Job Description and CV are required.")
    else:
        # initialize LLM with the hard-coded Gemini key
        st.session_state["ai_utilities"].initialize_llm(GEMINI_API_KEY)
        st.session_state["suggestions"] = None
        container.empty()
        try:
            # Extract PDF content and store in session state
            with pymupdf.open(stream=uploaded_jd_file.read(), filetype="pdf") as pdf:
                jd_content = "\n\n".join(page.get_text("text") for page in pdf)

            with pymupdf.open(stream=uploaded_cv_file.read(), filetype="pdf") as pdf:
                cv_content = "\n\n".join(page.get_text("text") for page in pdf)
                st.session_state["cv_content"] = cv_content

            if mode == "Hiring":
                evaluation = st.session_state["ai_utilities"].evaluate(
                    jd_content, cv_content, False
                )
                container.write(evaluation)
            else:
                with st.spinner("Processing evaluation..."):
                    evaluation_json = st.session_state["ai_utilities"].evaluate(
                        jd_content, cv_content, True
                    )
                st.session_state["evaluation"] = evaluation_json
                score = evaluation_json.get("overall_score", 0)
                gaps = evaluation_json.get("gaps", [])
                if gaps:
                    eval_report = st.session_state[
                        "ai_utilities"
                    ].json_to_markdown_report(evaluation_json)
                    with st.spinner("Generating suggestions..."):
                        suggestions = st.session_state[
                            "ai_utilities"
                        ].generate_suggestions(",".join(gaps))
                    st.session_state["suggestions"] = suggestions
                    st.session_state["evaluation_report"] = eval_report
                else:
                    st.session_state["suggestions"] = (
                        "No gaps found. Your CV is aligned!"
                    )

        except Exception as e:
            st.error(f"Error processing files: {e}")

# Candidate Mode Workflow
if mode == "Candidate" and st.session_state.get("evaluation"):
    score = st.session_state["evaluation"].get("overall_score", 0)

    if score >= SUCCESS_SCORE:
        container.success(
            "Congratulations! Your CV is well-aligned with the Job Description. No further improvements are needed."
        )
        container.write(st.session_state["evaluation_report"])
    elif FAILURE_SCORE <= score < SUCCESS_SCORE:
        container.warning(
            "Your CV has moderate alignment. Consider these improvements:"
        )
        container.markdown("### Report")
        container.write(st.session_state["evaluation_report"])
        container.markdown("### Improvement Suggestions")
        st.session_state["suggestions"] = container.text_area(
            "Review the suggested improvements to enhance your CV. You can also add your own points or suggestions to further refine your application.",
            value=st.session_state["suggestions"],
            disabled=score < FAILURE_SCORE,
        )
        generate_clicked = container.button("Generate Improved CV")
        if generate_clicked:
            st.session_state["generate_clicked"] = True
    else:
        container.error(
            "Your CV does not meet the job requirements. Please consider refining it further or applying for roles with matching qualifications."
        )
        container.markdown("### Report")
        container.write(st.session_state["evaluation_report"])
        container.markdown("### Improvement Suggestions")
        container.text_area(
            "Review the suggestions.",
            value=st.session_state["suggestions"],
            disabled=True,
        )


# Handle CV Generation
if st.session_state.get("generate_clicked"):
    container.empty()
    try:
        if st.session_state["evaluation"] and st.session_state["suggestions"]:
            with st.spinner("Generating your updated CV..."):
                updated_cv = st.session_state["ai_utilities"].rewrite_cv(
                    st.session_state["cv_content"],
                    st.session_state["suggestions"],
                    st.session_state["evaluation"].get("jd_summary", ""),
                )

            container.markdown("### Updated CV")
            container.code(updated_cv, language="markdown")
            st.download_button(
                "Download Improved CV",
                data=updated_cv,
                file_name="enhanced_cv.md",
                mime="text/markdown",
            )
            st.session_state["generate_clicked"] = False  # Reset state
        else:
            st.error("Missing data for CV rewrite.")
    except Exception as e:
        st.error(f"Error generating CV: {e}")
