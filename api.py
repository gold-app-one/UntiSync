import webuntis
from webuntis.objects import PeriodObject, KlassenList, RoomList, SubjectList
import datetime
from constants import BACKWARD_TIME, FORWARD_TIME
from typing import Literal, Optional, List


class APIConnection:
  class Lesson:
    def __init__(self, period: PeriodObject) -> None:
      self.id: int = period.id
      self.cancelled: bool = period.code == 'cancelled'
      self.start: datetime.datetime = period.start
      self.end: datetime.datetime = period.end
      self.classes: KlassenList = period.klassen
      self.subjects: SubjectList = period.subjects
      # self.te: list[Teacher]
      self.students: str = period.studentGroup
      try:
        self.rooms: Optional[RoomList] = period.rooms
      except IndexError:
        self.rooms: Optional[RoomList] = None
      self.activityType: Literal['ls', 'oh', 'sb', 'bs', 'ex'] = period.type  # type: ignore
      self.exam = (
          hasattr(
              period,
              'info') and any(
              x in period.info.lower() for x in [ # type: ignore
                  'prüf',
                  'klausur',
                  'exam',
                  'lek',
                  'test'])) or self.activityType == 'ex'  # type: ignore

    def getStart(self) -> datetime.datetime:
      return self.start

    def getEnd(self) -> datetime.datetime:
      return self.end

    def getClass(self) -> str:
      if len(self.classes) > 0:
        return str(self.classes[0])
      else:
        return 'classless'

    def getSubject(self) -> str:
      if len(self.subjects) > 0:
        return str(self.subjects[0])
      else:
        return 'subjectless'

    def getStudents(self) -> str:
      return self.students

    def getRoom(self) -> str:
      if self.rooms is None or not (len(self.rooms) > 0):
        return 'roomless'
      else:
        return str(self.rooms[0])

    def getType(self) -> str:
      return self.activityType

    def isCancelled(self) -> bool:
      return self.cancelled or self.getRoom().lower() == 'zuhause'

    def isExam(self) -> bool:
      return self.exam

    def __str__(self) -> str:
      start = self.start
      end = self.end
      klassen = self.classes
      subjects = self.subjects
      students = self.students
      rooms = self.rooms
      cancelled = self.cancelled
      return f'{
          'X' if cancelled else 'O'};{start}-+-{end} | cla={
          str(klassen):^10}, sub={
          str(subjects):^15}, stu={
          students:^20}, room={
          str(rooms):^15}'

    def __repr__(self) -> str:
      return self.__str__()

  def __init__(
          self,
          surname: Optional[str],
          forename: Optional[str],
          username: Optional[str],
          password: Optional[str],
          school: Optional[str]) -> None:
    if surname is None or forename is None or username is None or password is None or school is None:
      print('WARNING: Missing env vars')
    self.lessons: List[APIConnection.Lesson] = []
    self.surname = surname
    self.forename = forename
    self.username = username
    self.password = password
    self.school = school

  def getLessons(self) -> List['APIConnection.Lesson']:
    """Returns the list of lessons retrieved from the API.

    Returns:
        List[APIConnection.Lesson]: List of lesson objects.
    """
    with webuntis.Session(  # type: ignore
        username=self.username,
        password=self.password,
        server='neilo.webuntis.com',
        school=self.school,
        useragent='WebUntis Test'
    ).login() as s:
      today = datetime.date.today() - datetime.timedelta(seconds=BACKWARD_TIME)
      end = datetime.date.today() + datetime.timedelta(seconds=FORWARD_TIME)
      timetable = s.timetable(start=today, end=end, student=s.get_student(self.surname, self.forename))  # type: ignore
      for activity in timetable:
        self.lessons.append(APIConnection.Lesson(activity))
    self.lessons.sort(key=lambda l: l.start)
    return self.lessons


if __name__ == '__main__':
  from dotenv import load_dotenv
  import os
  load_dotenv()
  SURNAME = os.getenv('SURNAME')
  FORENAME = os.getenv('FORENAME')
  USERNAME = os.getenv('UNTIS_USERNAME')
  PASSWORD = os.getenv('UNTIS_PASSWORD')
  SCHOOL = os.getenv('UNTIS_SCHOOL')
  CALENDAR_ID = os.getenv('CALENDAR_ID')
  conn = APIConnection(SURNAME, FORENAME, USERNAME, PASSWORD, SCHOOL)
  print(*[f'{l}\n' for l in conn.getLessons()])
