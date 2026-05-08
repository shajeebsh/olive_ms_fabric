# Source-to-Target Mapping

This document defines the transformation contract from raw source fields to Silver and Gold models. Keep this file aligned with the notebooks.

## Training Enrolments

| Source column | Source type | Silver column | Target type | Rule | Nullable |
| --- | --- | --- | --- | --- | --- |
| `StudentID` | string | `student_id` | string | Trim and uppercase | No |
| `CourseCode` | string | `course_id` | string | Trim and uppercase | No |
| `EnrolDate` | string | `enrolment_date` | date | Parse as `dd/MM/yyyy` | No |
| `CompletionDate` | string | `completion_date` | date | Parse as `dd/MM/yyyy`, blank to null | Yes |
| `Score` | string | `score_pct` | decimal(5,2) | Cast to decimal, valid range 0-100 | Yes |
| `Status` | string | `enrolment_status` | string | Map `C`, `A`, `D` to Completed, Active, Dropped | No |
| Derived | n/a | `is_completed` | boolean | `enrolment_status = 'Completed'` | No |
| System | n/a | `_silver_created` | timestamp | Current timestamp | No |

## Staff

| Source column | Silver column | Rule |
| --- | --- | --- |
| `StaffID` | `staff_id` | Trim and uppercase |
| `FirstName` | `first_name` | Trim and title-case where appropriate |
| `LastName` | `last_name` | Trim and title-case where appropriate |
| `Department` | `department` | Map to approved department reference list |
| `Role` | `role` | Map to approved role reference list |
| `Email` | `email` | Lowercase and validate email format |
| `ContractedHours` | `monthly_contracted_hours` | Cast to decimal |

## Clinical Hours

| Source column | Silver column | Rule |
| --- | --- | --- |
| `StaffID` | `staff_id` | Validate against staff entity |
| `ProcedureCode` | `procedure_id` | Trim and uppercase |
| `ProcedureDate` | `procedure_date` | Parse date, reject future dates |
| `HoursLogged` | `hours_logged` | Cast to decimal, must be >= 0 |
| `Location` | `campus_id` | Map to campus reference list |

## Silver Audit Columns

All Silver entities should include:

| Column | Purpose |
| --- | --- |
| `valid_from` | Version start timestamp |
| `valid_to` | Version end timestamp, null for current |
| `is_current` | Current record flag |
| `row_hash` | Hash of business attributes |
| `_silver_created` | Insert timestamp |
| `_silver_updated` | Update timestamp |
| `_source_system` | Source lineage |

## Gold Mapping

| Silver entity | Gold output |
| --- | --- |
| `silver_students` | `dim_student` |
| `silver_staff` | `dim_staff` |
| `silver_courses` | `dim_course` |
| `silver_training_enrolments` | `fact_training_completion`, `fact_enrolment` |
| `silver_clinical_hours` | `fact_clinical_hours` |
| `silver_room_bookings` | `fact_room_booking` |

