// Apps Script web app: returns your Google Classroom data as one JSON (read-only).
// Without the secret key below it answers "bad key". `python -m dz.setup classroom` fills in the key.
const KEY = '__SECRET_KEY__';  // replaced with a random key by `python -m dz.setup classroom`

function all_(fn, key) {
  // Classroom returns lists in pages via nextPageToken
  let items = [], page;
  do {
    const res = fn({pageSize: 100, pageToken: page});
    items = items.concat(res[key] || []);
    page = res.nextPageToken;
  } while (page);
  return items;
}

function safe_(f) {
  try { return f(); } catch (e) { return {error: String(e)}; }  // a section may be hidden from students
}

function dump() {
  const me = Classroom.UserProfiles.get('me');
  const courses = all_(o => Classroom.Courses.list(Object.assign({studentId: 'me'}, o)), 'courses');
  const perCourse = {};
  courses.forEach(c => {
    const id = c.id;
    perCourse[id] = {
      name: c.name, section: c.section, state: c.courseState, link: c.alternateLink,
      teachers: safe_(() => all_(o => Classroom.Courses.Teachers.list(id, o), 'teachers')),
      topics: safe_(() => all_(o => Classroom.Courses.Topics.list(id, o), 'topic')),
      coursework: safe_(() => all_(o => Classroom.Courses.CourseWork.list(id, o), 'courseWork')),
      submissions: safe_(() => all_(o => Classroom.Courses.CourseWork.StudentSubmissions.list(
          id, '-', Object.assign({userId: 'me'}, o)), 'studentSubmissions')),
      materials: safe_(() => all_(o => Classroom.Courses.CourseWorkMaterials.list(id, o), 'courseWorkMaterial')),
      announcements: safe_(() => all_(o => Classroom.Courses.Announcements.list(id, o), 'announcements')),
    };
  });
  return {profile: {id: me.id, name: me.name, emailAddress: me.emailAddress}, courses: courses, courses_detail: perCourse};
}

function doGet(e) {
  const out = e.parameter.key === KEY ? dump() : {error: 'bad key'};
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}
