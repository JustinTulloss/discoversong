def parse_vcast(subject):
  
  lead = 'Music ID: "'
  separator = '" by '
  
  if subject.find(lead) < 0 or subject.find(separator) < 0:
    raise ValueError('not VCast!')
  
  title_start = subject.find(lead) + len(lead)
  title_end = subject.find(separator)
  
  title = subject[title_start:title_end]
  
  artist_start = title_end + len(separator)
  
  artist = subject[artist_start:]

  return title, artist

def parse_shazam(subject):
  
  separator =  '- '
  
  title_end = subject.find(separator)
  if title_end < 0:
    raise ValueError('not Shazam!')
  
  title = subject[:title_end]
  
  artist_start = title_end + len(separator)
  artist = subject[artist_start:]
  return title, artist

def parse_unknown(subject):
  
  return subject, ''

def parse(subject):
  
  parsers = [parse_vcast,
             parse_shazam,
             parse_unknown] # this should always be last
  
  for parse in parsers:
    try:
      parsed = parse(subject)
      return parsed
    except:
      continue
  raise ValueError('at least the unknown parser should have worked!')

