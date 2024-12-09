import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import sacrebleu
from typing import List, Tuple
import numpy as np
from io import StringIO
from pymongo import AsyncMongoClient
import asyncio

# Add the parent directory to the Python path
root_path = Path(__file__).parent.parent
sys.path.append(str(root_path))

# Page config
st.set_page_config(
    page_title="Evaluation - MTPE Manager",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


async def get_mongo_connection():
    """Get MongoDB connection"""
    connection_string = st.secrets["MONGO_CONNECTION_STRING"]
    client = AsyncMongoClient(
        connection_string, tlsAllowInvalidCertificates=True)
    db = client['mtpe_database']
    return db


async def get_users():
    """Retrieve list of users from MongoDB"""
    db = await get_mongo_connection()
    collection = db['user_progress']

    users = []
    cursor = collection.find({}, {'user_name': 1, 'user_surname': 1})
    async for doc in cursor:
        if 'user_name' in doc and 'user_surname' in doc:
            users.append({
                'name': doc['user_name'],
                'surname': doc['user_surname']
            })

    return users


async def get_post_edited_translations(user_name: str, user_surname: str):
    """Retrieve post-edited translations from MongoDB for specific user"""
    db = await get_mongo_connection()
    collection = db['user_progress']

    # Find specific user's progress
    doc = await collection.find_one({
        'user_name': user_name,
        'user_surname': user_surname
    })

    if doc and 'metrics' in doc:
        # Extract post-edited translations from metrics instead of full_text
        # This ensures we get only the edited translations
        metrics = sorted(doc['metrics'], key=lambda x: x['segment_id'])
        return [m['edited'] for m in metrics]

    return []


def calculate_metrics(references: List[str], hypotheses: List[str]) -> Tuple[float, float, float]:
    """Calculate BLEU, chrF, and TER scores"""
    # BLEU score
    bleu = sacrebleu.corpus_bleu(hypotheses, [references])

    # chrF score
    chrf = sacrebleu.corpus_chrf(hypotheses, [references])

    # TER score
    ter = sacrebleu.corpus_ter(hypotheses, [references])

    return bleu.score, chrf.score, ter.score


def process_file(uploaded_file) -> pd.DataFrame:
    """Process uploaded reference file and return a DataFrame"""
    if uploaded_file.name.endswith('.txt'):
        # Read text file line by line
        content = uploaded_file.getvalue().decode('utf-8')
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        return pd.DataFrame({'reference': lines})
    elif uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(uploaded_file)

    return df


def main():
    st.title("📊 Translation Evaluation")
    st.markdown("---")

    # Create tabs for different evaluation modes
    tabs = st.tabs(["📈 Metrics Calculation", "📊 Results History"])

    # Metrics Calculation Tab
    with tabs[0]:
        st.header("Calculate MT Metrics")

        # User selection section
        st.subheader("👤 Select User")
        users = asyncio.run(get_users())

        if not users:
            st.error("No users found in the database.")
            return

        # Create user selection dropdown
        user_options = [f"{user['name']} {user['surname']}" for user in users]
        selected_user = st.selectbox(
            "Select user to evaluate",
            options=user_options
        )

        # Split selected user into name and surname
        selected_name, selected_surname = selected_user.split(' ', 1)

        with st.container():
            st.caption("""
            Upload your reference translations to calculate quality metrics against post-edited translations.
            Supported file formats: CSV, Excel, TXT (tab-separated)
            """)

            # File upload section
            st.subheader("📄 Reference Translations")
            reference_file = st.file_uploader(
                "Upload reference file",
                type=['csv', 'xlsx', 'xls', 'txt'],
                key="reference_upload"
            )

            if reference_file:
                try:
                    # Process reference file
                    ref_df = process_file(reference_file)

                    # Get post-edited translations from MongoDB for selected user
                    post_edited = asyncio.run(get_post_edited_translations(
                        selected_name, selected_surname))

                    if not post_edited:
                        st.error(
                            f"No post-edited translations found for {selected_user}.")
                        return

                    # Get references directly from the 'reference' column
                    references = ref_df['reference'].tolist()

                    # Ensure we have matching number of translations
                    if len(references) != len(post_edited):
                        st.error(f"Number of reference translations ({len(references)}) does not match "
                                 f"number of post-edited translations ({len(post_edited)})")
                        return

                    if st.button("Calculate Metrics", type="primary", use_container_width=True):
                        bleu, chrf, ter = calculate_metrics(
                            references, post_edited)

                        # Display results
                        st.subheader("📊 Results")

                        # Metrics in columns
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric(
                                "BLEU Score",
                                f"{bleu:.2f}",
                                help="Higher is better (0-100)"
                            )

                        with col2:
                            st.metric(
                                "chrF Score",
                                f"{chrf:.2f}",
                                help="Higher is better (0-100)"
                            )

                        with col3:
                            st.metric(
                                "TER Score",
                                f"{ter:.2f}",
                                help="Lower is better"
                            )

                        # Detailed comparison
                        st.subheader("🔍 Detailed Comparison")
                        comparison_df = pd.DataFrame({
                            'Reference': references,
                            'Post-edited': post_edited
                        })
                        st.dataframe(
                            comparison_df,
                            use_container_width=True,
                            hide_index=True
                        )

                except Exception as e:
                    st.error(f"Error processing data: {str(e)}")
                    st.info(
                        "Please make sure your reference file has the correct format.")

    # Results History Tab
    with tabs[1]:
        st.header("Evaluation History")
        st.info("🚧 This feature is coming soon!")


if __name__ == "__main__":
    main()
