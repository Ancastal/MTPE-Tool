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
    """Load and apply custom CSS styles"""
    with open("static/styles.css") as f:
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
    
    # Display current segment with improved styling
    current_text = st.session_state.segments[st.session_state.current_segment]
    
    with st.container(border=True):
        # Source text with info styling
        st.markdown("**Original Text:**")
        st.info(current_text)
    
        if st.session_state.start_time is None:
            st.session_state.start_time = time.time()
        
        # Edited text area with more height
        edited_text = st.text_area(
            "Edit Translation:",  # Move label back into text_area
            value=current_text,
            key="edit_area",
        )
    
    # Navigation buttons with emojis and improved layout
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
        if st.button("Next ➡️", 
                    key="next_segment",
                    disabled=st.session_state.current_segment >= len(st.session_state.segments)):
            save_metrics(current_text, edited_text)
            st.session_state.current_segment += 1
            st.session_state.start_time = None
            
            # If we've processed all segments, show results
        if st.session_state.current_segment >= len(st.session_state.segments):
            display_results()


    # Show editing statistics in expander
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
    """Display final results and statistics"""
    st.markdown("<h2 class='pt-serif'>Post-editing completed! 🎉</h2>", unsafe_allow_html=True)
    
    # Convert metrics to DataFrame for easy analysis
    df = pd.DataFrame([vars(m) for m in st.session_state.edit_metrics])
    
    # Display statistics in a metrics container
    st.markdown("### Editing Statistics", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Segments", len(df))
    with col2:
        st.metric("Total Time", f"{df['edit_time'].sum():.1f}s")
    with col3:
        st.metric("Avg. Time/Segment", f"{df['edit_time'].mean():.1f}s")
    
    col4, col5 = st.columns(2)
    with col4:
        st.metric("Total Insertions", int(df['insertions'].sum()))
    with col5:
        st.metric("Total Deletions", int(df['deletions'].sum()))
    
    # Display detailed metrics
    st.markdown("### Detailed Metrics", unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    
    # Download buttons
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download metrics as CSV",
            data=csv,
            file_name="post_editing_metrics.csv",
            mime="text/csv"
        )
    
    with col2:
        # Prepare JSON data
        json_data = []
        for metric in st.session_state.edit_metrics:
            json_data.append({
                "segment_id": metric.segment_id,
                "source": metric.original,
                "post_edited": metric.edited,
                "edit_time_seconds": round(metric.edit_time, 2),
                "insertions": metric.insertions,
                "deletions": metric.deletions
            })
        
        json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
        st.download_button(
            label="📥 Download segments as JSON",
            data=json_str,
            file_name="post_edited_segments.json",
            mime="application/json"
        )
    

if __name__ == "__main__":
    main()
