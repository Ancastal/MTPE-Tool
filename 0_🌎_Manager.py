import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional
import pytz
import hashlib
import secrets
from enum import Enum


class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"


# Page config
st.set_page_config(
    page_title="MTPE Manager Dashboard",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
        padding: 1rem;
        border-right: 1px solid #e9ecef;
    }
    .stApp {
        background-color: #ffffff;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .user-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    .stats-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    .plotly-chart {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .settings-item {
        margin: 1rem 0;
    }
    .settings-item label {
        font-size: 0.9rem;
        color: #666;
        margin-bottom: 0.4rem;
    }
    .version-info {
        font-size: 0.8rem;
        color: #888;
        margin-top: 1rem;
        opacity: 0.8;
    }
</style>
""", unsafe_allow_html=True)


def connect_to_mongodb():
    """Connect to MongoDB database"""
    connection_string = st.secrets["MONGO_CONNECTION_STRING"]
    client = MongoClient(
        connection_string,
        tlsAllowInvalidCertificates=True  # For development only
    )
    return client['mtpe_database']


def get_all_users() -> List[Dict]:
    """Get all users and their progress from MongoDB"""
    db = connect_to_mongodb()
    collection = db['user_progress']
    return list(collection.find())


def format_time(seconds: float) -> str:
    """Format seconds into a readable time string"""
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}m {remaining_seconds}s"


def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_salt() -> str:
    """Generate a random salt for password hashing"""
    return secrets.token_hex(16)


def authenticate_user(email: str, password: str) -> Optional[Dict]:
    """Authenticate a user and return user data if successful"""
    db = connect_to_mongodb()
    users = db['users']

    user = users.find_one({"email": email, "active": True})
    if not user:
        return None

    hashed_password = hash_password(password + user['salt'])
    if hashed_password != user['password_hash']:
        return None

    return user


def init_admin_if_needed():
    """Initialize admin user if no users exist"""
    db = connect_to_mongodb()
    users = db['users']

    if users.count_documents({}) == 0:
        create_user(
            email=st.secrets["ADMIN_EMAIL"],
            password=st.secrets["ADMIN_PASSWORD"],
            name="Admin",
            surname="User",
            role=UserRole.ADMIN
        )


def login_required(func):
    """Decorator to require login for certain pages/functions"""
    def wrapper(*args, **kwargs):
        if "user" not in st.session_state:
            st.warning("Please log in to access this page.")
            show_login_page()
            return
        return func(*args, **kwargs)
    return wrapper


def show_login_page():
    """Display login form"""
    st.title("Login")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            user = authenticate_user(email, password)
            if user:
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("Invalid email or password")


def main():
    init_admin_if_needed()

    if "user" not in st.session_state:
        show_login_page()
        return

    # Original dashboard code
    st.title("👨‍💼 MTPE Manager Dashboard")
    st.markdown("""
    Welcome to the MTPE Manager Dashboard! Here you can monitor user progress, analyze performance metrics,
    and manage the post-editing project effectively.
    """)

    # Get all users data
    users_data = get_all_users()

    if not users_data:
        st.warning(
            "No user data available yet. Users need to complete some translations first.")
        return

    # Overview metrics
    st.header("📊 Project Overview")
    col1, col2, col3, col4 = st.columns(4)

    total_users = len(users_data)
    total_segments = sum(len(user.get('metrics', []))
                         for user in users_data)
    total_time = sum(
        sum(metric.get('edit_time', 0)
            for metric in user.get('metrics', []))
        for user in users_data
    )
    avg_time_per_segment = total_time / total_segments if total_segments > 0 else 0

    with col1:
        st.metric("Total Users", total_users)
    with col2:
        st.metric("Total Segments", total_segments)
    with col3:
        st.metric("Total Time", format_time(total_time))
    with col4:
        st.metric("Avg Time/Segment", format_time(avg_time_per_segment))

    # User Performance Analysis
    st.header("👥 User Performance Analysis")

    # Prepare data for visualization
    user_stats = []
    for user in users_data:
        metrics = user.get('metrics', [])
        if not metrics:
            continue

        total_segments = len(metrics)
        total_time = sum(m.get('edit_time', 0) for m in metrics)
        avg_time = total_time / total_segments
        total_edits = sum(m.get('insertions', 0) +
                          m.get('deletions', 0) for m in metrics)

        user_stats.append({
            'name': f"{user['user_name']} {user['user_surname']}",
            'segments': total_segments,
            'total_time': total_time,
            'avg_time': avg_time,
            'total_edits': total_edits
        })

    if user_stats:
        df = pd.DataFrame(user_stats)

        # User comparison charts
        col1, col2 = st.columns(2)

        with col1:
            fig = px.bar(
                df,
                x='name',
                y='segments',
                title='Segments Completed by User',
                color='segments',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(
                df,
                x='name',
                y='avg_time',
                title='Average Time per Segment (seconds)',
                color='avg_time',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # Individual User Details
    st.header("🎯 Individual User Details")

    # User selector
    selected_user = st.selectbox(
        "Select User",
        options=[
            f"{user['user_name']} {user['user_surname']}" for user in users_data]
    )

    # Display selected user's details
    user_data = next(
        user for user in users_data
        if f"{user['user_name']} {user['user_surname']}" == selected_user
    )

    metrics = user_data.get('metrics', [])
    if metrics:
        metrics_df = pd.DataFrame(metrics)

        # User stats cards
        st.subheader("User Statistics")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Completed Segments",
                len(metrics),
                help="Total number of segments completed by this user"
            )

        with col2:
            total_user_time = metrics_df['edit_time'].sum()
            st.metric(
                "Total Time",
                format_time(total_user_time),
                help="Total time spent on post-editing"
            )

        with col3:
            avg_user_time = metrics_df['edit_time'].mean()
            st.metric(
                "Average Time/Segment",
                format_time(avg_user_time),
                help="Average time spent per segment"
            )

        # Progress over time
        st.subheader("Progress Over Time")

        # Create cumulative progress chart
        metrics_df['cumulative_segments'] = range(1, len(metrics_df) + 1)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=metrics_df.index,
            y=metrics_df['cumulative_segments'],
            mode='lines+markers',
            name='Segments Completed',
            line=dict(color='#2E86C1', width=3),
            marker=dict(size=8)
        ))
        fig.update_layout(
            title='Cumulative Segments Completed',
            xaxis_title='Segment Number',
            yaxis_title='Total Segments',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        # Editing patterns
        st.subheader("Editing Patterns")
        col1, col2 = st.columns(2)

        with col1:
            # Time distribution
            fig = px.histogram(
                metrics_df,
                x='edit_time',
                title='Distribution of Editing Times',
                labels={'edit_time': 'Time (seconds)'},
                color_discrete_sequence=['#2E86C1']
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Edits distribution
            metrics_df['total_edits'] = metrics_df['insertions'] + \
                metrics_df['deletions']
            fig = px.histogram(
                metrics_df,
                x='total_edits',
                title='Distribution of Edit Operations',
                labels={'total_edits': 'Number of Edits'},
                color_discrete_sequence=['#2E86C1']
            )
            st.plotly_chart(fig, use_container_width=True)

        # Detailed metrics table
        st.subheader("Detailed Metrics")
        st.dataframe(
            metrics_df[['segment_id', 'edit_time',
                        'insertions', 'deletions']],
            use_container_width=True
        )

        # Export options
        st.subheader("Export Data")
        col1, col2 = st.columns(2)

        with col1:
            csv = metrics_df.to_csv(index=False)
            st.download_button(
                "📥 Download CSV",
                data=csv,
                file_name=f"{selected_user}_metrics.csv",
                mime="text/csv"
            )

        with col2:
            st.download_button(
                "📥 Download JSON",
                data=metrics_df.to_json(orient='records'),
                file_name=f"{selected_user}_metrics.json",
                mime="application/json"
            )
    else:
        st.info("No metrics available for this user yet.")


if __name__ == "__main__":
    main()
