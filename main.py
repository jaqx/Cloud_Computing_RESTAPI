
from google.cloud import datastore
from flask import Flask, request, Response, make_response, render_template, redirect, url_for
from google.oauth2 import id_token
from google.auth.transport import requests
import json
import constants
import string
import requests as http_requests
import random
import re

app = Flask(__name__)
client = datastore.Client()
client_id = "11332283004-g3fn2t90hg7tlveralit7s85plebbmq7.apps.googleusercontent.com"
client_secret = "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"

def validate_student(student_content):
    # Code Citation - Code was adapted from Stack Overflow
    # Source: https://stackoverflow.com/questions/57011986/how-to-check-that-a-string-contains-only-a-z-a-z-and-0-9-characters
    # Date accessed: April 27, 2022
    pattern = re.compile("[A-Za-z0-9\s]+")
    # End Code Citation

    # iterate through each of the content fields in student_content
    # this allows us to check each of the fields independently for PATCH
    for fields in student_content:
        if fields == "lastname_firstname":
            if not isinstance(student_content["lastname_firstname"], str):
                return False
        elif fields == "initial_level":
            if not isinstance(student_content["initial_level"], str):
                return False
        elif fields == "current_level":
            if not isinstance(student_content["current_level"], str):
                return False
        elif fields == "length_of_study":
            if not isinstance(student_content["length_of_study"], int):
                return False
        else:
            return False
    return True

def validate_course(course_content):
    # Code Citation - Code was adapted from Stack Overflow
    # Source: https://stackoverflow.com/questions/57011986/how-to-check-that-a-string-contains-only-a-z-a-z-and-0-9-characters
    # Date accessed: April 27, 2022
    pattern = re.compile("[A-Za-z0-9\s]+")
    # End Code Citation

    # iterate through each of the content fields in course_content
    # this allows us to check each of the fields independently for PATCH
    for fields in course_content:
        if fields == "level":
            if not isinstance(course_content["level"], str):
                return False
        elif fields == "name":
            if not isinstance(course_content["name"], str):
                return False
        elif fields == "term":
            if not isinstance(course_content["term"], str):
                return False
        # seperate function to validate student field
        elif fields == 'students':
            continue
        else:
            return False
    return True

def validate_student_level(course_content):
    # check to see if there are students to validate 
    if "students" in course_content:
        # iterate through all enrolled students in that class 
        for student in course_content["students"]:
            # if the students' current level does not match the level of the course,
            # student cannot be enrolled in the course 
            if student["current_level"] != course_content["level"]:
                return student["lastname_firstname"]
    return None

# create a response from this server as JSON
def return_json (json_object, status):
    response = make_response(json.dumps(json_object), status)
    response.headers["Content-Type"] = "application/json"
    return response

# remove "Bearer " from Authorization header to get raw JWT token
# returns raw Authorization header from request if successful
# returns None if Authorization is not in the request header
def trim_bearer(input_token):
    bearer = len('Bearer ')
    if input_token:
        if 'Bearer' in input_token:
            output_token = input_token[bearer:]
        return output_token
    return None

# Code Citation: Random String Generator adapted from Stack Overflow
# https://stackoverflow.com/questions/2257441/random-string-generation-with-upper-case-letters-and-digits
def state_generator(size=8, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

@app.route('/')
def index():
    state = state_generator()
    # add state to data store
    new_state = datastore.entity.Entity(key=client.key(constants.state))
    new_state.update({"state": state})
    client.put(new_state)
    return render_template("index.html", 
                            state = state,
                            client_id = client_id), 200

@app.route('/oauth', methods=['POST', 'GET'])
def authenticate():
    if request.method == 'GET':
        state_verify = request.args.get('state')
        code = request.args.get('code')
        redirect_uri = "https://jaquelin-final.wl.r.appspot.com/oauth"
        post_body = {'code': code, 'client_id': client_id,
                     'client_secret': client_secret, 'redirect_uri': redirect_uri,
                     'grant_type': 'authorization_code'}
        # compare state_verify with state
        query = client.query(kind=constants.state)
        unique_results = list(query.fetch())                   
        for i in unique_results:
            if state_verify == i["state"]:
                r = http_requests.post('https://oauth2.googleapis.com/token', data = json.dumps(post_body))
                results = r.json()
                # get JWT token
                jwt_token = results['id_token']

        # Step 1. decode the jwt_token variable     
        idinfo = id_token.verify_oauth2_token(jwt_token, requests.Request(), client_id)
        # 
        # Step 2. get the unique id and name of token 
        # 'sub' is the unique id associated with JWT
        user_id = idinfo['sub']           
        # 'name' is the name associated with JWT
        user_name = idinfo['name']
        #
        # Step 3. store this inside of datastore. This protects courses. If the sub of the person currently logged in
        # does not match the 'sub' of the teacher prevent the delete. 
        # compare state_verify with state and check that instructor id has not already been created
        query = client.query(kind=constants.instructor)
        unique_results = list(query.fetch())  
        instructor_found = False                 
        for i in unique_results:
            if i["instructor_id"] == user_id:
                instructor_found = True 
                break
        if not instructor_found:        
            new_instructor = datastore.entity.Entity(key=client.key(constants.instructor))
            new_instructor.update({"name": user_name, "instructor_id": user_id})
            client.put(new_instructor)
        return redirect(url_for('info', jwt_token = jwt_token ))
    else:
        return {'ERROR': 'Incorrect State'}, 404

@app.route('/info')
def info():
    # return render_template('info.html')
    jwt_token = request.args.get('jwt_token')
    return render_template("info.html", jwt_token = jwt_token)

@app.route('/students', methods = ['POST', 'GET'])
def post_students():
    token = trim_bearer(request.headers.get('Authorization'))
    if token:
        try:
            # try to verify authenticity of the JWT. if invalid, will return a value error
            # and be caught in the exception 
            id_token.verify_oauth2_token(token, requests.Request(), client_id)
        except ValueError:
            # Invalid token
            return return_json({"Error":"Invalid JWT"}, 401)                
    else:
        # missing JWT
        return return_json({"Error": "Missing JWT"}, 401)

    if request.method == 'POST':
        if 'application/json' not in request.mimetype:
            return return_json({"Error": "Not Acceptable Media Type"}, 406)
        content = request.get_json()
        # check that all 4 required attributes are in request body
        if len(content) != 4:
            return return_json({"Error": "Invalid entry. All 4 attributes are required to create a Student."}, 400)
        if not validate_student(content):
            return return_json({"Error": "Invalid entry. An attribute is in the wrong format."}, 400)
        new_student = datastore.entity.Entity(key=client.key(constants.students))
        new_student.update(
            {"lastname_firstname": content["lastname_firstname"],
            "initial_level": content["initial_level"],
            "current_level": content["current_level"],
            "length_of_study": content["length_of_study"]
            }
        )
        client.put(new_student)
        # add ID field
        student_id = new_student.key.id
        # add url
        app_url = request.url_root + "students/" + str(student_id)
        new_student['self'] = app_url
        new_student["id"] = student_id
        return return_json(new_student, 201)

    # only authenticated users can see list of students 
    elif request.method == 'GET':
        # pull data from datastore 
        query = client.query(kind=constants.students)
        q_limit = int(request.args.get('limit', '5'))
        q_offset = int(request.args.get('offset', '0'))

        # ensure that "next" page will return the next set of results 
        l_iterator = query.fetch(limit = q_limit, offset = q_offset)
        pages = l_iterator.pages 
        results = list(next(pages))

        # check if there are any pages remaining to display 
        if l_iterator.next_page_token:
            next_offset = q_offset + q_limit
            next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
        else:
            next_url = None
        # add datastore ids and self address to each record 
        for result in results:
            result['id'] = result.key.id
            # add url
            app_url = request.url_root + "students/" + str(result.key.id)
            result['self'] = app_url
        output = {"students": results}
        if next_url:
            output["next"] = next_url                
        return return_json(output, 200)
    else:
        return return_json({"Error": "Unsupported method"}, 405)

@app.route('/students/<student_id>', methods = ['GET', 'PATCH', 'DELETE'])
def modify_students(student_id):
    # pulls student record from datastore using student_id
    student_key = client.key(constants.students, int(student_id))
    student = client.get(key=student_key)
    token = trim_bearer(request.headers.get('Authorization'))
    if token:
        try:
            # try to verify authenticity of the JWT. if invalid, will return a value error
            # and be caught in the exception 
            id_token.verify_oauth2_token(token, requests.Request(), client_id)
        except ValueError:
            # Invalid token
            return return_json({"Error":"Invalid JWT"}, 401)                
    else:
        # missing JWT
        return return_json({"Error": "Missing JWT"}, 401)
    if request.method == 'GET':
        if student:
            return return_json({"student": student}, 200)
        else:
            return return_json({"Error": "No student with this student_id exists"}, 404)  
    elif request.method == 'PATCH':
        if 'application/json' not in request.mimetype:
            return return_json({"Error": "Not Acceptable Media Type"}, 406)
        # if student_id is found, proceed
        if student:
            content = request.get_json()
            if "id" in content:
                return return_json({"Error": "id is not an editable field"}, 400)
            if validate_student(content):
                # check to see that field exists in Student, then change to new value 
                for field in content:
                    if field in student:
                        student[field] = content[field]
                # now update row in datastore 
                client.put(student)
                response = student
                response["id"] = student.key.id
                return return_json(response, 200)
            else:
                return return_json({'Error': 'One or more fields does not exist for Students'}, 400)
        # if id is invalid
        else:
            return return_json({'Error': 'No student with this student_id exists'}, 404)
    elif request.method == 'DELETE':
        if student:
            # delete student from all courses
            query = client.query(kind=constants.courses)
            results = list(query.fetch())
            if results:                    
                for course in results:
                    new_student_list = []
                    # verify there is a list of students
                    if course["students"]:
                        for student in course["students"]:
                            if int(student_id) != int(student["id"]):
                                new_student_list.append(student)
                        course["students"] = new_student_list
                    client.put(course)
            # delete after successfully finding the student
            client.delete(student_key)
            return return_json({}, 204)
        else:
            # invalid student id, so cannot be deleted
            return return_json({"Error": "No student with this student_id exists"}, 403)

@app.route('/courses', methods = ['POST', 'GET'])
def post_courses():
    token = trim_bearer(request.headers.get('Authorization'))
    if token:
        try:
            # try to verify authenticity of the JWT. if invalid, will return a value error
            # and be caught in the exception 
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)
            user_id = idinfo['sub']
        except ValueError:
            # Invalid token
            return return_json({"Error":"Invalid JWT"}, 401)
    else:
        # missing JWT
        return return_json({"Error": "Missing JWT"}, 401)                
    if request.method == 'POST':
        if 'application/json' not in request.mimetype:
            return return_json({"Error": "Not Acceptable Media Type"}, 406)
        content = request.get_json()
        # check that all 4 required attributes are in request body
        required_fields = ['level', 'name', 'term']
        for fields in required_fields:
            if fields not in content:
                return return_json({"Error": "Invalid entry. Missing a required attribute."}, 400)
        if not validate_course(content):
            return return_json({"Error": "Invalid entry. An attribute is in the wrong format."}, 400)
        invalid_student_level = validate_student_level(content)
        if invalid_student_level:
            return return_json({"Error": str(invalid_student_level) + " is not in the correct level and cannot be enrolled"}, 400)

        new_course = datastore.entity.Entity(key=client.key(constants.courses))
        new_course.update(
            {"level": content["level"],
            "name": content["name"],
            "term": content["term"],
            "instructor": user_id
            }
        )
        # try to add the student field into the course if it exists in the body 
        try:
            new_course.update({"students": content["students"]})
        # if students does not exist in body content 
        except KeyError:
            new_course.update({"students": []})
        client.put(new_course)

        course_id = new_course.key.id
        # add url
        app_url = request.url_root + "courses/" + str(course_id)
        new_course['self'] = app_url
        
        # add course ID field
        new_course["id"] = course_id
        return return_json(new_course, 201)
    # only authenticated users can see list of students 
    elif request.method == 'GET':
        # pull data from datastore 
        query = client.query(kind=constants.courses)
        q_limit = int(request.args.get('limit', '5'))
        q_offset = int(request.args.get('offset', '0'))

        # ensure that "next" page will return the next set of results 
        l_iterator = query.fetch(limit = q_limit, offset = q_offset)
        pages = l_iterator.pages 
        results = list(next(pages))
        narrowed_results = []
        for course in results:
            if int(course["instructor"]) == int(user_id):
                narrowed_results.append(course)
    
        # check if there are any pages remaining to display 
        if l_iterator.next_page_token:
            next_offset = q_offset + q_limit
            next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
        else:
            next_url = None
        # add datastore ids and self address to each record 
        for result in narrowed_results:
            result['id'] = result.key.id
            app_url = request.url_root + "courses/" + str(result.key.id)
            result['self'] = app_url
        output = {"courses": narrowed_results}
        if next_url:
            output["next"] = next_url                
        return return_json(output, 200)
    else:
        return return_json({"Error": "Unsupported method"}, 405)

@app.route('/courses/<course_id>', methods = ['GET', 'PATCH', 'DELETE'])
def modify_courses(course_id):
    course_key = client.key(constants.students, int(course_id))
    course = client.get(key=course_key)
    token = trim_bearer(request.headers.get('Authorization'))
    if token:
        try:
            # try to verify authenticity of the JWT. if invalid, will return a value error
            # and be caught in the exception 
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)
        except ValueError:
            # Invalid token
            return return_json({"Error":"Invalid JWT"}, 401)                
    else:
        # missing JWT
        return return_json({"Error": "Missing JWT"}, 401)
    if request.method == 'GET':
        if course:
            return return_json({"course": course}, 200)
        else:
            return return_json({"Error": "No course with this course_id exists"}, 404)     
    elif request.method == 'PATCH':
        if 'application/json' not in request.mimetype:
            return return_json({"Error": "Not Acceptable Media Type"}, 406)
        # pulls course record from datastore using course_id
        course_key = client.key(constants.courses, int(course_id))
        course = client.get(key=course_key)     
        # if course_id is found, proceed
        if course:
            content = request.get_json()
            if "id" in content:
                return return_json({"Error": "id is not an editable field"}, 400)
            else: 
                if validate_course(content):
                    # check to see that field exists in course, then change to new value 
                    for field in content:
                        if field in course:
                            course[field] = content[field]
                    # now update row in datastore 
                    client.put(course)
                    response = course
                    response["id"] = course.key.id
                    return return_json(response, 200)
                else:
                    return return_json({'Error': 'One or more fields does not exist for Courses'}, 400)
        # if id is invalid
        else:
            return return_json({'Error': 'No course with this course_id exists'}, 404)

    elif request.method == 'DELETE':
        # get course based on course_id and get token
        course_key = client.key(constants.courses, int(course_id))
        course = client.get(key=course_key)
        user_id = idinfo['sub']
        # check if course id is valid
        if course:
            # check if the user_id matches the instructor id from the course first
            if int(user_id) == int(course["instructor"]):
            # delete after successfully finding the course
                client.delete(course_key)
                return return_json({}, 204)
            else:
                return return_json({"Error": "Instructor ID does not match Course Instructor. Cannot Delete"}, 401)
        else:
            # invalid course id, so cannot be deleted
            return return_json({"Error": "No course with this course_id exists"}, 403)
    else:
        return return_json({"Error": "Unsupported method"}, 405)

@app.route('/courses/<course_id>/students/<student_id>', methods=['PATCH','DELETE'])
def edit_students_in_course(student_id, course_id):
    student_key = client.key(constants.students, int(student_id))
    student = client.get(key=student_key)   
    course_key = client.key(constants.courses, int(course_id))
    course = client.get(key=course_key)
    token = trim_bearer(request.headers.get('Authorization'))
    if token:
        try:
            # try to verify authenticity of the JWT. if invalid, will return a value error
            # and be caught in the exception 
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)
            user_id = idinfo['sub']
        except ValueError:
            # Invalid token
            return return_json({"Error":"Invalid JWT"}, 401)
    else:
        # missing JWT
        return return_json({"Error": "Missing JWT"}, 401)     

    if request.method == 'PATCH':
        # ensure that both student and course exist 
        if course and student:            
            # verify that student is in same level as the course they are trying to enroll in
            if student["current_level"] != course["level"]:
                return return_json({"Error": str(student["lastname_firstname"]) + " is not in the correct level and cannot be enrolled"}, 400)

            # check that the instructor teaching this course is editing this course 
            if int(course["instructor"]) == int(user_id):
                course_students = course["students"]
                # iterate through list of students to ensure to no duplicate enrollments
                for person in course_students:
                    if person["id"] == student_id:
                        return return_json ({"Error": "The student is already enrolled in this course"}, 403)
                # add student to course by linking:
                # a) student_id and url to student data
                # b) student data to course data
                student_url = request.url_root + "students/" + str(student_id)
                student["id"] = student_id
                student["self"] = student_url
                course_students.append(student)            
                course.update({"students": course_students})
                client.put(course)
                return return_json(course, 200)
            else:
                return return_json({"Error": "Instructor ID does not match Course Instructor"}, 401)
            
        # if invalid course ID or student ID
        else:
            return return_json({'Error': 'The specified course and/or student does not exist'}, 404)

    elif request.method == 'DELETE':
        # check that course and student are valid
        if course and student:
            # check that the correct instructor is attempting to delete the course
            user_id = idinfo['sub']
            # check that the instructor teaching this course is editing this course 
            if int(course["instructor"]) == int(user_id):
                # delete course
                client.delete(course_key)
                return return_json({}, 204)                        
            else:
                return return_json({"Error": "Instructor ID does not match Course Instructor"}, 401)
         # if invalid course ID or student ID
        else:
            return return_json({'Error': 'The specified course and/or student does not exist'}, 404)
    else:
        return return_json({"Error": "Unsupported method"}, 405)

# THIS SECTION RETURNS ALL THE STUDENTS FOR A GIVEN COURSE
@app.route('/courses/<course_id>/students', methods=['GET'])
def students_courses_get(course_id):
    if request.method == 'GET':
        # get the course record from datastore 
        course_key = client.key(constants.courses, int(course_id))
        course = client.get(key=course_key)
        if course:
            course_students = course["students"]
            output = []
            # format the student for output
            for students in course_students:
                output.append(students)
            return return_json({"students": output}, 200)
        else:
            return return_json({"Error": "No course with this course_id exists"}, 404)
    else:
        return return_json({"Error": "Unsupported method"}, 405)

@app.route('/users', methods=['GET'])
def get_users():
    if request.method == 'GET':
        query = client.query(kind=constants.instructor)
        results = list(query.fetch())
        return return_json({"instructors": results}, 200)
    else:
        return return_json({"Error": "Unsupported method"}, 405)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=False)
