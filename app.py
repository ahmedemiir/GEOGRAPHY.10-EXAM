import io
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
import pandas as pd

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///exam_portal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'geography-secret-key-2026'

db = SQLAlchemy(app)
ADMIN_KEY = "admin123"

# Master Answer Key (Server-side grading)
ANSWER_KEY = {
    "q1": "C", "q2": "B", "q3": "C", "q4": "B", "q5": "A", 
    "q6": "D", "q7": "B", "q8": "C", "q9": "B", "q10": "C",
}

# Database Model
class ExamSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    student_id = db.Column(db.String(50), nullable=False)
    section = db.Column(db.String(10), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    violations = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize DB Tables
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('exam.html', access_code='EXAM2026')

@app.route('/submit-exam', methods=['POST'])
def submit_exam():
    try:
        data = request.get_json()
        student_answers = data.get('answers', {})
        student_id = data.get('id', '').strip()
        
        # Prevent Duplicate Submissions
        existing = ExamSubmission.query.filter_by(student_id=student_id).first()
        if existing:
            return jsonify({"status": "error", "message": "Exam already submitted for this ID."}), 400
        
        # Backend Score Calculation
        score = sum(1 for q, ans in ANSWER_KEY.items() if student_answers.get(q) == ans)
        total_q = len(ANSWER_KEY)
        percentage = round((score / total_q) * 100, 2)

        # Save to Database
        submission = ExamSubmission(
            student_name=data.get('name'),
            student_id=student_id,
            section=data.get('section'),
            score=score,
            total_questions=total_q,
            percentage=percentage,
            violations=data.get('violations', 0)
        )
        db.session.add(submission)
        db.session.commit()

        return jsonify({
            "status": "success",
            "score": score,
            "total": total_q,
            "percentage": percentage
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/export-excel')
def export_excel():
    key = request.args.get('key')
    if key != ADMIN_KEY:
        return "Unauthorized Access", 403

    submissions = ExamSubmission.query.order_by(ExamSubmission.submitted_at.desc()).all()

    # Format data for Excel download
    data = [{
        "Student ID": sub.student_id,
        "Full Name": sub.student_name,
        "Section": sub.section,
        "Score": f"{sub.score}/{sub.total_questions}",
        "Percentage": f"{sub.percentage}%",
        "Violations": sub.violations,
        "Submission Time": sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if sub.submitted_at else "N/A"
    } for sub in submissions]

    df = pd.DataFrame(data)
    
    # Save to memory buffer
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Geography_Results')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Geography_Exam_Results.xlsx'
    )

@app.route('/admin-results')
def admin_results():
    key = request.args.get('key')
    if key != ADMIN_KEY:
        return "Unauthorized Access", 403

    submissions = ExamSubmission.query.order_by(ExamSubmission.submitted_at.desc()).all()
    
    rows = ""
    for sub in submissions:
        rows += f"""
        <tr>
            <td>{sub.student_id}</td>
            <td>{sub.student_name}</td>
            <td>{sub.section}</td>
            <td>{sub.score}/{sub.total_questions}</td>
            <td>{sub.percentage}%</td>
            <td>{sub.violations}</td>
            <td>{sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S')}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Exam Submissions Dashboard</title>
        <style>
            body {{ font-family: system-ui, sans-serif; padding: 30px; background: #f8fafc; }}
            .container {{ max-width: 1100px; margin: auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
            .btn-excel {{ background-color: #16a34a; color: white; padding: 10px 18px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 14px; display: inline-block; }}
            .btn-excel:hover {{ background-color: #15803d; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ padding: 12px; border: 1px solid #cbd5e1; text-align: left; }}
            th {{ background: #2563eb; color: white; }}
            tr:nth-child(even) {{ background: #f1f5f9; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Student Exam Results ({len(submissions)} Submissions)</h2>
                <a href="/export-excel?key={ADMIN_KEY}" class="btn-excel">📥 Download Excel Report</a>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>ID</th><th>Name</th><th>Section</th><th>Score</th><th>Percentage</th><th>Violations</th><th>Time</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)