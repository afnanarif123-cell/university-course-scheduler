"""
Repeat Course Finder
Helps students find compatible batches for repeating courses
"""

import pandas as pd
import os
from typing import List, Dict, Tuple

def time_to_minutes(time_str: str) -> int:
    """Convert time string (HH:MM) to minutes since midnight"""
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])

def events_overlap(event1: Dict, event2: Dict) -> bool:
    """Check if two events overlap in time"""
    if event1['Day'] != event2['Day']:
        return False
    
    start1 = time_to_minutes(event1['StartTime'])
    end1 = time_to_minutes(event1['EndTime'])
    start2 = time_to_minutes(event2['StartTime'])
    end2 = time_to_minutes(event2['EndTime'])
    
    return start1 < end2 and start2 < end1

def find_compatible_batches(schedule_df: pd.DataFrame, 
                           user_batch: str, 
                           course_code: str) -> List[Dict]:
    """
    Find batches that offer the same course without schedule conflicts
    
    Args:
        schedule_df: DataFrame with schedule data
        user_batch: Name of the user's batch
        course_code: Course code to repeat
    
    Returns:
        List of compatible batch suggestions with details
    """
    # Get user's current schedule (excluding the course to repeat)
    user_schedule = schedule_df[
        (schedule_df['BatchName'] == user_batch) & 
        (schedule_df['CourseCode'] != course_code)
    ].copy()
    
    # Get all batches that offer this course
    course_batches = schedule_df[
        schedule_df['CourseCode'] == course_code
    ]['BatchName'].unique()
    
    # Remove user's own batch
    course_batches = [b for b in course_batches if b != user_batch]
    
    compatible_batches = []
    
    for batch_name in course_batches:
        # Get the course schedule in this batch
        batch_course_schedule = schedule_df[
            (schedule_df['BatchName'] == batch_name) &
            (schedule_df['CourseCode'] == course_code)
        ].copy()
        
        if batch_course_schedule.empty:
            continue
        
        # Check for overlaps with user's schedule
        has_overlap = False
        for _, user_event in user_schedule.iterrows():
            for _, batch_event in batch_course_schedule.iterrows():
                if events_overlap(user_event.to_dict(), batch_event.to_dict()):
                    has_overlap = True
                    break
            if has_overlap:
                break
        
        if not has_overlap:
            # This batch is compatible
            # Get additional info about the batch
            batch_info = {
                'BatchName': batch_name,
                'CourseCode': course_code,
                'CourseName': batch_course_schedule.iloc[0]['CourseName'],
                'Compatible': True,
                'ScheduleDetails': []
            }
            
            # Add schedule details
            for _, event in batch_course_schedule.iterrows():
                batch_info['ScheduleDetails'].append({
                    'Day': event['Day'],
                    'StartTime': event['StartTime'],
                    'EndTime': event['EndTime'],
                    'Room': event['Room'],
                    'Type': event['Type']
                })
            
            compatible_batches.append(batch_info)
    
    return compatible_batches

def main():
    """Main function for repeat finder"""
    # Read schedule.csv
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    schedule_path = os.path.join(project_root, 'schedule.csv')
    
    if not os.path.exists(schedule_path):
        print(f"Error: schedule.csv not found at {schedule_path}")
        print("Please run scheduler.py first to generate the schedule.")
        return
    
    schedule_df = pd.read_csv(schedule_path)
    
    # Get user input
    print("=" * 60)
    print("Repeat Course Finder")
    print("=" * 60)
    
    # Show available batches
    available_batches = sorted(schedule_df['BatchName'].unique())
    print("\nAvailable batches:")
    for i, batch in enumerate(available_batches, 1):
        print(f"  {i}. {batch}")
    
    # Get user batch
    while True:
        try:
            batch_input = input("\nEnter your batch name: ").strip()
            if batch_input in available_batches:
                user_batch = batch_input
                break
            else:
                print(f"Invalid batch name. Please choose from: {', '.join(available_batches)}")
        except KeyboardInterrupt:
            print("\nCancelled.")
            return
    
    # Show available courses in user's batch
    user_courses = schedule_df[schedule_df['BatchName'] == user_batch]['CourseCode'].unique()
    
    if len(user_courses) == 0:
        print(f"\nNo courses found for batch {user_batch}.")
        return
    
    print(f"\nCourses in {user_batch}:")
    for i, course in enumerate(sorted(user_courses), 1):
        course_rows = schedule_df[
            (schedule_df['BatchName'] == user_batch) & 
            (schedule_df['CourseCode'] == course)
        ]
        if not course_rows.empty:
            course_name = course_rows.iloc[0]['CourseName']
            print(f"  {i}. {course} - {course_name}")
        else:
            print(f"  {i}. {course}")
    
    # Get course to repeat
    while True:
        try:
            course_input = input("\nEnter course code to repeat: ").strip().upper()
            if course_input in user_courses:
                course_code = course_input
                break
            else:
                print(f"Invalid course code. Please choose from: {', '.join(sorted(user_courses))}")
        except KeyboardInterrupt:
            print("\nCancelled.")
            return
    
    # Find compatible batches
    print(f"\nSearching for compatible batches for {course_code}...")
    compatible = find_compatible_batches(schedule_df, user_batch, course_code)
    
    if not compatible:
        print(f"\nNo compatible batches found for {course_code}.")
        print("All batches offering this course have schedule conflicts with your current schedule.")
    else:
        print(f"\nFound {len(compatible)} compatible batch(es):")
        print("-" * 60)
        
        results = []
        for i, batch_info in enumerate(compatible, 1):
            print(f"\n{i}. Batch: {batch_info['BatchName']}")
            print(f"   Course: {batch_info['CourseCode']} - {batch_info['CourseName']}")
            print("   Schedule:")
            for detail in batch_info['ScheduleDetails']:
                print(f"     - {detail['Day']}: {detail['StartTime']} - {detail['EndTime']} "
                      f"({detail['Type']}) in {detail['Room']}")
            
            # Prepare result row
            for detail in batch_info['ScheduleDetails']:
                results.append({
                    'UserBatch': user_batch,
                    'CourseCode': batch_info['CourseCode'],
                    'CourseName': batch_info['CourseName'],
                    'CompatibleBatch': batch_info['BatchName'],
                    'Day': detail['Day'],
                    'StartTime': detail['StartTime'],
                    'EndTime': detail['EndTime'],
                    'Room': detail['Room'],
                    'Type': detail['Type'],
                    'Compatible': 'Yes'
                })
        
        # Save to CSV
        if results:
            results_df = pd.DataFrame(results)
            output_path = os.path.join(project_root, 'repeat_suggestions.csv')
            results_df.to_csv(output_path, index=False)
            print(f"\n✓ Results saved to: {output_path}")

if __name__ == "__main__":
    main()

