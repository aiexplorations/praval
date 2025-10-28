"""
Student Analytics Multi-Agent System

This example demonstrates a practical multi-agent system for analyzing student performance data.
A team of specialized agents self-organizes to answer questions about student test scores.

Praval Architecture (No Central Coordinator!):
Agents respond to message types and broadcast their results. The system self-organizes:

- Schema Agent: Responds to user queries, provides database context
- Query Builder Agent: Responds to schema info, translates questions to SQL
- Data Executor Agent: Responds to queries, runs them and retrieves data
- Analyst Agent: Responds to data, interprets results and finds patterns
- Report Agent: Responds to insights, formats them for the user

Each agent only does ONE thing and broadcasts its results for others to use.

Database Schema:
- students: id, name, grade, section
- scores: id, student_id, subject, score, test_date
"""

import sqlite3
import random
from datetime import datetime, timedelta
from praval import agent, start_agents, broadcast

# ============================================================================
# DATABASE SETUP
# ============================================================================

def create_and_populate_database(db_path="students.db"):
    """Create SQLite database with student performance data."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            grade INTEGER NOT NULL,
            section TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            score INTEGER NOT NULL,
            test_date TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # Clear existing data
    cursor.execute("DELETE FROM scores")
    cursor.execute("DELETE FROM students")

    # Generate student data
    print("📊 Generating student data...")

    first_names = [
        "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Arnav", "Ayaan",
        "Krishna", "Ishaan", "Aadhya", "Ananya", "Pari", "Anika", "Diya",
        "Ishita", "Navya", "Saanvi", "Sara", "Priya", "Riya", "Kiara", "Avni",
        "Kavya", "Zara", "Myra", "Aditi", "Tanvi", "Shreya", "Ira"
    ]

    last_names = [
        "Sharma", "Verma", "Kumar", "Singh", "Patel", "Gupta", "Reddy", "Rao",
        "Iyer", "Nair", "Menon", "Joshi", "Desai", "Pandey", "Mishra", "Das"
    ]

    grades = [6, 7, 8, 9, 10]
    sections = ["A", "B", "C", "D"]
    subjects = ["Mathematics", "Science", "English", "Hindi", "Social Studies"]

    student_id = 1
    students_data = []

    for grade in grades:
        for section in sections:
            # 15-20 students per section
            num_students = random.randint(15, 20)
            for _ in range(num_students):
                name = f"{random.choice(first_names)} {random.choice(last_names)}"
                students_data.append((student_id, name, grade, section))
                student_id += 1

    cursor.executemany(
        "INSERT INTO students (id, name, grade, section) VALUES (?, ?, ?, ?)",
        students_data
    )

    print(f"✅ Created {len(students_data)} students")

    # Generate test scores
    print("📝 Generating test scores...")

    scores_data = []
    base_date = datetime.now() - timedelta(days=90)

    for student_id, _, grade, _ in students_data:
        # Each student has scores for all subjects
        for subject in subjects:
            # Grade-appropriate scoring (higher grades tend to score higher)
            base_score = 50 + (grade - 6) * 5

            # Add subject-specific variance
            if subject == "Mathematics":
                score = base_score + random.randint(-15, 20)
            elif subject == "Science":
                score = base_score + random.randint(-10, 20)
            else:
                score = base_score + random.randint(-10, 15)

            # Clamp between 0-100
            score = max(0, min(100, score))

            test_date = (base_date + timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d")
            scores_data.append((student_id, subject, score, test_date))

    cursor.executemany(
        "INSERT INTO scores (student_id, subject, score, test_date) VALUES (?, ?, ?, ?)",
        scores_data
    )

    conn.commit()
    print(f"✅ Created {len(scores_data)} test scores")
    print(f"💾 Database saved to: {db_path}\n")

    conn.close()
    return db_path


# ============================================================================
# DATABASE SCHEMA CONSTANT
# ============================================================================

DATABASE_SCHEMA = """
Database Schema:

Table: students
- id (INTEGER, PRIMARY KEY): Unique student identifier
- name (TEXT): Student's full name
- grade (INTEGER): Grade level (6-10)
- section (TEXT): Section (A, B, C, D)

Table: scores
- id (INTEGER, PRIMARY KEY): Unique score record
- student_id (INTEGER): References students(id)
- subject (TEXT): Subject name (Mathematics, Science, English, Hindi, Social Studies)
- score (INTEGER): Test score (0-100)
- test_date (TEXT): Date of test (YYYY-MM-DD)

Relationships:
- scores.student_id → students.id (one-to-many)
"""


# ============================================================================
# MULTI-AGENT SYSTEM
# ============================================================================

@agent("schema_expert", channel="analytics", responds_to=["user_query"])
def schema_agent(spore):
    """
    I am the database schema expert. I understand the structure of the database
    and respond when someone asks a question by providing schema context.
    """
    question = spore.knowledge.get("question")
    db_path = spore.knowledge.get("db_path")

    print(f"📚 Schema Expert: Analyzing question: '{question}'")
    print(f"📚 Schema Expert: Database has students (id, name, grade, section)")
    print(f"📚 Schema Expert: and scores (student_id, subject, score, test_date)\n")

    # Broadcast schema info for query builder to use
    broadcast({
        "type": "build_query",
        "question": question,
        "schema": DATABASE_SCHEMA,
        "db_path": db_path
    }, channel="analytics")

    return {"schema": DATABASE_SCHEMA}


@agent("query_builder", channel="analytics", responds_to=["build_query"])
def query_builder_agent(spore):
    """
    I translate natural language questions into SQL queries.
    I understand the database schema and can construct appropriate queries.
    """
    question = spore.knowledge.get("question").lower()
    schema = spore.knowledge.get("schema")
    db_path = spore.knowledge.get("db_path")

    print(f"🔨 Query Builder: Translating question to SQL...")

    # Simple pattern matching for common queries
    # In production, this would use an LLM

    if "average" in question and "grade" in question:
        if "mathematics" in question or "math" in question:
            query = """
                SELECT s.grade, AVG(sc.score) as avg_score
                FROM students s
                JOIN scores sc ON s.id = sc.student_id
                WHERE sc.subject = 'Mathematics'
                GROUP BY s.grade
                ORDER BY s.grade
            """
            query_type = "grade_average_math"
        else:
            query = """
                SELECT s.grade, sc.subject, AVG(sc.score) as avg_score
                FROM students s
                JOIN scores sc ON s.id = sc.student_id
                GROUP BY s.grade, sc.subject
                ORDER BY s.grade, sc.subject
            """
            query_type = "grade_average_all"

    elif "top" in question and "students" in question:
        limit = 10
        if "5" in question:
            limit = 5
        elif "20" in question:
            limit = 20

        query = f"""
            SELECT s.name, s.grade, s.section, AVG(sc.score) as avg_score
            FROM students s
            JOIN scores sc ON s.id = sc.student_id
            GROUP BY s.id
            ORDER BY avg_score DESC
            LIMIT {limit}
        """
        query_type = "top_students"

    elif "section" in question and "performance" in question:
        query = """
            SELECT s.grade, s.section, AVG(sc.score) as avg_score, COUNT(DISTINCT s.id) as student_count
            FROM students s
            JOIN scores sc ON s.id = sc.student_id
            GROUP BY s.grade, s.section
            ORDER BY s.grade, s.section
        """
        query_type = "section_performance"

    elif "subject" in question and "performance" in question:
        query = """
            SELECT sc.subject, AVG(sc.score) as avg_score,
                   MIN(sc.score) as min_score, MAX(sc.score) as max_score,
                   COUNT(*) as test_count
            FROM scores sc
            GROUP BY sc.subject
            ORDER BY avg_score DESC
        """
        query_type = "subject_performance"

    else:
        # Default: overall statistics
        query = """
            SELECT
                COUNT(DISTINCT s.id) as total_students,
                COUNT(DISTINCT sc.subject) as total_subjects,
                AVG(sc.score) as overall_avg,
                MIN(sc.score) as lowest_score,
                MAX(sc.score) as highest_score
            FROM students s
            JOIN scores sc ON s.id = sc.student_id
        """
        query_type = "overall_stats"

    print(f"🔨 Query Builder: Generated SQL query")
    print(f"🔨 Query Builder: Query type: {query_type}\n")

    broadcast({
        "type": "execute_query",
        "query": query,
        "query_type": query_type,
        "question": spore.knowledge.get("question"),
        "db_path": db_path
    }, channel="analytics")

    return {"query": query}


@agent("data_executor", channel="analytics", responds_to=["execute_query"])
def executor_agent(spore):
    """
    I execute SQL queries against the database and return the results.
    I ensure safe query execution and proper error handling.
    """
    query = spore.knowledge.get("query")
    db_path = spore.knowledge.get("db_path")
    query_type = spore.knowledge.get("query_type")
    question = spore.knowledge.get("question")

    print(f"⚙️ Data Executor: Executing query...")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        conn.close()

        print(f"⚙️ Data Executor: Retrieved {len(results)} rows\n")

        broadcast({
            "type": "analyze_results",
            "results": results,
            "columns": columns,
            "query_type": query_type,
            "question": question
        }, channel="analytics")

        return {"results": results, "columns": columns}

    except Exception as e:
        print(f"❌ Data Executor: Error executing query: {e}\n")
        return {"error": str(e)}


@agent("analyst", channel="analytics", responds_to=["analyze_results"])
def analyst_agent(spore):
    """
    I analyze query results to find patterns, insights, and key findings.
    I provide statistical interpretation and identify notable trends.
    """
    results = spore.knowledge.get("results")
    columns = spore.knowledge.get("columns")
    query_type = spore.knowledge.get("query_type")
    question = spore.knowledge.get("question")

    print(f"📊 Analyst: Analyzing results...")

    insights = []

    if query_type == "grade_average_math":
        for row in results:
            grade, avg_score = row
            insights.append(f"Grade {grade}: Average Math score is {avg_score:.1f}")
            if avg_score < 60:
                insights.append(f"  ⚠️ Grade {grade} needs improvement in Mathematics")
            elif avg_score > 80:
                insights.append(f"  ✨ Grade {grade} shows strong performance in Mathematics")

    elif query_type == "top_students":
        insights.append(f"Top {len(results)} performing students:")
        for i, row in enumerate(results[:5], 1):
            name, grade, section, avg_score = row
            insights.append(f"  {i}. {name} (Grade {grade}-{section}): {avg_score:.1f}%")

    elif query_type == "section_performance":
        # Find best and worst performing sections
        sorted_results = sorted(results, key=lambda x: x[2], reverse=True)
        if sorted_results:
            best = sorted_results[0]
            worst = sorted_results[-1]
            insights.append(f"Best performing: Grade {best[0]}-{best[1]} with {best[2]:.1f}% average")
            insights.append(f"Needs attention: Grade {worst[0]}-{worst[1]} with {worst[2]:.1f}% average")

    elif query_type == "subject_performance":
        insights.append("Subject-wise performance:")
        for row in results:
            subject, avg, min_score, max_score, count = row
            insights.append(f"  {subject}: Avg={avg:.1f}, Range={min_score}-{max_score}")

    elif query_type == "overall_stats":
        row = results[0]
        total_students, total_subjects, overall_avg, lowest, highest = row
        insights.append(f"Total Students: {total_students}")
        insights.append(f"Subjects: {total_subjects}")
        insights.append(f"Overall Average: {overall_avg:.1f}%")
        insights.append(f"Score Range: {lowest}-{highest}")

    print(f"📊 Analyst: Found {len(insights)} key insights\n")

    broadcast({
        "type": "generate_report",
        "results": results,
        "columns": columns,
        "insights": insights,
        "question": question
    }, channel="analytics")

    return {"insights": insights}


@agent("reporter", channel="analytics", responds_to=["generate_report"])
def report_agent(spore):
    """
    I format the analysis into a clear, readable report for the user.
    I present data and insights in an easy-to-understand format.
    """
    results = spore.knowledge.get("results")
    columns = spore.knowledge.get("columns")
    insights = spore.knowledge.get("insights")
    question = spore.knowledge.get("question")

    print(f"📝 Reporter: Generating final report...\n")
    print("=" * 70)
    print(f"STUDENT ANALYTICS REPORT")
    print("=" * 70)
    print(f"\nQuestion: {question}\n")

    print("KEY FINDINGS:")
    print("-" * 70)
    for insight in insights:
        print(insight)

    print("\n" + "=" * 70)
    print("Analysis complete! ✅\n")

    return {"report": "\n".join(insights)}


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Run the student analytics multi-agent system."""

    print("=" * 70)
    print("STUDENT ANALYTICS MULTI-AGENT SYSTEM")
    print("=" * 70)
    print()

    # Create and populate database
    db_path = create_and_populate_database()

    # Example questions
    questions = [
        "What is the average score by grade for mathematics?",
        "Show me the top 10 students by overall performance",
        "What is the performance of each section?",
        "How do different subjects compare in performance?",
    ]

    print("=" * 70)
    print("RUNNING ANALYTICS QUERIES")
    print("=" * 70)
    print()

    # Process each question
    for i, question in enumerate(questions, 1):
        print(f"\n{'='*70}")
        print(f"QUERY {i}/{len(questions)}")
        print(f"{'='*70}\n")

        start_agents(
            schema_agent,
            query_builder_agent,
            executor_agent,
            analyst_agent,
            report_agent,
            initial_data={
                "type": "user_query",
                "question": question,
                "db_path": db_path
            }
        )

        import time
        time.sleep(0.5)  # Allow agents to complete

    print("\n" + "=" * 70)
    print("ALL ANALYSES COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
