import streamlit as st
import pandas as pd
from typing import List, Tuple
import time
from dataclasses import dataclass
from pathlib import Path
import difflib
import json

st.set_page_config(
    page_title="MT Post-Editing Tool",
    page_icon="🌍",
)

@dataclass
class EditMetrics:
    """Class to store metrics for each segment edit"""
    segment_id: int
    original: str
    edited: str
    edit_time: float
    insertions: int
    deletions: int

def calculate_edit_distance(original: str, edited: str) -> Tuple[int, int]:
    """Calculate insertions and deletions between original and edited text"""
    d = difflib.Differ()
    diff = list(d.compare(original.split(), edited.split()))
    
    insertions = len([d for d in diff if d.startswith('+')])
    deletions = len([d for d in diff if d.startswith('-')])
    
    return insertions, deletions

def load_segments(uploaded_file) -> List[str]:
    """Load segments from uploaded file"""
    if uploaded_file is None:
        return []
    
    content = uploaded_file.getvalue().decode("utf-8")
    return [line.strip() for line in content.split('\n') if line.strip()]

def init_session_state():
    """Initialize session state variables"""
    if 'current_segment' not in st.session_state:
        st.session_state.current_segment = 0
    if 'segments' not in st.session_state:
        st.session_state.segments = []
    if 'edit_metrics' not in st.session_state:
        st.session_state.edit_metrics = []
    if 'start_time' not in st.session_state:
        st.session_state.start_time = None

def load_css():
    with open("../static/styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def highlight_differences(original: str, edited: str) -> str:
    """Create HTML with highlighted differences"""
    d = difflib.Differ()
    diff = list(d.compare(original.split(), edited.split()))
    
    html_parts = []
    for word in diff:
        if word.startswith('  '):
            html_parts.append(f'<span>{word[2:]}</span>')
        elif word.startswith('- '):
            html_parts.append(f'<span style="background-color: #ffcdd2">{word[2:]}</span>')
        elif word.startswith('+ '):
            html_parts.append(f'<span style="background-color: #c8e6c9">{word[2:]}</span>')
    
    return ' '.join(html_parts)

def main():
    load_css()
    st.markdown("""
        <h1 class='main-header pt-serif'>🌍 MT Post-Editing Tool</h1>
    """, unsafe_allow_html=True)

    # Render header outside tabs
    st.markdown("""
        <div class="card pt-serif">
            <p><strong>Hi, I'm Antonio. 👋</strong></p>
            <p>I'm a PhD candidate in Artificial Intelligence at the University of Pisa, working on Creative Machine Translation with LLMs.</p>
            <p>My goal is to develop translation systems that can preserve style, tone, and creative elements while accurately conveying meaning across languages.</p>
            <p>Learn more about me at <a href="https://www.ancastal.com" target="_blank">www.ancastal.com</a></p>
        </div>

        <div class="info-card">
            <p>💡 In order to <strong>get started</strong>, please upload a text file containing your translations.</p>
        </div>
    """, unsafe_allow_html=True)

    init_session_state()

    # File upload with styled container
    with st.container():
        uploaded_file = st.file_uploader(
            "Upload a text file with translations (one per line)", 
            type=['txt']
        )
    
    if uploaded_file and len(st.session_state.segments) == 0:
        st.session_state.segments = load_segments(uploaded_file)
        st.rerun()

    if not st.session_state.segments:
        return

    # Check if editing is complete
    if st.session_state.current_segment >= len(st.session_state.segments):
        st.divider()
        display_results()
        return  # Exit main() to prevent the editor from showing

    st.divider()

    # Add segment selection dropdown
    segment_idx = st.selectbox(
        "Select segment to edit",
        range(len(st.session_state.segments)),
        index=st.session_state.current_segment,
        format_func=lambda x: f"Segment {x + 1}",
        key='segment_select'
    )
    st.session_state.current_segment = segment_idx

    # Display progress
    st.progress(st.session_state.current_segment / len(st.session_state.segments))

    # Display current segment
    current_text = st.session_state.segments[st.session_state.current_segment]

    with st.container(border=True):
        st.markdown("**Original Text:**")
        st.info(current_text)

        if st.session_state.start_time is None:
            st.session_state.start_time = time.time()

        edited_text = st.text_area(
            "Edit Translation:",
            value=current_text,
            key="edit_area",
        )

    # Navigation buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Previous", 
                     key="prev_segment", 
                     disabled=st.session_state.current_segment == 0):
            save_metrics(current_text, edited_text)
            st.session_state.current_segment -= 1
            st.session_state.start_time = None
            st.rerun()

    with col2:
        # Change the button text on the last segment
        is_last_segment = st.session_state.current_segment == len(st.session_state.segments) - 1
        button_text = "Finish ✨" if is_last_segment else "Next ➡️"
        
        if st.button(button_text, key="next_segment"):
            save_metrics(current_text, edited_text)
            st.session_state.current_segment += 1
            st.session_state.start_time = None
            st.rerun()

    # Show editing statistics
    if edited_text != current_text:
        st.divider()
        with st.expander("📊 Post-Editing Statistics", expanded=True):
            col1, col2, col3 = st.columns(3)

            with col1:
                edit_time = time.time() - st.session_state.start_time
                minutes = int(edit_time // 60)
                seconds = int(edit_time % 60)
                st.metric(
                    "Editing Time",
                    f"{minutes}m {seconds}s",
                    help="Time spent editing this segment"
                )

            insertions, deletions = calculate_edit_distance(current_text, edited_text)
            with col2:
                st.metric(
                    "Insertions",
                    f"{insertions}",
                    help="Number of inserted words"
                )

            with col3:
                st.metric(
                    "Deletions",
                    f"{deletions}",
                    help="Number of deleted words"
                )

        with st.expander("👀 View Changes", expanded=False):
            st.markdown(highlight_differences(current_text, edited_text), unsafe_allow_html=True)


def save_metrics(original: str, edited: str):
    """Save metrics for the current segment"""
    if st.session_state.start_time is None:
        return
        
    edit_time = time.time() - st.session_state.start_time
    insertions, deletions = calculate_edit_distance(original, edited)
    
    metrics = EditMetrics(
        segment_id=st.session_state.current_segment,
        original=original,
        edited=edited,
        edit_time=edit_time,
        insertions=insertions,
        deletions=deletions
    )
    
    st.session_state.edit_metrics.append(metrics)
def display_results():
    """Display final results and statistics after post-editing is complete."""
    # Convert metrics to DataFrame for detailed analysis
    # No columns "segment_id" and index
    df = pd.DataFrame([vars(m) for m in st.session_state.edit_metrics])
    df = df.drop(columns=["segment_id"])
    df = df.reset_index(drop=True)

    # Display summary statistics in a compact layout
    st.markdown("##### Summary Statistics", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Segments", len(df))
    with col2:
        st.metric("Total Time Spent", f"{df['edit_time'].sum():.1f}s")
    with col3:
        st.metric("Average Time/Segment", f"{df['edit_time'].mean():.1f}s")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Edits", f"{int(df['insertions'].sum() + df['deletions'].sum())} edits")
    with col2:
        st.metric("Total Insertions", f"{int(df['insertions'].sum())} ins")
    with col3:
        st.metric("Total Deletions", f"{int(df['deletions'].sum())} dels")

    # Show detailed metrics in a table
    st.divider()
    st.markdown("##### Detailed Metrics", unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)

    # Options for downloading metrics
    st.divider()
    st.markdown("##### Download Metrics", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv_data,
            file_name="post_editing_metrics.csv",
            mime="text/csv"
        )
    with col2:
        json_data = [
            {
                "segment_id": metric.segment_id,
                "source": metric.original,
                "post_edited": metric.edited,
                "edit_time_seconds": round(metric.edit_time, 2),
                "insertions": metric.insertions,
                "deletions": metric.deletions
            }
            for metric in st.session_state.edit_metrics
        ]
        json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
        st.download_button(
            label="📥 Download as JSON",
            data=json_str,
            file_name="post_edited_segments.json",
            mime="application/json"
        )
 
    st.divider()
    # Finishing note
    st.markdown("""
        <div class="info-card">
            <p>Thank you for using the MT Post-Editing Tool! 😊</p>
            <br>
            <p>We value your feedback. If you encounter any issues or have suggestions, feel free to reach out via the contact form on <a href="https://www.ancastal.com" target="_blank">my website</a>.</p>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.error(traceback.format_exc())