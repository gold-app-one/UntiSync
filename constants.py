SECOND = 1
MINUTE = 60*SECOND
HOUR = 60*MINUTE
DAY = 24*HOUR
WEEK = 7*DAY
MONTH = 31*DAY

BACKWARD_TIME = WEEK
FORWARD_TIME = 2*WEEK

NAME_REPLACEMENTS: dict[str, str] = {
  'L12Ch-T': 'Chemie LK',
  'L12Ma-N': 'Mathe LK',
  'G12Phi-A': 'Philosophie',
  'G12In-B': 'Informatik',
  'G12DS-C': 'DS',
  'G12Ph-D': 'Physik',
  'G12EnZ-E': 'Englisch-Z',
  'G12De-F': 'Deutsch',
  'G12Ge-G': 'Geschichte',
  'G12En-H': 'Englisch',
  'G12B09': 'Tennis',
  'Rel ev': 'Religion',
}