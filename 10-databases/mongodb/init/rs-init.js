// Initialize replica set and seed university data

rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017", priority: 2 },
    { _id: 1, host: "mongo2:27017", priority: 1 },
    { _id: 2, host: "mongo3:27017", priority: 1 }
  ]
});

// Wait for THIS node to become primary
let attempts = 0;
while (attempts < 60) {
  try {
    const hello = db.adminCommand({ hello: 1 });
    if (hello.isWritablePrimary) {
      print("This node is now PRIMARY.");
      break;
    }
  } catch (e) {
    // ignore errors during election
  }
  sleep(1000);
  attempts++;
}
if (attempts >= 60) {
  print("WARNING: Timed out waiting for primary election.");
}

// Switch to university database
const db = db.getSiblingDB("university");

// Seed students
db.students.insertMany([
  { name: "Alice Johnson", email: "alice@university.edu", major: "Computer Science" },
  { name: "Bob Smith", email: "bob@university.edu", major: "Mathematics" },
  { name: "Carol Davis", email: "carol@university.edu", major: "Computer Science" },
  { name: "David Lee", email: "david@university.edu", major: "Physics" },
  { name: "Eva Martinez", email: "eva@university.edu", major: "Computer Science" },
  { name: "Frank Wilson", email: "frank@university.edu", major: "Mathematics" },
  { name: "Grace Kim", email: "grace@university.edu", major: "Biology" },
  { name: "Henry Brown", email: "henry@university.edu", major: "Computer Science" },
  { name: "Iris Chen", email: "iris@university.edu", major: "Physics" },
  { name: "Jack Taylor", email: "jack@university.edu", major: "Mathematics" }
]);

// Seed courses
db.courses.insertMany([
  { code: "CS101", title: "Intro to Programming", capacity: 30, enrolled: 4 },
  { code: "CS201", title: "Data Structures", capacity: 25, enrolled: 2 },
  { code: "MATH101", title: "Calculus I", capacity: 35, enrolled: 2 },
  { code: "PHYS101", title: "Physics I", capacity: 30, enrolled: 2 }
]);

// Seed enrollments (normalized -- separate collection)
const students = db.students.find().toArray();
const courses = db.courses.find().toArray();

db.enrollments.insertMany([
  { studentId: students[0]._id, courseId: courses[0]._id, enrolledAt: new Date() },
  { studentId: students[2]._id, courseId: courses[0]._id, enrolledAt: new Date() },
  { studentId: students[4]._id, courseId: courses[0]._id, enrolledAt: new Date() },
  { studentId: students[7]._id, courseId: courses[0]._id, enrolledAt: new Date() },
  { studentId: students[0]._id, courseId: courses[1]._id, enrolledAt: new Date() },
  { studentId: students[2]._id, courseId: courses[1]._id, enrolledAt: new Date() },
  { studentId: students[1]._id, courseId: courses[2]._id, enrolledAt: new Date() },
  { studentId: students[5]._id, courseId: courses[2]._id, enrolledAt: new Date() },
  { studentId: students[3]._id, courseId: courses[3]._id, enrolledAt: new Date() },
  { studentId: students[8]._id, courseId: courses[3]._id, enrolledAt: new Date() }
]);

// Seed denormalized collection (embedded documents for comparison)
db.students_denormalized.insertMany([
  {
    name: "Alice Johnson",
    email: "alice@university.edu",
    major: "Computer Science",
    enrollments: [
      { code: "CS101", title: "Intro to Programming", enrolledAt: new Date() },
      { code: "CS201", title: "Data Structures", enrolledAt: new Date() }
    ]
  },
  {
    name: "Bob Smith",
    email: "bob@university.edu",
    major: "Mathematics",
    enrollments: [
      { code: "MATH101", title: "Calculus I", enrolledAt: new Date() }
    ]
  }
]);

print("University database seeded successfully.");
