from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta
import os
from config import Config


# Initialize Flask application
app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)


# Define database models

class Department(db.Model):
    """Department model representing university departments"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    courses = db.relationship('Course', backref='department', lazy=True)


class Course(db.Model):
    """Course model representing courses offered by departments"""
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    course_name = db.Column(db.String(200), nullable=False)
    notes = db.relationship('Note', backref='course', lazy=True)



class Note(db.Model):
    """Note model for storing course-related notes and images"""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    notes = db.Column(db.Text)
    image_path = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone(timedelta(hours=3))))



class CurrentCourse(db.Model):
    """Current courses taken by the student in the current semester"""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


# Define routes

@app.route('/')
def index():
    """Home page listing all departments"""
    departments = Department.query.all()
    return render_template('index.html', departments=departments)


@app.route('/select_class/<int:dept_id>')
def select_class(dept_id):
    """Page to select a class after choosing a department"""
    department = Department.query.get_or_404(dept_id)
    return render_template('select_class.html', department=department)


@app.route('/courses/<int:dept_id>/<int:year>')
def courses(dept_id, year):
    """List courses for a selected department and year"""
    department = Department.query.get_or_404(dept_id)
    courses = Course.query.filter_by(department_id=dept_id, year=year).all()
    current_courses = CurrentCourse.query.all()
    current_course_ids = [cc.course_id for cc in current_courses]
    return render_template('courses.html', department=department, courses=courses, year=year,
                           current_course_ids=current_course_ids)


@app.route('/current_courses')
def current_courses():
    """Show currently taken courses"""
    current_courses = CurrentCourse.query.order_by(CurrentCourse.added_at.desc()).all()
    courses = [Course.query.get(cc.course_id) for cc in current_courses]
    return render_template('current_courses.html', courses=courses)


@app.route('/toggle_current_course/<int:course_id>', methods=['POST'])
def toggle_current_course(course_id):
    """Add or remove a course from the current semester"""
    course = Course.query.get_or_404(course_id)
    current_course = CurrentCourse.query.filter_by(course_id=course_id).first()

    if current_course:
        db.session.delete(current_course)
        message = 'Course removed from current semester.'
    else:
        current_course = CurrentCourse(course_id=course_id)
        db.session.add(current_course)
        message = 'Course added to current semester.'

    db.session.commit()
    flash(message, 'success')
    return redirect(request.referrer or url_for('index'))


@app.route('/edit_elective/<int:course_id>', methods=['GET', 'POST'])
def edit_elective(course_id):
    """Edit elective course name"""
    course = Course.query.get_or_404(course_id)

    if 'ELECTIVE' not in course.course_name.upper():
        abort(404)

    if request.method == 'POST':
        new_name = request.form.get('course_name')
        if new_name:
            course.course_name = new_name
            db.session.commit()
            flash('Course name updated successfully!', 'success')
            return redirect(url_for('current_courses'))

    return render_template('edit_elective.html', course=course)


@app.route('/add_note/<int:course_id>', methods=['GET', 'POST'])
def add_note(course_id):
    """Add a note for a course, including optional image upload"""
    course = Course.query.get_or_404(course_id)

    if request.method == 'POST':
        note_text = request.form.get('note')
        image = request.files.get('image')
        image_path = None

        if image and image.filename:
            image_path = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image.filename}"
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_path))

        note = Note(
            course_id=course_id,
            notes=note_text,
            image_path=image_path
        )
        db.session.add(note)
        db.session.commit()

        flash('Note added successfully!', 'success')
        return redirect(url_for('courses', dept_id=course.department_id, year=course.year))

    notes = Note.query.filter_by(course_id=course_id).order_by(Note.created_at.desc()).all()
    return render_template('notes.html', course=course, notes=notes)


@app.route('/delete_note/<int:note_id>', methods=['POST'])
def delete_note(note_id):
    """Delete a note along with its associated image (if any)"""
    note = Note.query.get_or_404(note_id)
    course_id = note.course_id

    if note.image_path:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], note.image_path)
        if os.path.exists(image_path):
            os.remove(image_path)

    db.session.delete(note)
    db.session.commit()
    flash('Note deleted successfully!', 'success')
    return redirect(url_for('add_note', course_id=course_id))


@app.route('/all_notes')
def all_notes():
    """Display all notes"""
    all_notes = Note.query.order_by(Note.created_at.desc()).all()
    return render_template('all_notes.html', notes=all_notes)


@app.route('/update_note/<int:note_id>', methods=['POST'])
def update_note(note_id):
    """Update an existing note"""
    try:
        data = request.get_json()
        note = Note.query.get_or_404(note_id)
        note.notes = data['note']
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def init_db():
    with app.app_context():
        db.create_all()

        # Add departments
        if not Department.query.first():
            departments = [
                'Computer Engineering',
                'Industrial Engineering',
                'Electrical-Electronics Engineering',
                'Software Engineering',
                'Energy Systems Engineering',
                'Civil Engineering',
                'Mechanical Engineering'
            ]

            for dept_name in departments:
                dept = Department(name=dept_name)
                db.session.add(dept)
            db.session.commit()
            print("Departments added.")

        # Computer Engineering courses
        comp_eng = Department.query.filter_by(name='Computer Engineering').first()
        if comp_eng and not Course.query.filter_by(department_id=comp_eng.id).first():
            comp_courses = [
                # 1st Year Fall
                (1, 'Fall', 'MATH 1100 - MATHEMATICAL LOGIC'),
                (1, 'Fall', 'MATH 1131 - CALCULUS I'),
                (1, 'Fall', 'PHYS 1121 - PHYSICS I'),
                (1, 'Fall', 'SE 1105 - PROGRAMMING AND PROBLEM SOLVING I'),
                (1, 'Fall', 'SOFL 1101 - ACADEMIC ENGLISH I'),
                # 1st Year Spring
                (1, 'Spring', 'COMP 1202 - DISCRETE STRUCTURES'),
                (1, 'Spring', 'MATH 1132 - CALCULUS II'),
                (1, 'Spring', 'PHYS 1122 - PHYSICS II'),
                (1, 'Spring', 'SOFL 1102 - ACADEMIC ENGLISH II'),
                (1, 'Spring', 'UNV. COMP 1 - UNIVERSITY ELECTIVE COURSE'),
                # 2nd Year Fall
                (2, 'Fall', 'COMP 2233 - DATA STRUCTURES'),
                (2, 'Fall', 'EEE 2274 - FUNDAMENTALS OF ELECTRONICS'),
                (2, 'Fall', 'MATH 2260 - PROBABILITY AND STATISTICS FOR ENGINEERS'),
                (2, 'Fall', 'SE 2228 - ALGORITHM ANALYSIS AND DESIGN'),
                (2, 'Fall', 'UNV ELECT COMP - UNIVERSITY ELECTIVE COURSE'),
                # 2nd Year Spring
                (2, 'Spring', 'COMP 2215 - OBJECT-ORIENTED PROGRAMMING'),
                (2, 'Spring', 'COMP 3330 - AUTOMATA THEORY'),
                (2, 'Spring', 'EEE 2110 - DIGITAL DESIGN'),
                (2, 'Spring', 'MATH 2255 - LINEAR ALGEBRA'),
                # 3rd Year Fall
                (3, 'Fall', 'COMP 3315 - COMPUTER ORGANIZATION'),
                (3, 'Fall', 'COMP 3327 - COMPUTER NETWORKS'),
                (3, 'Fall', 'MATH 2261 - INTRODUCTION TO DIFFERENTIAL EQUATIONS'),
                (3, 'Fall', 'ELECT COMP A1 - DEPARTMENT ELECTIVE COURSE'),
                (3, 'Fall', 'UNV. COMP 2 - UNIVERSITY ELECTIVE COURSE'),
                # 3rd Year Spring
                (3, 'Spring', 'COMP 3304 - FUNDAMENTALS OF SOFTWARE ENGINEERING'),
                (3, 'Spring', 'COMP 3323 - OPERATING SYSTEMS'),
                (3, 'Spring', 'COMP 3328 - EMBEDDED SYSTEMS'),
                (3, 'Spring', 'ENGR 3450 - PROJECT MANAGEMENT'),
                (3, 'Spring', 'ENGR 4400 - ENGINEERING ETHICS AND SEMINAR'),
                (3, 'Spring', 'UNV. COMP 3 - UNIVERSITY ELECTIVE COURSE'),
                # 4th Year Fall
                (4, 'Fall', 'COMP 4910 - SENIOR DESIGN PROJECT I'),
                (4, 'Fall', 'ELECT COMP A2 - DEPARTMENT ELECTIVE COURSE'),
                (4, 'Fall', 'ELECT COMP B2 - DEPARTMENT ELECTIVE COURSE'),
                (4, 'Fall', 'UNV. COMP 4 - UNIVERSITY ELECTIVE COURSE'),
                # 4th Year Spring
                (4, 'Spring', 'COMP 4920 - SENIOR DESIGN PROJECT II'),
                (4, 'Spring', 'ELECT COMP A3 - DEPARTMENT ELECTIVE COURSE'),
                (4, 'Spring', 'ELECT COMP B3 - DEPARTMENT ELECTIVE COURSE')
            ]

            for year, semester, course_name in comp_courses:
                course = Course(
                    department_id=comp_eng.id,
                    year=year,
                    semester=semester,
                    course_name=course_name
                )
                db.session.add(course)
            db.session.commit()
            print("Computer Engineering courses added.")

        # Industrial Engineering courses
        ind_eng = Department.query.filter_by(name='Industrial Engineering').first()
        if ind_eng and not Course.query.filter_by(department_id=ind_eng.id).first():
            ind_courses = [
                # 1st Year Fall
                (1, 'Fall', 'ENGR 1115 - INTRODUCTION TO PROGRAMMING'),
                (1, 'Fall', 'MATH 1100 - MATHEMATICAL LOGIC'),
                (1, 'Fall', 'MATH 1131 - CALCULUS I'),
                (1, 'Fall', 'PHYS 1121 - PHYSICS I'),
                (1, 'Fall', 'SOFL 1101 - ACADEMIC ENGLISH I'),
                # 1st Year Spring
                (1, 'Spring', 'CHEM 1130 - ENGINEERING CHEMISTRY'),
                (1, 'Spring', 'ENGR 1116 - OBJECT-ORIENTED PROGRAMMING'),
                (1, 'Spring', 'MATH 1132 - CALCULUS II'),
                (1, 'Spring', 'SOFL 1102 - ACADEMIC ENGLISH II'),
                # 2nd Year Fall
                (2, 'Fall', 'ECON 1120 - ESSANTIALS ECONOMICS'),
                (2, 'Fall', 'IE 2511 - COST ANALYSIS IN ENGINEERING'),
                (2, 'Fall', 'IE 2531 - PROBABILITY FOR ENGINEERS'),
                (2, 'Fall', 'IE 2551 - ALGORITHMS AND COMPUTATION'),
                (2, 'Fall', 'MATH 2255 - LINEAR ALGEBRA'),
                # 2nd Year Spring
                (2, 'Spring', 'IE 2512 - ENGINEERING ECONOMICS'),
                (2, 'Spring', 'IE 2524 - WORK SYSTEMS ANALYSIS AND DESIGN'),
                (2, 'Spring', 'IE 2532 - STATISTICS FOR ENGINEERS'),
                (2, 'Spring', 'IE 2552 - MODELING IN OPERATIONS RESEARCH'),
                (2, 'Spring', 'MATH 2261 - INTRODUCTION TO DIFFERENTIAL EQUATIONS'),
                # 3rd Year Fall
                (3, 'Fall', 'ENGR 3450 - PROJECT MANAGEMENT'),
                (3, 'Fall', 'ENGR 4400 - ENGINEERING ETHICS AND SEMINAR'),
                (3, 'Fall', 'IE 3513 - QUALITY ASSURANCE AND RELIABILITY'),
                (3, 'Fall', 'IE 3523 - PRODUCTION AND SERVICE SYSTEMS PLANNING'),
                (3, 'Fall', 'IE 3553 - DETERMINISTIC OPERATIONS RESEARCH'),
                (3, 'Fall', '[G] UNV ELECT IE1 - UNIVERSITY ELECTIVE COURSE IE1'),
                # 3rd Year Spring
                (3, 'Spring', 'IE 3511 - SYSTEM SIMULATION'),
                (3, 'Spring', 'IE 3524 - INTEGRATED MANUFACTURING SYSTEMS'),
                (3, 'Spring', 'IE 3554 - STOCHASTIC OPERATIONS RESEARCH'),
                (3, 'Spring', 'IE 3562 - INDUSTRIAL INFORMATION SYSTEMS'),
                (3, 'Spring', '[G] ELECT IE 45X1-A - DEPARTMENT ELECTIVE COURSE IE 45X1-A'),
                # 4th Year Fall
                (4, 'Fall', 'IE 4911 - SYSTEM ANALYSIS'),
                (4, 'Fall', '[G] ELECT IE 45X1-B - DEPARTMENT ELECTIVE COURSE IE 45X1-B'),
                (4, 'Fall', '[G] ELECT IE 45X2-A - DEPARTMENT ELECTIVE COURSE IE 45X2-A'),
                (4, 'Fall', '[G] UNV ELECT IE2 - UNIVERSITY ELECTIVE COURSE IE2'),
                # 4th Year Spring
                (4, 'Spring', 'IE 4912 - SYSTEM DESIGN'),
                (4, 'Spring', '[G] ELECT IE 45X2-B - DEPARTMENT ELECTIVE COURSE IE 45X2-B'),
                (4, 'Spring', '[G] ELECT IE 45X3-A - DEPARTMENT ELECTIVE COURSE IE 45X3-A'),
                (4, 'Spring', '[G] ELECT IE 45X4-A - DEPARTMENT ELECTIVE COURSE IE 45X4-A'),
                (4, 'Spring', '[G] UNV ELECT IE3 - UNIVERSITY ELECTIVE COURSE IE3')
            ]

            for year, semester, course_name in ind_courses:
                course = Course(
                    department_id=ind_eng.id,
                    year=year,
                    semester=semester,
                    course_name=course_name
                )
                db.session.add(course)
            db.session.commit()
            print("Industrial Engineering courses added.")

        # Civil Engineering courses
        civil_eng = Department.query.filter_by(name='Civil Engineering').first()
        if civil_eng and not Course.query.filter_by(department_id=civil_eng.id).first():
            civil_courses = [
                # 1st Year Fall
                (1, 'Fall', 'ENGR 1115 - INTRODUCTION TO PROGRAMMING'),
                (1, 'Fall', 'MATH 1100 - MATHEMATICAL LOGIC'),
                (1, 'Fall', 'MATH 1131 - CALCULUS I'),
                (1, 'Fall', 'PHYS 1121 - PHYSICS I'),
                (1, 'Fall', 'SOFL 1101 - ACADEMIC ENGLISH I'),
                # 1st Year Spring
                (1, 'Spring', 'CE 1102 - ENGINEERING MECHANICS I'),
                (1, 'Spring', 'CHEM 1130 - ENGINEERING CHEMISTRY'),
                (1, 'Spring', 'MATH 1132 - CALCULUS II'),
                (1, 'Spring', 'SOFL 1102 - ACADEMIC ENGLISH II'),
                # 2nd Year Fall
                (2, 'Fall', 'CE 2101 - FUNDAMENTALS OF MATERIAL SCIENCE'),
                (2, 'Fall', 'CE 2103 - STRENGTH OF MATERIALS'),
                (2, 'Fall', 'CE 2105 - ENGINEERING MECHANICS II : DYNAMICS'),
                (2, 'Fall', 'MATH 2230 - COMPUTATIONAL METHODS IN ENGINEERING'),
                (2, 'Fall', 'MATH 2263 - DIFFERENTIAL EQUATIONS AND DYNAMIC SYSTEMS'),
                (2, 'Fall', 'UNV ELECT CE1 - UNIVERSITY ELECTIVE CE 1'),
                # 2nd Year Spring
                (2, 'Spring', 'CE 2102 - INTRODUCTION TO STRUCTURAL ANALYSIS'),
                (2, 'Spring', 'CE 2104 - CONSTRUCTION MATERIALS'),
                (2, 'Spring', 'CE 2106 - FLUID MECHANICS'),
                (2, 'Spring', 'MATH 2260 - PROBABILITY AND STATISTICS FOR ENGINEERS'),
                # 3rd Year Fall
                (3, 'Fall', 'CE 3101 - FUNDAMENTALS OF TRANSPORTATION ENGINEERING'),
                (3, 'Fall', 'CE 3103 - SOIL MECHANICS'),
                (3, 'Fall', 'CE 3105 - HYDROMECHANICS'),
                (3, 'Fall', 'ENGR 3450 - PROJECT MANAGEMENT'),
                (3, 'Fall', 'ELECT CE B1 - CE FIELD ELECTIVE GROUP B1'),
                # 3rd Year Spring
                (3, 'Spring', 'CE 3102 - FUNDAMENTALS OF REINFORCED CONCRETE DESIGN'),
                (3, 'Spring', 'CE 3104 - FUNDAMENTALS OF STEEL STRUCTURE DESIGN'),
                (3, 'Spring', 'CE 3106 - FOUNDATION ENGINEERING'),
                (3, 'Spring', 'CE 3108 - CONSTRUCTION MANAGEMENT'),
                (3, 'Spring', 'CE 3110 - COMPUTER-AIDED DESIGN'),
                (3, 'Spring', 'ELECT CE A1 - CE FIELD ELECTIVE GROUP A1'),
                # 4th Year Fall
                (4, 'Fall', 'CE 4120 - SUSTAINABILITY AND CIRCULAR ECONOMY FOR CIVIL ENGINEERS'),
                (4, 'Fall', 'CE 4910 - SENIOR DESIGN PROJECT I'),
                (4, 'Fall', 'ENGR 4400 - ENGINEERING ETHICS AND SEMINAR'),
                (4, 'Fall', 'ELECT CE A2 - CE FIELD ELECTIVE GROUP A2'),
                (4, 'Fall', 'ELECT CE A3 - CE FIELD ELECTIVE GROUP A3'),
                # 4th Year Spring
                (4, 'Spring', 'CE 4920 - SENIOR DESIGN PROJECT II'),
                (4, 'Spring', 'ELECT CE A4 - CE FIELD ELECTIVE GROUP A4'),
                (4, 'Spring', 'ELECT CE B2 - CE FIELD ELECTIVE GROUP B2'),
                (4, 'Spring', 'UNV ELECT CE2 - UNIVERSITY ELECTIVE CE2'),
                (4, 'Spring', 'UNV ELECT CE3 - UNIVERSITY ELECTIVE CE3')
            ]

            for year, semester, course_name in civil_courses:
                course = Course(
                    department_id=civil_eng.id,
                    year=year,
                    semester=semester,
                    course_name=course_name
                )
                db.session.add(course)
            db.session.commit()
            print("Civil Engineering courses added.")

        # Mechanical Engineering courses
        mech_eng = Department.query.filter_by(name='Mechanical Engineering').first()
        if mech_eng and not Course.query.filter_by(department_id=mech_eng.id).first():
            mech_courses = [
                # 1st Year Fall
                (1, 'Fall', 'ENGR 1115 - INTRODUCTION TO PROGRAMMING'),
                (1, 'Fall', 'MATH 1100 - MATHEMATICAL LOGIC'),
                (1, 'Fall', 'MATH 1131 - CALCULUS I'),
                (1, 'Fall', 'PHYS 1121 - PHYSICS I'),
                (1, 'Fall', 'SOFL 1101 - ACADEMIC ENGLISH I'),
                # 1st Year Spring
                (1, 'Spring', 'CHEM 1130 - ENGINEERING CHEMISTRY'),
                (1, 'Spring', 'MATH 1132 - CALCULUS II'),
                (1, 'Spring', 'ME 1110 - INTRODUCTION TO MECHANICAL ENGINEERING'),
                (1, 'Spring', 'PHYS 1122 - PHYSICS II'),
                (1, 'Spring', 'SOFL 1102 - ACADEMIC ENGLISH II'),
                # 2nd Year Fall
                (2, 'Fall', 'EEE 2280 - ELECTRICAL CIRCUITS AND SYSTEMS'),
                (2, 'Fall', 'ENGR 2120 - INTRODUCTION TO COMPUTER-AIDED MODELING'),
                (2, 'Fall', 'ME 2210 - ENGINEERING MECHANICS I'),
                (2, 'Fall', 'ME 2710 - MATERIAL SCIENCE'),
                # 2nd Year Spring
                (2, 'Spring', 'MATH 2230 - COMPUTATIONAL METHODS IN ENGINEERING'),
                (2, 'Spring', 'MATH 2263 - DIFFERENTIAL EQUATIONS AND DYNAMIC SYSTEMS'),
                (2, 'Spring', 'ME 2220 - MECHANICS OF MATERIALS'),
                (2, 'Spring', 'ME 2320 - THERMODYNAMICS'),
                # 3rd Year Fall
                (3, 'Fall', 'EEE 3718 - FEEDBACK SYSTEMS'),
                (3, 'Fall', 'ENGR 3450 - PROJECT MANAGEMENT'),
                (3, 'Fall', 'ME 3220 - ENGINEERING MECHANICS II'),
                (3, 'Fall', 'ME 3320 - HEAT AND MASS TRANSFER'),
                (3, 'Fall', 'ME 3420 - PRODUCTION TECHNOLOGIES AND PROCESSES'),
                (3, 'Fall', 'UNV ELECT ME1 - UNIVERSITY ELECTIVE COURSE ME1'),
                # 3rd Year Spring
                (3, 'Spring', 'MATH 2260 - PROBABILITY AND STATISTICS FOR ENGINEERS'),
                (3, 'Spring', 'ME 3330 - FLUID MECHANICS AND MACHINERY'),
                (3, 'Spring', 'ME 3410 - MECHANICAL COMPONENTS'),
                (3, 'Spring', 'ME 3510 - THEORY OF MACHINES AND MECHANISMS'),
                (3, 'Spring', 'ELECT ME A1 - DEPARTMENTAL ELECTIVE COURSE A1'),
                # 4th Year Fall
                (4, 'Fall', 'ENGR 4400 - ENGINEERING ETHICS AND SEMINAR'),
                (4, 'Fall', 'ME 4910 - SENIOR DESIGN PROJECT I'),
                (4, 'Fall', 'ELECT ME A2 - DEPARTMENTAL ELECTIVE COURSE A2'),
                (4, 'Fall', 'ELECT ME B1 - DEPARTMENTAL ELECTIVE COURSE B1'),
                (4, 'Fall', 'UNV ELECT ME2 - UNIVERSITY ELECTIVE COURSE ME2'),
                # 4th Year Spring
                (4, 'Spring', 'ME 4920 - SENIOR DESIGN PROJECT II'),
                (4, 'Spring', 'ELECT ME A3 - DEPARTMENTAL ELECTIVE COURSE A3'),
                (4, 'Spring', 'ELECT ME B2 - DEPARTMENTAL ELECTIVE COURSE B2'),
                (4, 'Spring', 'ELECT ME B3 - DEPARTMENTAL ELECTIVE COURSE B3'),
                (4, 'Spring', 'UNV ELECT ME3 - UNIVERSITY ELECTIVE ME3')
            ]

            for year, semester, course_name in mech_courses:
                course = Course(
                    department_id=mech_eng.id,
                    year=year,
                    semester=semester,
                    course_name=course_name
                )
                db.session.add(course)
            db.session.commit()
            print("Mechanical Engineering courses added.")

        # Electrical-Electronics Engineering courses
        ee_eng = Department.query.filter_by(name='Electrical-Electronics Engineering').first()
        if ee_eng and not Course.query.filter_by(department_id=ee_eng.id).first():
            ee_courses = [
                # 1st Year Fall
                (1, 'Fall', 'ENGR 1115 - INTRODUCTION TO PROGRAMMING'),
                (1, 'Fall', 'MATH 1100 - MATHEMATICAL LOGIC'),
                (1, 'Fall', 'MATH 1131 - CALCULUS I'),
                (1, 'Fall', 'PHYS 1121 - PHYSICS I'),
                (1, 'Fall', 'SOFL 1101 - ACADEMIC ENGLISH I'),
                # 1st Year Spring
                (1, 'Spring', 'MATH 2255 - LINEAR ALGEBRA'),
                (1, 'Spring', 'MATH 1132 - CALCULUS II'),
                (1, 'Spring', 'PHYS 1122 - PHYSICS II'),
                (1, 'Spring', 'SOFL 1102 - ACADEMIC ENGLISH II'),
                # 2nd Year Fall
                (2, 'Fall', 'EEE 2271 - CIRCUIT THEORY I'),
                (2, 'Fall', 'EEE 2273 - DIGITAL DESIGN'),
                (2, 'Fall', 'MATH 2259 - ENGINEERING MATHEMATICS'),
                (2, 'Fall', 'MATH 2263 - DIFFERENTIAL EQUATIONS AND DYNAMIC SYSTEMS'),
                # 2nd Year Spring
                (2, 'Spring', 'EEE 2022 - CIRCUIT THEORY II'),
                (2, 'Spring', 'EEE 2214 - ENGINEERING ELECTROMAGNETICS'),
                (2, 'Spring', 'EEE 2426 - ANALOG ELECTRONICS'),
                (2, 'Spring', 'ELECT EEE A1 - DEPARTMENTAL ELECTIVE COURSES EEE A1'),
                # 3rd Year Fall
                (3, 'Fall', 'EEE 3435 -	DIGITAL ELECTRONICS'),
                (3, 'Fall', 'EEE 3513 -	SIGNALS AND SYSTEMS'),
                (3, 'Fall', 'EEE 3615 -	ELECTROMECHANICAL ENERGY CONVERSION'),
                (3, 'Fall', 'MATH 3305 - PROBABILITY AND RANDOM PROCESSES'),
                (3, 'Fall', 'ENGR 3450 - PROJECT MANAGEMENT'),
                # 3rd Year Spring
                (3, 'Spring', 'EEE 3134 - MICROCONTROLLERS'),
                (3, 'Spring', 'EEE 3524 - TELECOMMUNICATIONS'),
                (3, 'Spring', 'EEE 3638 - POWER SYSTEMS'),
                (3, 'Spring', 'EEE 3718 - FEEDBACK SYSTEMS'),
                (3, 'Spring', 'UNV. EEE2 - UNIVERSITY ELECTIVE COURSES EEE2'),
                # 4th Year Fall
                (4, 'Fall', 'EEE 4910 - SENIOR DESIGN PROJECT I'),
                (4, 'Fall', 'ENGR 4400 - ENGINEERING ETHICS AND SEMINAR'),
                (4, 'Fall', 'ELECT EEE A2 - DEPARTMENTAL ELECTIVE COURSE A2'),
                (4, 'Fall', 'ELECT EEE B1 - DEPARTMENTAL ELECTIVE COURSE B1'),
                (4, 'Fall', 'UNV ELECT EEE1 - UNIVERSITY ELECTIVE COURSE EEE1'),
                # 4th Year Spring
                (4, 'Spring', 'EEE 4920 - SENIOR DESIGN PROJECT II'),
                (4, 'Spring', 'ELECT EEE A3 - DEPARTMENTAL ELECTIVE COURSE A3'),
                (4, 'Spring', 'ELECT EEE B2 - DEPARTMENTAL ELECTIVE COURSE B2'),
                (4, 'Spring', 'ELECT EEE B3 - DEPARTMENTAL ELECTIVE COURSE B3'),
                (4, 'Spring', 'UNV ELECT EEE2 - UNIVERSITY ELECTIVE COURSE EEE2')
            ]

            for year, semester, course_name in ee_courses:
                course = Course(
                    department_id=ee_eng.id,
                    year=year,
                    semester=semester,
                    course_name=course_name
                )
                db.session.add(course)
            db.session.commit()
            print("Electrical-Electronics Engineering courses added.")

        # Energy Systems Engineering courses
        energy_eng = Department.query.filter_by(name='Energy Systems Engineering').first()
        if energy_eng and not Course.query.filter_by(department_id=energy_eng.id).first():
            energy_courses = [
                # 1st Year Fall
                (1, 'Fall', 'ENGR 1115 - INTRODUCTION TO PROGRAMMING'),
                (1, 'Fall', 'MATH 1100 - MATHEMATICAL LOGIC'),
                (1, 'Fall', 'MATH 1131 - CALCULUS I'),
                (1, 'Fall', 'PHYS 1121 - PHYSICS I'),
                (1, 'Fall', 'SOFL 1101 - ACADEMIC ENGLISH I'),
                # 1st Year Spring
                (1, 'Spring', 'CHEM 1130 - ENGINEERING CHEMISTRY'),
                (1, 'Spring', 'ESE 1110 - INTRODUCTION TO ENERGY SYSTEMS ENGINEERING'),
                (1, 'Spring', 'MATH 1132 - CALCULUS II'),
                (1, 'Spring', 'PHYS 1122 - PHYSICS II'),
                (1, 'Spring', 'SOFL 1102 - ACADEMIC ENGLISH II'),
                # 2nd Year Fall
                (2, 'Fall', 'ENGR 2120 - INTRO TO COMPUTER AIDED MODELING'),
                (2, 'Fall', 'MATH 2230 - COMPUTATIONAL METHODS IN ENGINEERING'),
                (2, 'Fall', 'ME 2320 - THERMODYNAMICS'),
                (2, 'Fall', 'MATH 2263 - DIFFERENTIAL EQUATIONS AND DYNAMIC SYSTEMS'),
                # 2nd Year Spring
                (2, 'Spring', 'EEE 2280 - ELECTRIC CIRCUITS AND SYSTEMS'),
                (2, 'Spring', 'ESE 2501 - MEASUREMENT TECHNIQUES AND INSTRUMENTATION'),
                (2, 'Spring', 'MATH 2260 - PROBABILITY AND STATISTICS FOR ENGINEERING'),
                (2, 'Spring', 'ME 3330 - FLUID MECHANICS AND MACHINERY'),
                # 3rd Year Fall
                (3, 'Fall', 'EEE 3718 - FEEDBACK SYSTEMS'),
                (3, 'Fall', 'ESE 3504 -	SMART ENERGY SYSTEMS'),
                (3, 'Fall', 'EEE 3615 -	ELECTROMECHANICAL ENERGY CONVERSION'),
                (3, 'Fall', 'ME 2710 - MATERIAL SCIENCE'),
                (3, 'Fall', 'ME 3320 - HEAT AND MASS TRANSFER'),
                # 3rd Year Spring
                (3, 'Spring', 'ENGR 3450 - PROJECT MANAGEMENT'),
                (3, 'Spring', 'ESE 3404 - ENERGY EFFICIENCY AND MANAGEMENT'),
                (3, 'Spring', 'ESE 3510 - POWER CONVERSION SYSTEMS'),
                (3, 'Spring', 'ELECT ESE B1 - DEPARTMENTAL ELECTIVE COURSES-B1'),
                (3, 'Spring', 'ESE 32X2 - RENEWABLE ENERGY ELECTIVE II'),
                (3, 'Spring', 'UNV ELECT ESE1 - UNIVERSITY ELECTIVE COURSE ESE1'),
                # 4th Year Fall
                (4, 'Fall', 'ENGR 4400 - ENGINEERING ETHICS AND SEMINAR'),
                (4, 'Fall', 'ESE 4910 -	ENERGY SYSTEMS ANALYSIS'),
                (4, 'Fall', 'ELECT ESE A1 - DEPARTMENTAL ELECTIVE COURSE A1'),
                (4, 'Fall', 'ELECT ESE B1 - DEPARTMENTAL ELECTIVE COURSE B1'),
                (4, 'Fall', 'UNV ELECT ESE2 - UNIVERSITY ELECTIVE COURSE ESE2'),
                # 4th Year Spring
                (4, 'Spring', 'ESE 4920 - ENERGY SYSTEMS DESIGN'),
                (4, 'Spring', 'ELECT ESE A2 - DEPARTMENTAL ELECTIVE COURSE A2'),
                (4, 'Spring', 'ELECT ESE B2 - DEPARTMENTAL ELECTIVE COURSE B2'),
                (4, 'Spring', 'ELECT ESE B3 - DEPARTMENTAL ELECTIVE COURSE B3'),
                (4, 'Spring', 'UNV ELECT ESE3 - UNIVERSITY ELECTIVE COURSE ESE3')
            ]

            for year, semester, course_name in energy_courses:
                course = Course(
                    department_id=energy_eng.id,
                    year=year,
                    semester=semester,
                    course_name=course_name
                )
                db.session.add(course)
            db.session.commit()
            print("Energy Systems Engineering courses added.")

        # Software Engineering courses
        software_eng = Department.query.filter_by(name='Software Engineering').first()
        if software_eng and not Course.query.filter_by(department_id=software_eng.id).first():
            software_courses = [
                # 1st Year Fall
                (1, 'Fall', 'MATH 1100 - MATHEMATICAL LOGIC'),
                (1, 'Fall', 'MATH 1131 - CALCULUS I'),
                (1, 'Fall', 'PHYS 1121 - PHYSICS I'),
                (1, 'Fall', 'SE 1105 - PROGRAMMING AND PROBLEM SOLVING I'),
                (1, 'Fall', 'SOFL 1101 - ACADEMIC ENGLISH I'),
                # 1st Year Spring
                (1, 'Spring', 'MATH 1132 - CALCULUS II'),
                (1, 'Spring', 'PHYS 1122 - PHYSICS II'),
                (1, 'Spring', 'SE 1108 - PROGRAMMING AND PROBLEM SOLVING II'),
                (1, 'Spring', 'SOFL 1102 - ACADEMIC ENGLISH II'),
                # 2nd Year Fall
                (2, 'Fall', 'MATH 2255 - LINEAR ALGEBRA'),
                (2, 'Fall', 'COMP 1202 - DISCRETE COMPUTATIONAL STRUCTURES'),
                (2, 'Fall', 'SE 2217 - SOFTWARE ENGINEERING PRINCIPLES'),
                (2, 'Fall', 'SE 2310 - DATA STRUCTURES AND ALGORITHMS'),
                # 2nd Year Spring
                (2, 'Spring', 'MATH 2261 - INTRODUCTION TO DIFFERENTIAL EQUATIONS'),
                (2, 'Spring', 'SE 2226 - SOFTWARE QUALITY ASSURANCE AND TESTING'),
                (2, 'Spring', 'SE 2228 - ANALYSIS AND DESIGN OF ALGORITHMS'),
                (2, 'Spring', 'SE 2230 - DATABASE SYSTEMS'),
                (2, 'Spring', 'SE 2232 - SOFTWARE SYSTEM ANALYSIS'),
                # 3rd Year Fall
                (3, 'Fall', 'SE 3317 - SOFTWARE DESIGN AND ARCHITECTURE'),
                (3, 'Fall', 'SE 3310 - OPERATING SYSTEMS AND NETWORKING'),
                (3, 'Fall', 'MATH 2260 - PROBABILITY AND STATISTICS FOR ENGINEERING'),
                (3, 'Fall', 'COMP 3330 - AUTOMATA THEORY'),
                (3, 'Fall', 'UNV ELECT SE1 - UNIVERSITY ELECTIVE COURSE SE1'),
                # 3rd Year Spring
                (3, 'Spring', 'EEE 2110	- DIGITAL DESIGN'),
                (3, 'Spring', '	ENGR 3450 - PROJECT MANAGEMENT'),
                (3, 'Spring', 'ENGR 4400 - ENGINEERING ETHICS AND SEMINAR'),
                (3, 'Spring', 'SE 3318 - SOFTWARE CONSTRUCTION'),
                (3, 'Spring', 'SE 3332 - LOW LEVEL PROGRAMMING'),
                (3, 'Spring', 'ELECT SE A1 - DEPARTMENT ELECTIVE COURSE A1'),
                # 4th Year Fall
                (4, 'Fall', 'SE 4910 - GRADUATION DESIGN PROJECT I'),
                (4, 'Fall', 'ELECT SE A2 - DEPARTMENTAL ELECTIVE COURSE A2'),
                (4, 'Fall', 'ELECT SE A3 - DEPARTMENTAL ELECTIVE COURSE A3'),
                (4, 'Fall', 'UNV ELECT SE2 - UNIVERSITY ELECTIVE COURSE SE2'),
                # 4th Year Spring
                (4, 'Spring', 'SE 4920 - GRADUATION DESIGN PROJECT II'),
                (4, 'Spring', 'ELECT SE B1 - DEPARTMENTAL ELECTIVE COURSE B1'),
                (4, 'Spring', 'ELECT SE B2 - DEPARTMENTAL ELECTIVE COURSE B2'),
                (4, 'Spring', 'UNV ELECT SE4 - UNIVERSITY ELECTIVE COURSE SE3')
            ]

            for year, semester, course_name in software_courses:
                course = Course(
                    department_id=software_eng.id,
                    year=year,
                    semester=semester,
                    course_name=course_name
                )
                db.session.add(course)
            db.session.commit()
            print("Software Engineering courses added.")

if __name__ == '__main__':
    init_db()
    app.run(debug=True , host='0.0.0.0', port=5001)


