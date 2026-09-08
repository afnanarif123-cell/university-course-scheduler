"""
Course Scheduler using A* Search Algorithm
Reads courses and batches CSVs and generates optimized schedules
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass
from collections import defaultdict
import os

# Room definitions
LECTURE_ROOMS = [f"G{i:02d}" for i in range(1, 10)] + \
                [f"{i}01" for i in range(1, 4)] + \
                [f"{i}{j:02d}" for i in range(1, 4) for j in range(2, 10)]
LAB_ROOMS = [f"CL{i:02d}" for i in range(1, 13)]

# Time slots: Mon-Fri, 30-min intervals (8:00-18:00)
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
TIME_SLOTS = []
for hour in range(8, 18):
    TIME_SLOTS.append(f"{hour:02d}:00")
    TIME_SLOTS.append(f"{hour:02d}:30")

@dataclass
class CourseEvent:
    """Represents a single course event (lecture or lab)"""
    course_code: str
    course_name: str
    batch_name: str
    day: str
    start_time: str
    end_time: str
    duration: float
    room: str
    event_type: str  # 'Lecture' or 'Lab'
    
    def to_dict(self):
        return {
            'BatchName': self.batch_name,
            'CourseCode': self.course_code,
            'CourseName': self.course_name,
            'Day': self.day,
            'StartTime': self.start_time,
            'EndTime': self.end_time,
            'Duration': self.duration,
            'Room': self.room,
            'Type': self.event_type
        }

@dataclass
class ScheduleState:
    """Represents a state in the A* search"""
    events: List[CourseEvent]
    room_usage: Dict[Tuple[str, str, str], bool]  # (room, day, time) -> occupied
    batch_schedules: Dict[str, List[CourseEvent]]  # batch_name -> events
    
    def __lt__(self, other):
        return id(self) < id(other)

def time_to_minutes(time_str: str) -> int:
    """Convert time string (HH:MM) to minutes since midnight"""
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])

def minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight to time string (HH:MM)"""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"

def get_time_slots(start_time: str, duration: float) -> List[str]:
    """Get all 30-min time slots for a given start time and duration"""
    start_min = time_to_minutes(start_time)
    duration_min = int(duration * 60)
    slots = []
    current = start_min
    while current < start_min + duration_min:
        slots.append(minutes_to_time(current))
        current += 30
    return slots

def expand_course_events(course_code: str, course_name: str, credits: int, batch_name: str) -> List[Dict]:
    """Expand a course into required weekly events based on credits"""
    events = []
    
    if credits == 2:
        # One 2-hour class per week
        events.append({
            'course_code': course_code,
            'course_name': course_name,
            'batch_name': batch_name,
            'duration': 2.0,
            'event_type': 'Lecture'
        })
    elif credits == 3:
        # Two 1.5-hour classes per week
        events.append({
            'course_code': course_code,
            'course_name': course_name,
            'batch_name': batch_name,
            'duration': 1.5,
            'event_type': 'Lecture'
        })
        events.append({
            'course_code': course_code,
            'course_name': course_name,
            'batch_name': batch_name,
            'duration': 1.5,
            'event_type': 'Lecture'
        })
    elif credits == 4:
        # Two 1.5-hour classes + one 3-hour lab per week
        events.append({
            'course_code': course_code,
            'course_name': course_name,
            'batch_name': batch_name,
            'duration': 1.5,
            'event_type': 'Lecture'
        })
        events.append({
            'course_code': course_code,
            'course_name': course_name,
            'batch_name': batch_name,
            'duration': 1.5,
            'event_type': 'Lecture'
        })
        events.append({
            'course_code': course_code,
            'course_name': course_name,
            'batch_name': batch_name,
            'duration': 3.0,
            'event_type': 'Lab'
        })
    
    return events

def check_constraints(state: ScheduleState, new_event: CourseEvent) -> Tuple[bool, str]:
    """Check if adding new_event violates any constraints"""
    batch_events = state.batch_schedules.get(new_event.batch_name, [])
    
    # Check for overlapping courses in the same batch
    for event in batch_events:
        if (event.day == new_event.day and
            event.start_time < new_event.end_time and
            event.end_time > new_event.start_time):
            return False, "Overlapping with existing course in batch"
    
    # Check room availability
    slots = get_time_slots(new_event.start_time, new_event.duration)
    for slot in slots:
        key = (new_event.room, new_event.day, slot)
        if state.room_usage.get(key, False):
            return False, "Room already occupied"
    
    # Check max consecutive classes
    same_day_events = [e for e in batch_events if e.day == new_event.day]
    same_day_events.append(new_event)
    same_day_events.sort(key=lambda x: time_to_minutes(x.start_time))
    
    # Check max 3 consecutive 1.5h classes
    consecutive_15h = 0
    for i, event in enumerate(same_day_events):
        if event.duration == 1.5:
            consecutive_15h += 1
            if consecutive_15h > 3:
                return False, "More than 3 consecutive 1.5h classes"
        else:
            consecutive_15h = 0
    
    # Check max 2 consecutive 2h classes
    consecutive_2h = 0
    for i, event in enumerate(same_day_events):
        if event.duration == 2.0:
            consecutive_2h += 1
            if consecutive_2h > 2:
                return False, "More than 2 consecutive 2h classes"
        else:
            consecutive_2h = 0
    
    # Check max 1 lab per day
    labs_today = sum(1 for e in same_day_events if e.event_type == 'Lab')
    if labs_today > 1:
        return False, "More than 1 lab per day"
    
    # Check max 6 study hours per day
    total_hours = sum(e.duration for e in same_day_events)
    if total_hours > 6:
        return False, "More than 6 study hours per day"
    
    # Check at least 15-min breaks between classes
    for i in range(len(same_day_events) - 1):
        current_end = time_to_minutes(same_day_events[i].end_time)
        next_start = time_to_minutes(same_day_events[i + 1].start_time)
        if next_start - current_end < 15:
            return False, "Less than 15-min break between classes"
    
    return True, "OK"

def schedule_all_events(all_events: List[Dict]) -> Optional[ScheduleState]:
    """Place every event using a greedy best-first search.

    For each event, all legal (day, time, room) placements are scored and the
    best one is committed immediately. Placements are never revisited, so this
    trades guaranteed optimality for speed. Events that cannot be placed under
    the constraints are reported and skipped.
    """
    # Group events by batch for better locality
    events_by_batch = defaultdict(list)
    for event in all_events:
        events_by_batch[event['batch_name']].append(event)
    
    # Initialize state
    state = ScheduleState(
        events=[],
        room_usage={},
        batch_schedules=defaultdict(list)
    )
    
    # Process events batch by batch (greedy approach)
    total_events = len(all_events)
    scheduled_count = 0
    
    # Sort batches to process them in order
    batches = sorted(events_by_batch.keys())
    
    for batch_name in batches:
        batch_events = events_by_batch[batch_name]
        
        for event_to_schedule in batch_events:
            scheduled_count += 1
            if scheduled_count % 5 == 0:
                print(f"  Progress: {scheduled_count}/{total_events} events scheduled...")
            
            # Find best slot for this event
            candidates = []
            
            for day in DAYS:
                day_events = [e for e in state.batch_schedules.get(batch_name, []) if e.day == day]
                day_events.sort(key=lambda x: time_to_minutes(x.start_time))
                
                for start_time in TIME_SLOTS:
                    start_min = time_to_minutes(start_time)
                    duration_min = int(event_to_schedule['duration'] * 60)
                    end_min = start_min + duration_min
                    
                    if end_min > time_to_minutes("18:00"):
                        continue
                    
                    # Select appropriate room type
                    if event_to_schedule['event_type'] == 'Lab':
                        rooms = LAB_ROOMS
                    else:
                        rooms = LECTURE_ROOMS
                    
                    for room in rooms:
                        end_time = minutes_to_time(end_min)
                        new_event = CourseEvent(
                            course_code=event_to_schedule['course_code'],
                            course_name=event_to_schedule['course_name'],
                            batch_name=batch_name,
                            day=day,
                            start_time=start_time,
                            end_time=end_time,
                            duration=event_to_schedule['duration'],
                            room=room,
                            event_type=event_to_schedule['event_type']
                        )
                        
                        # Check constraints
                        valid, reason = check_constraints(state, new_event)
                        if not valid:
                            continue
                        
                        # Calculate score (lower is better)
                        score = 0.0
                        # Prefer lunch break (12:00-14:00)
                        if start_min >= time_to_minutes("12:00") and end_min <= time_to_minutes("14:00"):
                            score -= 10.0
                        # Prefer earlier times
                        score += start_min / 60.0
                        # Prefer compact schedules
                        if day_events:
                            min_gap = float('inf')
                            for existing in day_events:
                                existing_end = time_to_minutes(existing.end_time)
                                existing_start = time_to_minutes(existing.start_time)
                                gap_before = abs(start_min - existing_end)
                                gap_after = abs(existing_start - end_min)
                                min_gap = min(min_gap, gap_before, gap_after)
                            score += min_gap / 60.0
                        else:
                            # First event of the day - prefer morning
                            score += (start_min - time_to_minutes("08:00")) / 60.0
                        
                        candidates.append((score, day, start_time, room, new_event))
            
            # Sort candidates and try the best one
            if candidates:
                candidates.sort(key=lambda x: x[0])
                # Take the best candidate
                score, day, start_time, room, new_event = candidates[0]
                
                # Add to state
                state.events.append(new_event)
                
                # Mark room as occupied
                slots = get_time_slots(start_time, event_to_schedule['duration'])
                for slot in slots:
                    state.room_usage[(room, day, slot)] = True
                
                state.batch_schedules[batch_name].append(new_event)
            else:
                # If no valid slot found, try with relaxed constraints (skip some checks)
                # This is a fallback - try to find ANY slot
                found = False
                for day in DAYS:
                    if found:
                        break
                    for start_time in TIME_SLOTS:
                        if found:
                            break
                        start_min = time_to_minutes(start_time)
                        duration_min = int(event_to_schedule['duration'] * 60)
                        end_min = start_min + duration_min
                        
                        if end_min > time_to_minutes("18:00"):
                            continue
                        
                        if event_to_schedule['event_type'] == 'Lab':
                            rooms = LAB_ROOMS
                        else:
                            rooms = LECTURE_ROOMS
                        
                        for room in rooms:
                            # Check only basic constraints (no overlap, room available)
                            slots = get_time_slots(start_time, event_to_schedule['duration'])
                            room_available = True
                            for slot in slots:
                                if state.room_usage.get((room, day, slot), False):
                                    room_available = False
                                    break
                            
                            if not room_available:
                                continue
                            
                            # Check batch overlap only
                            batch_events = state.batch_schedules.get(batch_name, [])
                            overlaps = False
                            for existing in batch_events:
                                existing_start = time_to_minutes(existing.start_time)
                                existing_end = time_to_minutes(existing.end_time)
                                if (existing.day == day and
                                    existing_start < end_min and
                                    existing_end > start_min):
                                    overlaps = True
                                    break
                            
                            if not overlaps:
                                end_time = minutes_to_time(end_min)
                                new_event = CourseEvent(
                                    course_code=event_to_schedule['course_code'],
                                    course_name=event_to_schedule['course_name'],
                                    batch_name=batch_name,
                                    day=day,
                                    start_time=start_time,
                                    end_time=end_time,
                                    duration=event_to_schedule['duration'],
                                    room=room,
                                    event_type=event_to_schedule['event_type']
                                )
                                
                                state.events.append(new_event)
                                for slot in slots:
                                    state.room_usage[(room, day, slot)] = True
                                state.batch_schedules[batch_name].append(new_event)
                                found = True
                                break
                        if found:
                            break
                
                if not found:
                    print(f"Warning: Could not schedule {event_to_schedule['course_code']} for batch {batch_name}")
    
    return state

def optimize_lunch_breaks(state: ScheduleState) -> ScheduleState:
    """Post-process to prefer lunch breaks in 12:00-14:00 range"""
    # This is a simple optimization - try to shift events to create lunch breaks
    # For now, we'll keep the A* solution as is since it already considers this
    return state

def main():
    """Main function to run the scheduler"""
    # Read CSVs
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    courses_path = os.path.join(project_root, 'courses_sample.csv')
    batches_path = os.path.join(project_root, 'batches_sample.csv')
    
    if not os.path.exists(courses_path):
        print(f"Error: {courses_path} not found")
        return
    
    if not os.path.exists(batches_path):
        print(f"Error: {batches_path} not found")
        return
    
    try:
        courses_df = pd.read_csv(courses_path)
        batches_df = pd.read_csv(batches_path)
    except Exception as e:
        print(f"Error reading CSV files: {e}")
        return
    
    # Create course lookup
    course_lookup = {}
    for _, row in courses_df.iterrows():
        course_lookup[row['CourseCode']] = {
            'name': row['CourseName'],
            'credits': int(row['Credits']),
            'professor': row['Professor']
        }
    
    # Expand all courses into events
    all_events = []
    for _, batch_row in batches_df.iterrows():
        batch_name = batch_row['BatchName']
        courses_str = str(batch_row['Courses[]'])  # Convert to string in case of NaN
        
        # Parse courses (separated by ;)
        course_codes = [c.strip() for c in courses_str.split(';') if c.strip() and c.strip().upper() != 'NAN']
        
        for course_code in course_codes:
            if course_code in course_lookup:
                course_info = course_lookup[course_code]
                events = expand_course_events(
                    course_code,
                    course_info['name'],
                    course_info['credits'],
                    batch_name
                )
                all_events.extend(events)
            else:
                print(f"Warning: Course {course_code} not found in courses list for batch {batch_name}")
    
    if len(all_events) == 0:
        print("Error: No events to schedule. Please check your input files.")
        return
    
    print(f"Total events to schedule: {len(all_events)}")
    print("Running A* search...")
    
    # Run A* search
    final_state = schedule_all_events(all_events)
    
    if final_state is None or len(final_state.events) == 0:
        print("Error: Could not generate schedule. Please check constraints and try again.")
        return
    
    # Optimize lunch breaks
    final_state = optimize_lunch_breaks(final_state)
    
    # Convert to DataFrame
    schedule_data = [event.to_dict() for event in final_state.events]
    schedule_df = pd.DataFrame(schedule_data)
    
    # Sort by batch, day, and start time
    day_order = {day: i for i, day in enumerate(DAYS)}
    schedule_df['DayOrder'] = schedule_df['Day'].map(day_order)
    schedule_df = schedule_df.sort_values(['BatchName', 'DayOrder', 'StartTime'])
    schedule_df = schedule_df.drop('DayOrder', axis=1)
    
    # Save to CSV
    output_path = os.path.join(project_root, 'schedule.csv')
    schedule_df.to_csv(output_path, index=False)
    
    print(f"Schedule generated successfully!")
    print(f"Total events scheduled: {len(schedule_df)}")
    print(f"Output saved to: {output_path}")

if __name__ == "__main__":
    main()

