import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add project root to path so we can import our modules
sys.path.append(os.getcwd())

from src.database.db_manager import get_db_manager
from src.workers.tasks import discover_videos_task, download_video_task
from src.models.processing_status import DownloadStatus, TranscriptionStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)

def parse_transcript(content: str):
    """Parse transcript text into structured segments"""
    segments = []
    
    # Pattern 1: [HH:MM:SS] **Speaker:** Text
    # Pattern 2: (MM:SS-MM:SS) **Speaker:** Text
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Try Pattern 1: [HH:MM:SS]
        m1 = re.match(r'\[(\d{1,2}:\d{2}:\d{2})\]\s*(.*)', line)
        if m1:
            ts_str, remaining = m1.groups()
            h, m, s = map(int, ts_str.split(':'))
            seconds = h * 3600 + m * 60 + s
            
            speaker_match = re.match(r'\*\*(.*?):\*\*\s*(.*)', remaining)
            if speaker_match:
                speaker, text = speaker_match.groups()
                segments.append({"time": seconds, "time_str": ts_str, "speaker": speaker, "text": text, "type": "speech"})
            else:
                segments.append({"time": seconds, "time_str": ts_str, "speaker": None, "text": remaining, "type": "noise"})
            continue

        # Try Pattern 2: (MM:SS-MM:SS) or (HH:MM:SS-HH:MM:SS)
        # We take the start time
        m2 = re.match(r'\(((\d{1,2}:)?\d{2}:\d{2})-\d{2}:\d{2}\)\s*(.*)', line)
        if m2:
            ts_str, _, remaining = m2.groups()
            parts = ts_str.split(':')
            if len(parts) == 3:
                h, m, s = map(int, parts)
                seconds = h * 3600 + m * 60 + s
            else:
                m, s = map(int, parts)
                seconds = m * 60 + s
            
            speaker_match = re.match(r'\*\*(.*?):\*\*\s*(.*)', remaining)
            if speaker_match:
                speaker, text = speaker_match.groups()
                segments.append({"time": seconds, "time_str": ts_str, "speaker": speaker, "text": text, "type": "speech"})
            else:
                segments.append({"time": seconds, "time_str": ts_str, "speaker": None, "text": remaining, "type": "noise"})
            continue

    return segments

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
    
    # Initialize session state for discovered videos
    if 'discovered_videos' not in st.session_state:
        st.session_state.discovered_videos = []
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Trigger Discovery")
        
        # Date range inputs instead of slider
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime.now().date() - timedelta(days=30),
                help="Videos recorded on or after this date will be discovered"
            )
        with date_col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.now().date(),
                help="Videos recorded on or before this date will be discovered"
            )
        
        # Validate date range
        if start_date > end_date:
            st.error("⚠️ Start date must be before or equal to end date")
        else:
            # Convert date inputs to datetime for discovery service
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            if st.button("🔍 Discover House Videos"):
                with st.spinner("Discovering House videos..."):
                    try:
                        from src.services.discovery_service import DiscoveryService
                        from src.services.state_service import StateService
                        
                        discovery_service = DiscoveryService()
                        state_service = StateService(db)
                        
                        # Run discovery synchronously to get immediate results
                        house_videos = discovery_service.discover_videos(
                            start_date=start_datetime,
                            end_date=end_datetime,
                            source="house",
                            resolve_streams=False,  # Skip stream resolution for faster discovery
                        )
                        
                        # Mark videos as discovered in DB (but don't dispatch downloads yet)
                        for video in house_videos:
                            state_service.mark_video_discovered(video)
                        
                        # Store in session state for review
                        st.session_state.discovered_videos = house_videos
                        
                        # Display results
                        st.success(f"✅ Discovered **{len(house_videos)} House videos** between {start_date} and {end_date}")
                        st.info("📋 Review discovered videos below and click 'Download All Videos' when ready")
                    except Exception as e:
                        st.error(f"❌ Error discovering House videos: {str(e)}")
                        logger.error(f"Dashboard discovery error: {e}", exc_info=True)
            
            if st.button("🔍 Discover Senate Videos"):
                with st.spinner("Discovering Senate videos..."):
                    try:
                        from src.services.discovery_service import DiscoveryService
                        from src.services.state_service import StateService
                        
                        discovery_service = DiscoveryService()
                        state_service = StateService(db)
                        
                        # Run discovery synchronously to get immediate results
                        senate_videos = discovery_service.discover_videos(
                            start_date=start_datetime,
                            end_date=end_datetime,
                            source="senate",
                            resolve_streams=False,  # Skip stream resolution for faster discovery
                        )
                        
                        # Mark videos as discovered in DB (but don't dispatch downloads yet)
                        for video in senate_videos:
                            state_service.mark_video_discovered(video)
                        
                        # Store in session state for review
                        st.session_state.discovered_videos = senate_videos
                        
                        # Display results
                        st.success(f"✅ Discovered **{len(senate_videos)} Senate videos** between {start_date} and {end_date}")
                        st.info("📋 Review discovered videos below and click 'Download All Videos' when ready")
                    except Exception as e:
                        st.error(f"❌ Error discovering Senate videos: {str(e)}")
                        logger.error(f"Dashboard discovery error: {e}", exc_info=True)
            
            if st.button("🔍 Discover All Videos"):
                with st.spinner("Discovering videos from all sources..."):
                    try:
                        from src.services.discovery_service import DiscoveryService
                        from src.services.state_service import StateService
                        
                        discovery_service = DiscoveryService()
                        state_service = StateService(db)
                        
                        # Run discovery synchronously to get immediate results
                        all_videos = discovery_service.discover_videos(
                            start_date=start_datetime,
                            end_date=end_datetime,
                            source=None,  # Discover from all sources
                            resolve_streams=False,  # Skip stream resolution for faster discovery
                        )
                        
                        # Count by source
                        house_videos = [v for v in all_videos if v.source == "house"]
                        senate_videos = [v for v in all_videos if v.source == "senate"]
                        
                        # Mark videos as discovered in DB (but don't dispatch downloads yet)
                        for video in all_videos:
                            state_service.mark_video_discovered(video)
                        
                        # Store in session state for review
                        st.session_state.discovered_videos = all_videos
                        
                        # Display results
                        st.success(f"✅ Discovered **{len(house_videos)} House videos** and **{len(senate_videos)} Senate videos** between {start_date} and {end_date}")
                        st.info("📋 Review discovered videos below and click 'Download All Videos' when ready")
                    except Exception as e:
                        st.error(f"❌ Error discovering videos: {str(e)}")
                        logger.error(f"Dashboard discovery error: {e}", exc_info=True)
        
        # Display discovered videos table
        if st.session_state.discovered_videos:
            st.markdown("---")
            st.subheader("📋 Discovered Videos")
            st.caption(f"Total: {len(st.session_state.discovered_videos)} videos")
            
            # Create dataframe for display
            videos_data = []
            for video in st.session_state.discovered_videos:
                videos_data.append({
                    "Video ID": video.video_id,
                    "Title": video.title or "N/A",
                    "Committee": video.committee or "N/A",
                    "Date Recorded": video.date_recorded.strftime("%Y-%m-%d") if video.date_recorded else "N/A",
                    "Source": video.source.upper(),
                })
            
            if videos_data:
                df = pd.DataFrame(videos_data)
                # Display scrollable table
                st.dataframe(
                    df,
                    width="stretch",
                    height=400,
                )
                
                # Download button
                col_dl1, col_dl2 = st.columns([1, 3])
                with col_dl1:
                    if st.button("📥 Download All Videos", type="primary"):
                        with st.spinner(f"Dispatching download tasks for {len(st.session_state.discovered_videos)} videos..."):
                            try:
                                from src.services.state_service import StateService
                                state_service = StateService(db)
                                
                                # Dispatch download tasks
                                dispatched_count = 0
                                for video in st.session_state.discovered_videos:
                                    download_video_task.apply_async(args=[video.video_id, video.source], queue="download")
                                    dispatched_count += 1
                                
                                st.success(f"✅ Dispatched **{dispatched_count} download tasks** to Celery")
                                st.info("📥 Videos are now being downloaded in the background")
                                
                                # Optionally clear session state after dispatch
                                # st.session_state.discovered_videos = []
                            except Exception as e:
                                st.error(f"❌ Error dispatching downloads: {str(e)}")
                                logger.error(f"Dashboard download dispatch error: {e}", exc_info=True)
                
                with col_dl2:
                    if st.button("🗑️ Clear Discovered Videos"):
                        st.session_state.discovered_videos = []
                        st.rerun()

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
                # Setup session state for video seeking
                if 'video_start_time' not in st.session_state:
                    st.session_state.video_start_time = 0
                if 'seek_id' not in st.session_state:
                    st.session_state.seek_id = 0
                
                # If we switched videos, reset start time and seek ID
                if 'current_video_id' not in st.session_state or st.session_state.current_video_id != selected_video_id:
                    st.session_state.current_video_id = selected_video_id
                    st.session_state.video_start_time = 0
                    st.session_state.seek_id = 0

                t_col, v_col = st.columns([2, 1])
                
                with t_col:
                    st.subheader("📜 Transcript")
                    st.markdown(f"**Provider:** {transcript_record.provider}")
                    
                    # Parse transcript into segments
                    segments = parse_transcript(transcript_record.content)
                    
                    if not segments:
                        st.info("Transcript format not recognized for interactive viewing. Showing raw text.")
                        st.text_area("Raw Transcript", transcript_record.content, height=600)
                    else:
                        # Add custom CSS for highlighting
                        st.markdown("""
                            <style>
                            .highlight-segment {
                                background-color: rgba(255, 255, 0, 0.2);
                                border-left: 5px solid #ffcc00;
                                padding-left: 10px;
                                border-radius: 5px;
                            }
                            </style>
                        """, unsafe_allow_html=True)

                        # Create scrollable container
                        with st.container(height=600):
                            for i, seg in enumerate(segments):
                                # Check if this is the active segment (last clicked)
                                is_active = st.session_state.video_start_time == seg['time']
                                
                                # Use a container for styling
                                with st.container():
                                    if is_active:
                                        # Use markdown for highlighted row
                                        st.markdown(f'<div class="highlight-segment">', unsafe_allow_html=True)
                                    
                                    col_time, col_text = st.columns([1, 5])
                                    
                                    # Use a button for the timestamp to trigger seeking
                                    if col_time.button(f"🕒 {seg['time_str']}", key=f"btn_{selected_video_id}_{i}"):
                                        st.session_state.video_start_time = seg['time']
                                        st.session_state.seek_id += 1
                                        st.rerun()
                                    
                                    if seg['type'] == 'speech':
                                        col_text.markdown(f"**{seg['speaker']}:** {seg['text']}")
                                    else:
                                        col_text.markdown(f"*{seg['text']}*", help="Non-speech event")
                                    
                                    if is_active:
                                        st.markdown('</div>', unsafe_allow_html=True)
                
                with v_col:
                    st.subheader("📹 Video")
                    if video_record.download_path and os.path.exists(video_record.download_path):
                        # Video file path for st.video
                        st.video(
                            video_record.download_path, 
                            start_time=st.session_state.video_start_time,
                            key=f"video_{selected_video_id}_{st.session_state.seek_id}"
                        )
                        st.info(f"Currently playing from: {timedelta(seconds=st.session_state.video_start_time)}")
                    else:
                        st.warning("Video file not found locally.")
                        if video_record.url:
                            st.info(f"External Link: [Watch Here]({video_record.url})")
            else:
                st.error("Transcript content not found in database.")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("StateAffair v1.0 - Turbo Edition")

