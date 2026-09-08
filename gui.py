"""
Streamlit GUI for Course Scheduler
Dark-purple theme with interactive timetable view
"""

import streamlit as st
import pandas as pd
import os
import sys
import subprocess
from datetime import datetime
from typing import Dict, List
from modules.repeat_finder import find_compatible_batches

# Page config
st.set_page_config(
    page_title="Course Scheduler",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark-purple theme
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --primary-color: #6B46C1;
        --secondary-color: #8B5CF6;
        --background-color: #1E1B2E;
        --surface-color: #2D2A3E;
        --text-color: #E9D5FF;
        --accent-color: #A78BFA;
    }
    
    /* Override Streamlit defaults */
    .stApp {
        background: linear-gradient(135deg, #1E1B2E 0%, #2D2A3E 100%);
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Header styling */
    h1, h2, h3 {
        color: #E9D5FF !important;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: #2D2A3E;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #6B46C1;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        background-color: #8B5CF6;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(107, 70, 193, 0.4);
    }
    
    /* Selectbox and multiselect */
    .stSelectbox label, .stMultiSelect label {
        color: #E9D5FF !important;
    }
    
    /* Dataframe styling */
    .dataframe {
        background-color: #2D2A3E;
        color: #E9D5FF;
    }
    
    /* Table styling */
    table {
        background-color: #2D2A3E !important;
    }
    
    th {
        background-color: #6B46C1 !important;
        color: white !important;
    }
    
    td {
        background-color: #2D2A3E !important;
        color: #E9D5FF !important;
    }
    
    /* Metric cards */
    [data-testid="stMetricValue"] {
        color: #A78BFA !important;
    }
    
    [data-testid="stMetricLabel"] {
        color: #E9D5FF !important;
    }
</style>
""", unsafe_allow_html=True)

# Days of the week
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
DAY_ORDER = {day: i for i, day in enumerate(DAYS)}

# Time slots (30-min intervals from 8:00 to 18:00)
def get_time_slots():
    slots = []
    for hour in range(8, 18):
        slots.append(f"{hour:02d}:00")
        slots.append(f"{hour:02d}:30")
    return slots

def time_to_minutes(time_str: str) -> int:
    """Convert time string to minutes since midnight"""
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])

def minutes_to_slot(minutes: int) -> int:
    """Convert minutes to slot index (0-19 for 8:00-18:00 in 30-min intervals)"""
    return (minutes - 8 * 60) // 30

def slot_to_time(slot: int) -> str:
    """Convert slot index to time string"""
    total_minutes = 8 * 60 + slot * 30
    hours = total_minutes // 60
    mins = total_minutes % 60
    return f"{hours:02d}:{mins:02d}"

def get_course_color(course_code: str, color_map: Dict[str, str]) -> str:
    """Get or assign color for a course"""
    if course_code not in color_map:
        # Generate color based on course code hash
        colors = [
            '#6B46C1', '#8B5CF6', '#A78BFA', '#C4B5FD',
            '#7C3AED', '#9333EA', '#A855F7', '#C084FC',
            '#5B21B6', '#6D28D9', '#7E22CE', '#9F7AEA'
        ]
        idx = hash(course_code) % len(colors)
        color_map[course_code] = colors[idx]
    return color_map[course_code]

def run_scheduler():
    """Run scheduler.py to generate schedule.csv"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scheduler_path = os.path.join(script_dir, 'modules', 'scheduler.py')
    
    try:
        # Run scheduler
        result = subprocess.run(
            [sys.executable, scheduler_path],
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Scheduler timed out after 5 minutes"
    except Exception as e:
        return False, str(e)

@st.cache_data
def load_schedule():
    """Load schedule CSV, auto-generate if missing"""
    schedule_path = os.path.join(os.path.dirname(__file__), 'schedule.csv')
    
    if not os.path.exists(schedule_path):
        # Try to run scheduler
        with st.spinner("Schedule not found. Generating schedule... This may take a moment."):
            success, message = run_scheduler()
            if success:
                st.success("Schedule generated successfully!")
                if os.path.exists(schedule_path):
                    # Clear cache to reload
                    load_schedule.clear()
                    return pd.read_csv(schedule_path)
            else:
                st.error(f"Failed to generate schedule: {message}")
                return None
    
    return pd.read_csv(schedule_path)

def create_timetable_view(df: pd.DataFrame, selected_batch: str = None):
    """Create weekly timetable visualization"""
    if df.empty:
        return None, {}
    
    # Filter by batch if selected
    if selected_batch:
        df = df[df['BatchName'] == selected_batch]
    
    if df.empty:
        return None, {}
    
    # Create color map for courses
    color_map = {}
    for course_code in df['CourseCode'].unique():
        get_course_color(course_code, color_map)
    
    # Create timetable grid - store events with their start slot and duration
    timetable = {}
    for day in DAYS:
        timetable[day] = [None] * 20  # 20 slots (8:00-18:00, 30-min intervals)
    
    # Fill timetable - store event info in the starting slot only
    for _, row in df.iterrows():
        day = row['Day']
        start_time = row['StartTime']
        end_time = row['EndTime']
        duration = row['Duration']
        
        start_slot = minutes_to_slot(time_to_minutes(start_time))
        duration_slots = int(duration * 2)  # Convert hours to 30-min slots
        
        if start_slot < 20:
            if timetable[day][start_slot] is None:
                timetable[day][start_slot] = []
            timetable[day][start_slot].append({
                'course_code': str(row['CourseCode']),
                'course_name': str(row['CourseName']),
                'room': str(row['Room']),
                'type': str(row['Type']),
                'start_time': str(start_time),
                'end_time': str(end_time),
                'duration': float(duration),
                'duration_slots': duration_slots
            })
    
    return timetable, color_map

def escape_html(text):
    """Escape HTML special characters"""
    if text is None:
        return ""
    text = str(text)
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;"))

def render_timetable(timetable: Dict, color_map: Dict):
    """Render timetable as HTML table"""
    html = """
    <style>
        .timetable {
            width: 100%;
            border-collapse: collapse;
            background-color: #2D2A3E;
            color: #E9D5FF;
            font-family: Arial, sans-serif;
            margin: 20px 0;
        }
        .timetable th {
            background-color: #6B46C1;
            color: white;
            padding: 12px;
            text-align: center;
            border: 1px solid #8B5CF6;
            font-weight: bold;
        }
        .timetable td {
            border: 1px solid #4C1D95;
            padding: 4px;
            vertical-align: top;
            height: 30px;
            position: relative;
            background-color: #2D2A3E;
        }
        .time-slot {
            background-color: #1E1B2E;
            color: #A78BFA;
            font-size: 11px;
            padding: 4px;
            font-weight: 600;
            text-align: center;
        }
        .course-block {
            border-radius: 4px;
            padding: 6px 8px;
            margin: 1px;
            font-size: 11px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .course-block:hover {
            transform: scale(1.03);
            box-shadow: 0 4px 8px rgba(0,0,0,0.4);
            z-index: 10;
        }
        .course-code {
            font-weight: bold;
            font-size: 12px;
        }
        .course-details {
            font-size: 9px;
            margin-top: 2px;
            opacity: 0.95;
        }
    </style>
    <table class="timetable">
        <thead>
            <tr>
                <th>Time</th>
    """
    
    for day in DAYS:
        html += f"<th>{day}</th>"
    
    html += """
            </tr>
        </thead>
        <tbody>
    """
    
    # Track which slots are already occupied by multi-slot events (rowspan)
    occupied = {}
    for day in DAYS:
        occupied[day] = {}  # slot_idx -> remaining_rows
    
    time_slots = get_time_slots()
    for slot_idx in range(20):
        time_str = slot_to_time(slot_idx)
        html += f"<tr><td class='time-slot'>{time_str}</td>"
        
        for day in DAYS:
            # Check if this cell is part of a rowspan from a previous row
            if day in occupied and slot_idx in occupied[day]:
                # This slot is occupied by a rowspan, skip rendering
                occupied[day][slot_idx] -= 1
                if occupied[day][slot_idx] <= 0:
                    del occupied[day][slot_idx]
                continue
            
            events = timetable[day][slot_idx]
            if events and events[0] is not None:
                # Show first event
                event = events[0]
                course_code = escape_html(event['course_code'])
                course_name = escape_html(event['course_name'])
                room = escape_html(event['room'])
                event_type = escape_html(event['type'])
                start_time = escape_html(event['start_time'])
                end_time = escape_html(event['end_time'])
                duration_slots = event.get('duration_slots', 1)
                
                color = color_map.get(event['course_code'], '#6B46C1')
                
                # Mark subsequent slots as occupied for rowspan
                if duration_slots > 1:
                    if day not in occupied:
                        occupied[day] = {}
                    for i in range(1, duration_slots):
                        next_slot = slot_idx + i
                        if next_slot < 20:
                            occupied[day][next_slot] = duration_slots - i - 1
                
                rowspan_attr = f' rowspan="{duration_slots}"' if duration_slots > 1 else ''
                # Escape quotes in attributes properly
                html += f"""<td{rowspan_attr}><div class="course-block" style="background-color: {color};" data-code="{course_code}" data-name="{course_name}" data-room="{room}" data-type="{event_type}" data-start="{start_time}" data-end="{end_time}"><div class="course-code">{course_code}</div><div class="course-details">{room} | {event_type}</div></div></td>"""
            else:
                html += "<td></td>"
        
        html += "</tr>"
    
    html += """
        </tbody>
    </table>
    <script>
        // Add showDetails method to course blocks
        document.addEventListener('DOMContentLoaded', function() {
            const blocks = document.querySelectorAll('.course-block');
            blocks.forEach(function(block) {
                block.showDetails = function() {
                    const code = this.getAttribute('data-code') || '';
                    const name = this.getAttribute('data-name') || '';
                    const room = this.getAttribute('data-room') || '';
                    const type = this.getAttribute('data-type') || '';
                    const start = this.getAttribute('data-start') || '';
                    const end = this.getAttribute('data-end') || '';
                    alert('Course: ' + code + '\\n' +
                          'Name: ' + name + '\\n' +
                          'Room: ' + room + '\\n' +
                          'Type: ' + type + '\\n' +
                          'Time: ' + start + ' - ' + end);
                };
                block.addEventListener('click', block.showDetails);
            });
        });
    </script>
    """
    
    return html

def main():
    """Main application"""
    # Load data (will auto-generate if missing)
    schedule_df = load_schedule()
    
    if schedule_df is None or schedule_df.empty:
        st.error("⚠️ Could not load schedule. Please ensure courses_sample.csv and batches_sample.csv exist in the root directory.")
        st.info("To manually generate the schedule, run: `python modules/scheduler.py`")
        return
    
    # Sidebar Navigation
    st.sidebar.title("📅 Course Scheduler")
    st.sidebar.markdown("---")
    
    # Navigation menu
    page = st.sidebar.radio(
        "Navigation",
        ["🏠 Dashboard", "🔁 Repeat Course", "📅 Weekly Timetable", "📂 Import Schedule", "📥 Export", "⚙️ Settings"],
        label_visibility="collapsed"
    )
    
    st.sidebar.markdown("---")
    
    # Statistics Section
    st.sidebar.header("📈 Statistics")
    
    total_events = len(schedule_df)
    total_batches = schedule_df['BatchName'].nunique()
    total_courses = schedule_df['CourseCode'].nunique()
    total_rooms = schedule_df['Room'].nunique()
    
    st.sidebar.metric("Total Events", f"{total_events:,}")
    st.sidebar.metric("Total Batches", total_batches)
    st.sidebar.metric("Total Courses", total_courses)
    st.sidebar.metric("Rooms Used", total_rooms)
    
    st.sidebar.markdown("---")
    
    # Quick Info Section
    st.sidebar.header("ℹ️ Quick Info")
    
    # Most used rooms
    room_usage = schedule_df['Room'].value_counts().head(5)
    st.sidebar.write("**Most Used Rooms:**")
    for room, count in room_usage.items():
        st.sidebar.write(f"  • {room}: {count} events")
    
    st.sidebar.markdown("---")
    
    # Course Distribution
    st.sidebar.header("📚 Course Distribution")
    course_counts = schedule_df['CourseCode'].value_counts().head(5)
    st.sidebar.write("**Most Scheduled Courses:**")
    for course, count in course_counts.items():
        st.sidebar.write(f"  • {course}: {count} events")
    
    st.sidebar.markdown("---")
    
    # Batch Distribution
    st.sidebar.header("👥 Batch Distribution")
    batch_counts = schedule_df['BatchName'].value_counts().head(5)
    st.sidebar.write("**Most Active Batches:**")
    for batch, count in batch_counts.items():
        st.sidebar.write(f"  • {batch}: {count} events")
    
    st.sidebar.markdown("---")
    
    # Time Distribution
    st.sidebar.header("⏰ Time Distribution")
    try:
        schedule_df_copy = schedule_df.copy()
        schedule_df_copy['Hour'] = pd.to_datetime(schedule_df_copy['StartTime'], format='%H:%M', errors='coerce').dt.hour
        hour_dist = schedule_df_copy['Hour'].dropna().value_counts().sort_index()
        if not hour_dist.empty:
            st.sidebar.write("**Events by Hour:**")
            for hour in sorted(hour_dist.index):
                count = int(hour_dist[hour])
                bar = "█" * min(count // 2, 20)  # Simple bar visualization, max 20 chars
                st.sidebar.write(f"  {int(hour):02d}:00 - {bar} {count}")
    except Exception:
        st.sidebar.write("**Events by Hour:**")
        st.sidebar.write("  Data unavailable")
    
    st.sidebar.markdown("---")
    
    # System Info
    st.sidebar.header("🔧 System")
    st.sidebar.write(f"**Last Updated:**")
    st.sidebar.write(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    if st.sidebar.button("🔄 Regenerate Schedule"):
        with st.sidebar:
            with st.spinner("Regenerating..."):
                success, message = run_scheduler()
                if success:
                    st.sidebar.success("Schedule regenerated!")
                    st.rerun()
                else:
                    st.sidebar.error(f"Error: {message}")
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Course Scheduler v1.0")
    
    # Main Content Area
    st.title("📅 Course Scheduler")
    st.markdown("---")
    
    # Extract unique values
    all_batches = sorted(schedule_df['BatchName'].unique())
    
    # Page routing
    if page == "🏠 Dashboard":
        st.header("Dashboard")
        
        # Overall statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Events", f"{total_events:,}")
        
        with col2:
            st.metric("Unique Batches", total_batches)
        
        with col3:
            st.metric("Unique Courses", total_courses)
        
        with col4:
            st.metric("Total Rooms Used", total_rooms)
        
        st.markdown("---")
        
        # Charts and visualizations
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Events by Day")
            day_counts = schedule_df['Day'].value_counts()
            st.bar_chart(day_counts)
        
        with col2:
            st.subheader("Events by Type")
            type_counts = schedule_df['Type'].value_counts()
            st.bar_chart(type_counts)
        
        st.markdown("---")
        
        # Recent schedule preview
        st.subheader("Schedule Preview")
        st.dataframe(
            schedule_df.head(20),
            use_container_width=True,
            hide_index=True
        )
    
    elif page == "🔁 Repeat Course":
        st.header("Repeat Course Finder")

        # Select user's batch (single selection)
        st.subheader("Select Your Batch")
        user_batch = st.selectbox(
            "Your Batch",
            options=all_batches,
            index=0,
            key="repeat_user_batch"
        )

        # Get available courses in user's batch
        user_courses = sorted(schedule_df[schedule_df['BatchName'] == user_batch]['CourseCode'].unique())
        if not user_courses:
            st.info(f"No courses found for batch {user_batch}.")
        else:
            st.subheader("Select Course To Repeat")
            course_to_repeat = st.selectbox(
                "Course to repeat",
                options=user_courses,
                index=0,
                key="repeat_course_select"
            )

            st.markdown("---")

            if st.button("🔎 Find Compatible Batches"):
                with st.spinner("Searching for compatible batches..."):
                    compatible = find_compatible_batches(schedule_df, user_batch, course_to_repeat)

                if not compatible:
                    st.info(f"No compatible batches found for {course_to_repeat}.")
                else:
                    st.success(f"Found {len(compatible)} compatible batch(es) for {course_to_repeat}.")

                    # Flatten results for display
                    rows = []
                    for info in compatible:
                        batch_name = info.get('BatchName')
                        course_code = info.get('CourseCode')
                        course_name = info.get('CourseName')
                        for detail in info.get('ScheduleDetails', []):
                            rows.append({
                                'CompatibleBatch': batch_name,
                                'CourseCode': course_code,
                                'CourseName': course_name,
                                'Day': detail.get('Day'),
                                'StartTime': detail.get('StartTime'),
                                'EndTime': detail.get('EndTime'),
                                'Room': detail.get('Room'),
                                'Type': detail.get('Type')
                            })

                    if rows:
                        results_df = pd.DataFrame(rows)
                        st.subheader("Compatible Batch Suggestions")
                        st.dataframe(results_df, use_container_width=True, hide_index=True)

                        # Allow download
                        csv = results_df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Suggestions",
                            data=csv,
                            file_name=f"repeat_suggestions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
    
    elif page == "📅 Weekly Timetable":
        st.header("Weekly Timetable View")
        
        # Batch selector for timetable view - allow only one batch at a time
        st.subheader("🔍 Select Batch (single selection)")
        selected_batch = st.selectbox(
            "Select Batch to Display",
            options=all_batches,
            index=0,
            key="batch_selector_timetable_single"
        )

        # Course filter - timetable will update based on this
        all_courses = sorted(schedule_df['CourseCode'].unique())
        selected_course = st.selectbox(
            "Select Course to Filter (optional)",
            options=['All'] + all_courses,
            index=0,
            key="course_filter_timetable"
        )

        st.markdown("---")

        # Apply filters
        filtered_df = schedule_df.copy()
        if selected_batch:
            filtered_df = filtered_df[filtered_df['BatchName'] == selected_batch]
        if selected_course and selected_course != 'All':
            filtered_df = filtered_df[filtered_df['CourseCode'] == selected_course]
        
        # Create timetable
        if filtered_df.empty:
            st.info("No schedule data available for the selected batch or course.")
        else:
            timetable, color_map = create_timetable_view(filtered_df, selected_batch)
            
            if timetable and color_map:
                # Render timetable
                try:
                    html = render_timetable(timetable, color_map)
                    st.markdown(html, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error rendering timetable: {e}")
                
                # Legend
                st.markdown("### Course Color Legend")
                legend_cols = st.columns(min(6, len(color_map)))
                for idx, (course_code, color) in enumerate(color_map.items()):
                    with legend_cols[idx % 6]:
                        st.markdown(
                            f'<div style="background-color: {color}; padding: 8px; border-radius: 4px; '
                            f'color: white; text-align: center; font-weight: bold;">{course_code}</div>',
                            unsafe_allow_html=True
                        )
            else:
                st.info("No schedule data available for the selected batch.")
    
    elif page == "📂 Import Schedule":
        st.header("Import Schedule (CSV)")

        uploaded = st.file_uploader("Upload generated schedule CSV", type=["csv"], key="import_schedule_file")
        if uploaded is None:
            st.info("Upload a CSV file to view its timetable.")
        else:
            try:
                imported_df = pd.read_csv(uploaded)
            except Exception as e:
                st.error(f"Failed to read CSV: {e}")
                imported_df = None

            if imported_df is not None and not imported_df.empty:
                st.subheader("Imported Schedule Preview")
                st.dataframe(imported_df.head(10), use_container_width=True)

                # Course filter
                imported_courses = sorted(imported_df['CourseCode'].unique()) if 'CourseCode' in imported_df.columns else []
                selected_import_course = None
                if imported_courses:
                    selected_import_course = st.selectbox(
                        "Filter by Course (optional)",
                        options=['All'] + imported_courses,
                        index=0,
                        key="import_course_filter"
                    )

                # Apply filter
                display_df = imported_df.copy()
                if selected_import_course and selected_import_course != 'All':
                    display_df = display_df[display_df['CourseCode'] == selected_import_course]

                if display_df.empty:
                    st.info("No schedule rows match the selected course.")
                else:
                    # Create and render timetable
                    timetable, color_map = create_timetable_view(display_df)
                    if timetable and color_map:
                        try:
                            html = render_timetable(timetable, color_map)
                            st.markdown(html, unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Error rendering imported timetable: {e}")
                    else:
                        st.info("No timetable data available in the imported file.")
    
    elif page == "📥 Export":
        st.header("Export Schedule")
        
        # Batch filter for export
        st.subheader("🔍 Filter by Batch")
        selected_batches = st.multiselect(
            "Select Batch(es) to Export",
            options=all_batches,
            default=all_batches,
            key="batch_filter_export"
        )
        
        # Apply batch filter
        filtered_df = schedule_df.copy()
        if selected_batches:
            filtered_df = filtered_df[filtered_df['BatchName'].isin(selected_batches)]
        
        st.markdown("---")
        
        st.write("Export the filtered schedule to CSV:")
        
        # Convert to CSV
        csv = filtered_df.to_csv(index=False)
        
        st.download_button(
            label="📥 Download Filtered Schedule",
            data=csv,
            file_name=f"schedule_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        
        st.markdown("---")
        st.write("**Export Preview:**")
        st.dataframe(filtered_df.head(10), use_container_width=True)
    
    elif page == "⚙️ Settings":
        st.header("Settings")
        
        st.subheader("Schedule Generation")
        st.write("Manually regenerate the schedule from CSV files.")
        
        if st.button("🔄 Regenerate Schedule", type="primary"):
            with st.spinner("Regenerating schedule... This may take a moment."):
                success, message = run_scheduler()
                if success:
                    st.success("Schedule regenerated successfully!")
                    st.rerun()
                else:
                    st.error(f"Error: {message}")
        
        st.markdown("---")
        
        st.subheader("About")
        st.write("**Course Scheduler v1.0**")
        st.write("A comprehensive scheduling system for managing course timetables.")
        st.write(f"**Total Events:** {total_events}")
        st.write(f"**Total Batches:** {total_batches}")
        st.write(f"**Total Courses:** {total_courses}")

if __name__ == "__main__":
    main()

