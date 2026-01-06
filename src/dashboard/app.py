import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add project root to path so we can import our modules
sys.path.append(os.getcwd())

from src.database.db_manager import get_db_manager
from src.workers.tasks import discover_videos_task
from src.models.processing_status import DownloadStatus, TranscriptionStatus

# Page config
st.set_page_config(
    page_title="StateAffair Pipeline Dashboard",
    page_icon="🏛️",
    layout="wide"
)

# Initialize DB Manager
db = get_db_manager()

# Sidebar
st.sidebar.title("🏛️ StateAffair Control")
st.sidebar.markdown("---")

# Connection Status
db_url = os.getenv("DATABASE_URL", "SQLite")
st.sidebar.success(f"Connected to {db_url.split('://')[0]}")

# Navigation
page = st.sidebar.radio("Go to", ["Pipeline Control", "Video Registry", "Transcript Search"])

if page == "Pipeline Control":
    st.title("Pipeline Control Center")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Trigger Discovery")
        days = st.slider("Lookback Days", 1, 30, 2)
        
        if st.button("🔍 Discover House Videos"):
            with st.spinner("Dispatching House discovery task..."):
                discover_videos_task.delay(source="house", days=days)
                st.info("House discovery task dispatched to Celery.")
        
        if st.button("🔍 Discover Senate Videos"):
            with st.spinner("Dispatching Senate discovery task..."):
                discover_videos_task.delay(source="senate", days=days)
                st.info("Senate discovery task dispatched to Celery.")

        st.markdown("---")
        if st.button("♻️ Retry Failed Tasks"):
            with st.spinner("Re-queueing failed tasks..."):
                from src.workers.tasks import requeue_failed_tasks
                requeue_failed_tasks.delay()
                st.success("Retry task dispatched to Celery.")

    with col2:
        st.subheader("System Stats")
        stats = db.get_stats()
        
        s1, s2 = st.columns(2)
        s1.metric("Total Videos", stats['total'])
        s1.metric("Downloaded", stats['downloaded'])
        s2.metric("Transcribed", stats['transcribed'])
        s2.metric("Failed", stats['failed'])

elif page == "Video Registry":
    st.title("Video Registry")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    source_filter = col1.multiselect("Source", ["house", "senate"], default=["house", "senate"])
    status_filter = col2.multiselect("Transcription Status", ["pending", "in_progress", "completed", "failed"], default=["pending", "in_progress", "completed", "failed"])
    
    # Load Data
    videos = db.get_all_videos()
    if videos:
        df = pd.DataFrame([
            {
                "ID": v.id,
                "Source": v.source,
                "Title": v.title,
                "Committee": v.committee,
                "Date Recorded": v.date_recorded.strftime("%Y-%m-%d"),
                "Download": v.download_status,
                "Transcription": v.transcription_status,
                "Path": v.download_path
            } for v in videos
        ])
        
        # Apply Filters
        if source_filter:
            df = df[df['Source'].isin(source_filter)]
        if status_filter:
            df = df[df['Transcription'].isin(status_filter)]
            
        st.dataframe(df, width="stretch")
        
        # Details view
        selected_id = st.selectbox("View Details for Video ID", df['ID'].tolist())
        if selected_id:
            record = next(v for v in videos if v.id == selected_id)
            st.json({
                "id": record.id,
                "url": record.url,
                "stream_url": record.stream_url,
                "download_path": record.download_path,
                "audio_path": record.audio_path
            })
    else:
        st.info("No videos found in registry.")

elif page == "Transcript Search":
    st.title("Search & View Transcripts")
    
    # 1. Search and Filters
    col1, col2 = st.columns([2, 1])
    query = col1.text_input("Search keywords (e.g. 'Appropriations', 'Sine Die')", placeholder="Enter keywords...")
    source_filter = col2.multiselect("Filter Source", ["house", "senate"], default=["house", "senate"])
    
    # 2. Get Transcribed Sessions
    # We join with transcripts to ensure we only show those that have one
    all_videos = db.get_all_videos()
    transcribed_videos = [v for v in all_videos if v.transcription_status == "completed"]
    
    if source_filter:
        transcribed_videos = [v for v in transcribed_videos if v.source in source_filter]

    if not transcribed_videos:
        st.info("No transcribed sessions found matching the filters.")
    else:
        # 3. Handle Keyword Search Results
        if query:
            search_results = db.search_transcripts(query)
            if search_results:
                st.success(f"Found {len(search_results)} matching segments.")
                # Filter results by source
                if source_filter:
                    search_results = [r for r in search_results if r['source'] in source_filter]
                
                # Create a selection for search results
                result_options = [f"{r['date'].strftime('%Y-%m-%d')} - {r['title']} ({r['source']})" for r in search_results]
                selected_search_result = st.selectbox("Select a search result to view", result_options)
                
                if selected_search_result:
                    idx = result_options.index(selected_search_result)
                    selected_video_id = search_results[idx]['video_id']
                    selected_source = search_results[idx]['source']
            else:
                st.warning(f"No matches found for '{query}'.")
                selected_video_id = None
        else:
            # 4. Default view: List of all transcribed sessions
            session_options = [f"{v.date_recorded.strftime('%Y-%m-%d')} - {v.title} ({v.source})" for v in transcribed_videos]
            selected_session = st.selectbox("Select a session to view transcript", session_options)
            
            if selected_session:
                idx = session_options.index(selected_session)
                selected_video_id = transcribed_videos[idx].id
                selected_source = transcribed_videos[idx].source
            else:
                selected_video_id = None

        # 5. Display Transcript and Video Side-by-Side
        if selected_video_id:
            st.markdown("---")
            video_record = db.get_video_record(selected_video_id, selected_source)
            
            # Fetch transcript content
            session = db.get_session()
            from src.database.db_manager import TranscriptRecord
            transcript_record = session.query(TranscriptRecord).filter_by(video_id=selected_video_id).first()
            session.close()

            if transcript_record:
                t_col, v_col = st.columns([2, 1])
                
                with t_col:
                    st.subheader("📜 Transcript")
                    # Use a container with fixed height for scrolling if content is long
                    st.markdown(f"**Provider:** {transcript_record.provider}")
                    st.markdown(f'<div style="height: 600px; overflow-y: scroll; border: 1px solid #ccc; padding: 15px; border-radius: 5px;">{transcript_record.content.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
                
                with v_col:
                    st.subheader("📹 Video")
                    if video_record.download_path and os.path.exists(video_record.download_path):
                        # Video file path for st.video
                        st.video(video_record.download_path)
                    else:
                        st.warning("Video file not found locally.")
                        if video_record.url:
                            st.info(f"External Link: [Watch Here]({video_record.url})")
            else:
                st.error("Transcript content not found in database.")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("StateAffair v1.0 - Turbo Edition")

