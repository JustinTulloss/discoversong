__author__ = 'Eugene Efremov'

from discoversong.includes import *

def generate_name():
  import random
  name = ''
  for i in range(10):
    name += letters[random.randrange(0, len(letters))]
    name += str(random.randrange(0, 9))
  name += '@discoversong.com'
  return name

def generate_playlist_name(existing_names):
  base_name = "discoversong's finds"
  name = base_name
  i = 0
  while name in existing_names:
    i += 1
    name = '%s %i' % (base_name, i)
  return name

def make_unique_email(db):
  
  exists = 1
  name = None
  
  while exists > 0:
    name = generate_name()
    exists = db.select('discoversong_user', what='count(*)', where="address='%s'" % name)[0]['count']
  
  return name

