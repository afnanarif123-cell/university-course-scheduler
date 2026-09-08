# University Course Scheduler

An automatic timetable generator for university course batches. It takes a list of
courses and the batches enrolled in them, then uses a greedy best-first search to
place every class into a weekly schedule without room clashes, batch clashes, or
unreasonable student workloads. A Streamlit web interface renders the result as
an interactive timetable.

The scheduler also answers a practical follow-up question: if a student has to
repeat a course, which other batch can they attend it with, without breaking the
rest of their timetable?

## Features

- **Constraint-based scheduling** — a greedy best-first search over time slots and
  rooms that respects hard constraints and minimises idle gaps between classes.
- **Credit-aware class expansion** — each course becomes the right number of
  weekly sessions based on its credit value.
- **Repeat course finder** — given a student's batch and the course they need to
  retake, lists the batches whose sessions fit their existing schedule.
- **Interactive timetable** — a colour-coded weekly grid, filterable by batch and
  by course.
- **Import and export** — load an external schedule CSV for viewing, or export
  the generated one (whole schedule or a single batch).

## Requirements

- Python 3.11 or newer
- streamlit, pandas, numpy (see `requirements.txt`)

## Setup

```bash
git clone <your-repo-url>
cd Scheduler

python -m venv .venv
```

Activate the environment:

```bash
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Then install the dependencies:

```bash
pip install -r requirements.txt
```

## Running

Start the web interface:

```bash
streamlit run gui.py
```

Then open <http://localhost:8501>. The app generates `schedule.csv` automatically
on first launch if it does not already exist, and the **Settings** page has a
button to regenerate it on demand.

To run the scheduler on its own, without the interface:

```bash
python modules/scheduler.py
```

This reads `courses_sample.csv` and `batches_sample.csv` and writes `schedule.csv`.

## Input format

**`courses_sample.csv`** — the course catalogue:

```csv
CourseCode,CourseName,Credits,Professor
CS101,Introduction to Computer Science,3,Dr. Smith
CS102,Data Structures,4,Dr. Johnson
```

**`batches_sample.csv`** — the batches and what each one is taking. Course codes
are separated by semicolons; empty slots may be left as `NaN`.

```csv
BatchName,Semester,Courses[]
CS-A-2024,1,CS101;MATH201;ENG101;PHYS101;STAT201;PHIL101;NaN;NaN
```

## Output format

**`schedule.csv`** — one row per scheduled class session:

```csv
BatchName,CourseCode,CourseName,Day,StartTime,EndTime,Duration,Room,Type
BIO-A-2024,MATH201,Calculus I,Monday,08:00,09:30,1.5,G01,Lecture
```

## How scheduling works

Courses are first expanded into weekly sessions according to their credits:

| Credits | Weekly sessions                             |
| ------- | ------------------------------------------- |
| 2       | One 2-hour lecture                          |
| 3       | Two 1.5-hour lectures                       |
| 4       | Two 1.5-hour lectures plus one 3-hour lab   |

Those sessions are then placed by a greedy best-first search across
Monday–Friday, 08:00–18:00, in 30-minute increments. Lectures go into general
rooms and labs into computer labs (`CL01`–`CL12`). A placement is only accepted
if it satisfies every hard constraint:

- No batch has two classes overlapping.
- No room hosts two classes at once.
- At most 3 consecutive 1.5-hour classes, or 2 consecutive 2-hour classes.
- At most one lab per batch per day.
- At most 6 hours of class per batch per day.
- At least a 15-minute break between consecutive classes.

Among the placements that qualify, each one is scored and the best is chosen:
slots close to the batch's existing classes score better, so days stay compact
rather than scattered around long gaps; earlier start times are preferred; and
the 12:00–14:00 window gets a bonus so lunch hours are used.

The search is greedy — each session is committed as it is placed and earlier
choices are never revisited. This trades guaranteed optimality for speed, which
is why a full 1,000-session timetable generates in seconds.

## Project structure

```
Scheduler/
├── gui.py                    # Streamlit interface
├── modules/
│   ├── scheduler.py          # Scheduling engine (greedy best-first search)
│   └── repeat_finder.py      # Compatible-batch finder for repeat students
├── courses_sample.csv        # Input: course catalogue
├── batches_sample.csv        # Input: batches and enrolments
├── schedule.csv              # Output: generated timetable
├── requirements.txt
└── LICENSE
```

## Notes

If a batch is enrolled in more courses than can fit within the constraints, the
scheduler prints a warning naming each session it could not place and continues
with the rest, rather than failing outright. In the bundled sample data this
happens for `PHYS-C-2024`, which is deliberately over-subscribed.

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.
