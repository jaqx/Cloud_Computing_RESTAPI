# Cloud_Computing_RESTAPI
Background Information: This application tracks students’ progress through a language-learning program at a college. 
Instructors log in using their Google credentials. 
They use the application to see students’ initial level placement when they enrolled in the program as well as how 
many years it takes for students to complete the program. This helps instructors and administrators accurately assess the 
efficacy of their curriculum and plans of study.   Functionality:  Students are placed in Courses. 
When you add a Student to a Course, the Student’s Current Level must match the Course Level. 
When a Student is deleted, they are deleted from all courses they were enrolled in. 
Students cannot be added to a course until after the course has been created.   
Instructors are the Users. 
Unique Instructor IDs are created based on the “sub” field from a decoded JSON Web Token (JWT). 
A datastore entry is created from the JWT by linking the “sub” field with the “name” field. 
Instructors can create a course. 
Once a Course is created, only the original instructor can edit or delete that course. 
When an Instructor creates a Course, their id is automatically added to that course. 
